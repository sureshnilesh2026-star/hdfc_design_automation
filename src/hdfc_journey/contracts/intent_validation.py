"""Deterministic Intent proposal validation (no LLM).

Layers:
1. Schema validation
2. Referential integrity (enum/registry coherence of the proposal itself)
3. Vocabulary validation (closed-world intent membership)
4. Business-rule validation (honesty rules: status vs ambiguity vs confidence)

This is NOT acceptance. A proposal can be perfectly valid and still be rejected
by the gate (e.g. valid but ambiguous). Validation asks "is this artifact
well-formed?"; the gate asks "may the workflow proceed?".
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from hdfc_journey.contracts.intent import (
    IntentInput,
    IntentProposalOutput,
)
from hdfc_journey.contracts.intent_enums import (
    UNKNOWN_INTENT,
    IntentStatus,
    normalize_intent_id,
)

# Enterprise intent ids are UPPER_SNAKE by convention.
_INTENT_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
# Control characters / newlines in entity values are a prompt-injection smell.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class IntentValidationLayer(StrEnum):
    SCHEMA = "schema"
    REFERENTIAL_INTEGRITY = "referential_integrity"
    VOCABULARY = "vocabulary"
    BUSINESS_RULE = "business_rule"


class IntentViolationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class IntentProposalViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    layer: IntentValidationLayer
    severity: IntentViolationSeverity = IntentViolationSeverity.ERROR
    path: str | None = None


class IntentLayerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: IntentValidationLayer
    passed: bool
    violations: list[IntentProposalViolation] = Field(default_factory=list)


class IntentProposalValidationReport(BaseModel):
    """Deterministic validation report for an IntentProposalOutput artifact.

    Hard guarantee: this report never accepts an intent. ``grants_acceptance``
    is a frozen ``False`` so no caller can mistake a clean report for a verdict.
    """

    # validate_assignment makes the `grants_acceptance` guarantee real rather
    # than declarative: without it, pydantic would happily allow a caller to
    # set it to True after construction.
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    validator_id: Literal["intent_proposal_deterministic_v1"] = (
        "intent_proposal_deterministic_v1"
    )
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    grants_acceptance: Literal[False] = False
    artifact_type_expected: Literal["intent_proposal"] = "intent_proposal"

    overall_passed: bool
    layers: list[IntentLayerResult] = Field(default_factory=list)
    violations: list[IntentProposalViolation] = Field(default_factory=list)
    warnings: list[IntentProposalViolation] = Field(default_factory=list)

    input_run_id: str | None = None
    output_intent_status: str | None = None

    def error_summary(self) -> str:
        if not self.violations:
            return ""
        return "; ".join(f"{v.code}:{v.message}" for v in self.violations)

    def codes(self) -> list[str]:
        return [v.code for v in self.violations]


def _v(
    code: str,
    message: str,
    layer: IntentValidationLayer,
    path: str | None = None,
    severity: IntentViolationSeverity = IntentViolationSeverity.ERROR,
) -> IntentProposalViolation:
    return IntentProposalViolation(
        code=code, message=message, layer=layer, path=path, severity=severity
    )


def validate_intent_proposal_report(
    output: IntentProposalOutput,
    intent_input: IntentInput,
) -> IntentProposalValidationReport:
    """Validate a proposal artifact against its input. Pure function, no I/O."""
    violations: list[IntentProposalViolation] = []
    warnings: list[IntentProposalViolation] = []
    registry = intent_input.config.registry

    # -- Layer 1: schema -----------------------------------------------------
    schema_v: list[IntentProposalViolation] = []
    if output.artifact_type != "intent_proposal":
        schema_v.append(
            _v(
                "invalid_artifact_type",
                f"artifact_type must be 'intent_proposal', got {output.artifact_type!r}",
                IntentValidationLayer.SCHEMA,
                "artifact_type",
            )
        )
    if output.schema_version != "1.0.0":
        schema_v.append(
            _v(
                "invalid_schema_version",
                f"unexpected schema_version {output.schema_version!r}",
                IntentValidationLayer.SCHEMA,
                "schema_version",
            )
        )

    # -- Layer 2: referential integrity --------------------------------------
    ref_v: list[IntentProposalViolation] = []

    if output.proposal_ok and output.error is not None:
        ref_v.append(
            _v(
                "ok_with_error",
                "proposal_ok=true but error is populated",
                IntentValidationLayer.REFERENTIAL_INTEGRITY,
                "error",
            )
        )
    if not output.proposal_ok and output.error is None:
        ref_v.append(
            _v(
                "failed_without_error",
                "proposal_ok=false requires an error object",
                IntentValidationLayer.REFERENTIAL_INTEGRITY,
                "error",
            )
        )
    if output.intent_status == IntentStatus.FAILED and output.proposal_ok:
        ref_v.append(
            _v(
                "status_inconsistent_with_ok",
                "intent_status=failed contradicts proposal_ok=true",
                IntentValidationLayer.REFERENTIAL_INTEGRITY,
                "intent_status",
            )
        )

    if len(output.entities) > intent_input.config.max_entities:
        ref_v.append(
            _v(
                "max_entities",
                f"{len(output.entities)} entities exceeds cap "
                f"{intent_input.config.max_entities}",
                IntentValidationLayer.REFERENTIAL_INTEGRITY,
                "entities",
            )
        )
    if len(output.ambiguities) > intent_input.config.max_ambiguities:
        ref_v.append(
            _v(
                "max_ambiguities",
                f"{len(output.ambiguities)} ambiguities exceeds cap "
                f"{intent_input.config.max_ambiguities}",
                IntentValidationLayer.REFERENTIAL_INTEGRITY,
                "ambiguities",
            )
        )

    seen_entities: set[tuple[str, str]] = set()
    for idx, ent in enumerate(output.entities):
        key = (ent.type, ent.value)
        if key in seen_entities:
            warnings.append(
                _v(
                    "duplicate_entity",
                    f"duplicate entity {ent.type}={ent.value!r}",
                    IntentValidationLayer.REFERENTIAL_INTEGRITY,
                    f"entities[{idx}]",
                    IntentViolationSeverity.WARNING,
                )
            )
        seen_entities.add(key)
        if _CONTROL_CHARS_RE.search(ent.value) or _CONTROL_CHARS_RE.search(ent.type):
            ref_v.append(
                _v(
                    "entity_control_characters",
                    f"entity {ent.type!r} contains control characters",
                    IntentValidationLayer.REFERENTIAL_INTEGRITY,
                    f"entities[{idx}].value",
                )
            )

    # -- Layer 3: vocabulary (closed world) ----------------------------------
    vocab_v: list[IntentProposalViolation] = []
    ui = output.user_intent
    raw_unknown = UNKNOWN_INTENT

    # Validate the NORMALIZED form so that mere formatting (case, hyphens,
    # spaces) is recoverable by the gate rather than a contract violation.
    ui_normalized = normalize_intent_id(ui) if ui is not None else None
    if ui_normalized is not None and ui_normalized != raw_unknown:
        if ui_normalized != ui:
            warnings.append(
                _v(
                    "intent_id_not_canonical",
                    f"user_intent {ui!r} is not canonical; normalizes to "
                    f"{ui_normalized!r}",
                    IntentValidationLayer.VOCABULARY,
                    "user_intent",
                    IntentViolationSeverity.WARNING,
                )
            )
        if not _INTENT_ID_RE.match(ui_normalized):
            vocab_v.append(
                _v(
                    "malformed_intent_id",
                    f"user_intent {ui!r} is not a well-formed UPPER_SNAKE intent id",
                    IntentValidationLayer.VOCABULARY,
                    "user_intent",
                )
            )
        elif registry.get(ui_normalized) is None:
            # Deliberately a WARNING, not an error. The proposer is *allowed* to
            # be wrong about membership — catching that is precisely the gate's
            # job. Making it an artifact error here would mask the specific
            # `intent_not_allowlisted` gate reason behind a generic
            # `proposal_invalid`, which is far less useful to a human operator.
            warnings.append(
                _v(
                    "intent_not_in_registry",
                    f"user_intent {ui!r} is not an allowlisted enterprise intent",
                    IntentValidationLayer.VOCABULARY,
                    "user_intent",
                    IntentViolationSeverity.WARNING,
                )
            )

    if output.proposal_ok and ui is None:
        vocab_v.append(
            _v(
                "missing_user_intent",
                "proposal_ok=true requires user_intent (use 'UNKNOWN' when unresolved)",
                IntentValidationLayer.VOCABULARY,
                "user_intent",
            )
        )

    # Entity types must be plausible for the proposed intent when the intent is
    # known. Unknown types are a warning here; the gate drops them.
    if ui_normalized and registry.get(ui_normalized) is not None:
        allowed = set(registry.allowed_entity_types(ui_normalized))
        if allowed:
            for idx, ent in enumerate(output.entities):
                if ent.type not in allowed:
                    warnings.append(
                        _v(
                            "entity_type_not_registered",
                            f"entity type {ent.type!r} not registered for intent {ui_normalized}",
                            IntentValidationLayer.VOCABULARY,
                            f"entities[{idx}].type",
                            IntentViolationSeverity.WARNING,
                        )
                    )

    # -- Layer 4: business rules (honesty) -----------------------------------
    rule_v: list[IntentProposalViolation] = []

    if ui_normalized == UNKNOWN_INTENT and output.intent_status not in (
        IntentStatus.UNKNOWN,
        IntentStatus.PROPOSED_WITH_AMBIGUITY,
    ):
        rule_v.append(
            _v(
                "unknown_intent_status_mismatch",
                "user_intent=UNKNOWN requires intent_status unknown "
                "or proposed_with_ambiguity",
                IntentValidationLayer.BUSINESS_RULE,
                "intent_status",
            )
        )

    if output.ambiguities and output.intent_status == IntentStatus.PROPOSED:
        rule_v.append(
            _v(
                "ambiguity_status_mismatch",
                "ambiguities present but intent_status=proposed; "
                "must be proposed_with_ambiguity",
                IntentValidationLayer.BUSINESS_RULE,
                "intent_status",
            )
        )

    # Anti-overconfidence: declaring ambiguity while claiming near-certainty is
    # incoherent, and high confidence on UNKNOWN is the classic silent guess.
    if output.ambiguities and output.confidence > 0.9:
        rule_v.append(
            _v(
                "overconfident_with_ambiguity",
                f"confidence {output.confidence} too high with "
                f"{len(output.ambiguities)} unresolved ambiguities",
                IntentValidationLayer.BUSINESS_RULE,
                "confidence",
            )
        )
    if ui_normalized == UNKNOWN_INTENT and output.confidence > 0.5:
        rule_v.append(
            _v(
                "overconfident_unknown",
                f"confidence {output.confidence} is not defensible for UNKNOWN intent",
                IntentValidationLayer.BUSINESS_RULE,
                "confidence",
            )
        )

    for idx, amb in enumerate(output.ambiguities):
        if len(amb.candidates) == 1:
            warnings.append(
                _v(
                    "single_candidate_ambiguity",
                    f"ambiguity on {amb.field.value} lists only one candidate",
                    IntentValidationLayer.BUSINESS_RULE,
                    f"ambiguities[{idx}]",
                    IntentViolationSeverity.WARNING,
                )
            )

    # The proposer must not smuggle an acceptance-shaped claim into rationale.
    lowered = output.rationale.lower()
    for banned in ("accepted", "validated", "escalate", "route to", "approved"):
        if banned in lowered:
            rule_v.append(
                _v(
                    "rationale_claims_decision",
                    f"rationale contains decision language {banned!r}; "
                    "the proposer does not decide",
                    IntentValidationLayer.BUSINESS_RULE,
                    "rationale",
                )
            )
            break

    layers = [
        IntentLayerResult(
            layer=IntentValidationLayer.SCHEMA,
            passed=not schema_v,
            violations=schema_v,
        ),
        IntentLayerResult(
            layer=IntentValidationLayer.REFERENTIAL_INTEGRITY,
            passed=not ref_v,
            violations=ref_v,
        ),
        IntentLayerResult(
            layer=IntentValidationLayer.VOCABULARY,
            passed=not vocab_v,
            violations=vocab_v,
        ),
        IntentLayerResult(
            layer=IntentValidationLayer.BUSINESS_RULE,
            passed=not rule_v,
            violations=rule_v,
        ),
    ]
    violations = [*schema_v, *ref_v, *vocab_v, *rule_v]

    return IntentProposalValidationReport(
        overall_passed=not violations,
        layers=layers,
        violations=violations,
        warnings=warnings,
        input_run_id=str(intent_input.execution.run_id),
        output_intent_status=output.intent_status.value,
    )
