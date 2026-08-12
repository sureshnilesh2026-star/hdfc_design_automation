"""Deterministic Journey Planner output validation (no LLM).

Layers:
1. Schema validation
2. Referential-integrity validation
3. Knowledge-reference validation
4. Planner business-rule validation

This is NOT Journey Blueprint official validation.
PlannerOutput must never be marked validation_status=validated / official.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hdfc_journey.contracts.enums import (
    AssumptionRisk,
    AttributionKind,
    DecisionKind,
    PlannerStatus,
    RequiredInfoSource,
    UnknownRequirementKind,
)
from hdfc_journey.contracts.planner import PlannerInput, PlannerOutput


class ValidationLayer(StrEnum):
    SCHEMA = "schema"
    REFERENTIAL_INTEGRITY = "referential_integrity"
    KNOWLEDGE_REFERENCE = "knowledge_reference"
    BUSINESS_RULE = "business_rule"


class ViolationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class PlannerOutputViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    layer: ValidationLayer
    severity: ViolationSeverity = ViolationSeverity.ERROR
    path: str | None = None


class LayerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: ValidationLayer
    passed: bool
    violations: list[PlannerOutputViolation] = Field(default_factory=list)


class PlannerOutputValidationReport(BaseModel):
    """
    Deterministic validation report for a PlannerOutput artifact.

    Explicitly NOT an official Journey Blueprint validation result.
    """

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    validator_id: Literal["planner_output_deterministic_v1"] = (
        "planner_output_deterministic_v1"
    )
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Hard guarantee: this report never grants official journey validation.
    official_journey_validation: Literal[False] = False
    artifact_type_expected: Literal["journey_plan"] = "journey_plan"

    overall_passed: bool
    layers: list[LayerResult] = Field(default_factory=list)
    violations: list[PlannerOutputViolation] = Field(default_factory=list)
    warnings: list[PlannerOutputViolation] = Field(default_factory=list)

    input_skeleton_id: str | None = None
    input_pack_id: str | None = None
    output_planner_status: str | None = None
    output_planner_ok: bool | None = None

    def error_summary(self, limit: int = 12) -> str:
        errs = [v for v in self.violations if v.severity == ViolationSeverity.ERROR]
        return "; ".join(f"{v.code}:{v.message}" for v in errs[:limit])


# Backward-compatible aliases used by existing tests


class PlannerContractViolation:
    def __init__(self, code: str, message: str, path: str | None = None) -> None:
        self.code = code
        self.message = message
        self.path = path


class PlannerValidationResult:
    def __init__(
        self,
        ok: bool,
        violations: list[PlannerContractViolation] | None = None,
        report: PlannerOutputValidationReport | None = None,
    ) -> None:
        self.ok = ok
        self.violations = violations or []
        self.report = report

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise ValueError(
                f"Planner contract validation failed: {self.report.error_summary() if self.report else self.ok}"
            )


_ENDPOINTISH = re.compile(
    r"^(https?://|/?v\d+/|POST\s+/|GET\s+/|PUT\s+/|DELETE\s+/)",
    re.IGNORECASE,
)

_CONFIRMED_FACT_PATTERNS = re.compile(
    r"(annual fee is|eligibility (is |was )?approved|guaranteed approval|"
    r"POST\s+/|GET\s+/v\d+)",
    re.IGNORECASE,
)


def validate_planner_output_report(
    output: PlannerOutput | dict[str, Any] | None,
    input_data: PlannerInput,
) -> PlannerOutputValidationReport:
    """Run all four deterministic layers and return a structured report."""
    layers: list[LayerResult] = []
    all_violations: list[PlannerOutputViolation] = []

    schema_result, parsed = _layer_schema(output, input_data)
    layers.append(schema_result)
    all_violations.extend(schema_result.violations)

    if parsed is None:
        return _finalize_report(
            layers=layers,
            violations=all_violations,
            input_data=input_data,
            output=None,
        )

    # Failed planner outputs: schema identity checks only (already done)
    if parsed.planner_status == PlannerStatus.FAILED or not parsed.planner_ok:
        ref = _layer_referential(parsed, input_data, success_path=False)
        know = _layer_knowledge(parsed, input_data, success_path=False)
        biz = _layer_business_rules(parsed, input_data, success_path=False)
        layers.extend([ref, know, biz])
        all_violations.extend(ref.violations + know.violations + biz.violations)
        return _finalize_report(
            layers=layers,
            violations=all_violations,
            input_data=input_data,
            output=parsed,
        )

    ref = _layer_referential(parsed, input_data, success_path=True)
    know = _layer_knowledge(parsed, input_data, success_path=True)
    biz = _layer_business_rules(parsed, input_data, success_path=True)
    layers.extend([ref, know, biz])
    all_violations.extend(ref.violations + know.violations + biz.violations)

    return _finalize_report(
        layers=layers,
        violations=all_violations,
        input_data=input_data,
        output=parsed,
    )


def validate_planner_output(
    output: PlannerOutput,
    input_data: PlannerInput,
) -> PlannerValidationResult:
    """Backward-compatible wrapper around layered validation."""
    report = validate_planner_output_report(output, input_data)
    violations = [
        PlannerContractViolation(code=v.code, message=v.message, path=v.path)
        for v in report.violations
        if v.severity == ViolationSeverity.ERROR
    ]
    return PlannerValidationResult(
        ok=report.overall_passed, violations=violations, report=report
    )


def _finalize_report(
    *,
    layers: list[LayerResult],
    violations: list[PlannerOutputViolation],
    input_data: PlannerInput,
    output: PlannerOutput | None,
) -> PlannerOutputValidationReport:
    errors = [v for v in violations if v.severity == ViolationSeverity.ERROR]
    warnings = [v for v in violations if v.severity == ViolationSeverity.WARNING]
    return PlannerOutputValidationReport(
        overall_passed=len(errors) == 0,
        layers=layers,
        violations=errors,
        warnings=warnings,
        input_skeleton_id=input_data.skeleton.skeleton_id,
        input_pack_id=input_data.knowledge_pack.pack_id,
        output_planner_status=(
            None
            if output is None
            else (
                output.planner_status.value
                if hasattr(output.planner_status, "value")
                else str(output.planner_status)
            )
        ),
        output_planner_ok=output.planner_ok if output else None,
        official_journey_validation=False,
    )


def _v(
    code: str,
    message: str,
    layer: ValidationLayer,
    path: str | None = None,
    severity: ViolationSeverity = ViolationSeverity.ERROR,
) -> PlannerOutputViolation:
    return PlannerOutputViolation(
        code=code, message=message, layer=layer, path=path, severity=severity
    )


# ---------------------------------------------------------------------------
# 1. Schema validation
# ---------------------------------------------------------------------------


def _layer_schema(
    output: PlannerOutput | dict[str, Any] | None,
    input_data: PlannerInput,
) -> tuple[LayerResult, PlannerOutput | None]:
    violations: list[PlannerOutputViolation] = []
    parsed: PlannerOutput | None = None

    if output is None:
        violations.append(
            _v("missing_output", "Planner output is null", ValidationLayer.SCHEMA)
        )
        return LayerResult(layer=ValidationLayer.SCHEMA, passed=False, violations=violations), None

    try:
        parsed = (
            output
            if isinstance(output, PlannerOutput)
            else PlannerOutput.model_validate(output)
        )
    except ValidationError as exc:
        violations.append(
            _v(
                "schema_invalid",
                str(exc),
                ValidationLayer.SCHEMA,
            )
        )
        return LayerResult(layer=ValidationLayer.SCHEMA, passed=False, violations=violations), None

    required_fields = [
        "schema_version",
        "artifact_type",
        "planner_status",
        "planner_ok",
        "skeleton_id",
        "ordered_step_ids",
        "decisions",
        "entity_bindings",
        "required_information",
        "assumptions",
        "unknown_requirements",
        "knowledge_references",
    ]
    data = parsed.model_dump()
    for field_name in required_fields:
        if field_name not in data:
            violations.append(
                _v(
                    "missing_required_field",
                    f"Required field {field_name!r} missing",
                    ValidationLayer.SCHEMA,
                    field_name,
                )
            )

    if parsed.artifact_type != "journey_plan":
        violations.append(
            _v(
                "invalid_artifact_type",
                f"artifact_type must be journey_plan, got {parsed.artifact_type!r}",
                ValidationLayer.SCHEMA,
                "artifact_type",
            )
        )

    # Enum validity (Pydantic already enforces; re-check critical ones defensively)
    try:
        PlannerStatus(parsed.planner_status)
    except Exception:
        violations.append(
            _v(
                "invalid_enum",
                f"Invalid planner_status {parsed.planner_status!r}",
                ValidationLayer.SCHEMA,
                "planner_status",
            )
        )

    for d in parsed.decisions:
        try:
            DecisionKind(d.kind)
        except Exception:
            violations.append(
                _v(
                    "invalid_enum",
                    f"Invalid decision kind {d.kind!r}",
                    ValidationLayer.SCHEMA,
                    f"decisions[{d.id}].kind",
                )
            )
        for attr in d.attributions:
            try:
                AttributionKind(attr.kind)
            except Exception:
                violations.append(
                    _v(
                        "invalid_enum",
                        f"Invalid attribution kind {attr.kind!r}",
                        ValidationLayer.SCHEMA,
                        f"decisions[{d.id}].attributions",
                    )
                )

    for a in parsed.assumptions:
        try:
            AssumptionRisk(a.risk)
        except Exception:
            violations.append(
                _v(
                    "invalid_enum",
                    f"Invalid assumption risk {a.risk!r}",
                    ValidationLayer.SCHEMA,
                    f"assumptions[{a.id}].risk",
                )
            )
        if not a.statement.strip():
            violations.append(
                _v(
                    "assumption_schema",
                    "Assumption statement must be non-empty",
                    ValidationLayer.SCHEMA,
                    f"assumptions[{a.id}].statement",
                )
            )

    for u in parsed.unknown_requirements:
        try:
            UnknownRequirementKind(u.kind)
        except Exception:
            violations.append(
                _v(
                    "invalid_enum",
                    f"Invalid unknown_requirement kind {u.kind!r}",
                    ValidationLayer.SCHEMA,
                    f"unknown_requirements[{u.id}].kind",
                )
            )

    for ri in parsed.required_information:
        try:
            RequiredInfoSource(ri.source)
        except Exception:
            violations.append(
                _v(
                    "invalid_enum",
                    f"Invalid required_information source {ri.source!r}",
                    ValidationLayer.SCHEMA,
                    f"required_information[{ri.id}].source",
                )
            )

    # Planner must never claim official journey validation
    raw_keys = set(data.keys())
    if "validation_status" in raw_keys:
        violations.append(
            _v(
                "official_validation_forbidden",
                "PlannerOutput must not include validation_status (official journey validation)",
                ValidationLayer.SCHEMA,
                "validation_status",
            )
        )
    for forbidden in (
        "views",
        "actions",
        "api_requirements",
        "platform_extensions",
        "success_state",
        "navigation",
        "analytics",
        "content",
        "blueprint_id",
    ):
        if forbidden in raw_keys:
            violations.append(
                _v(
                    "blueprint_fields_forbidden",
                    f"PlannerOutput must not include JourneyBlueprint field {forbidden!r}",
                    ValidationLayer.SCHEMA,
                    forbidden,
                )
            )

    if parsed.skeleton_id != input_data.skeleton.skeleton_id:
        violations.append(
            _v(
                "skeleton_mismatch",
                f"output.skeleton_id {parsed.skeleton_id!r} != "
                f"input {input_data.skeleton.skeleton_id!r}",
                ValidationLayer.SCHEMA,
                "skeleton_id",
            )
        )

    passed = not any(v.severity == ViolationSeverity.ERROR for v in violations)
    return (
        LayerResult(layer=ValidationLayer.SCHEMA, passed=passed, violations=violations),
        parsed,
    )


# ---------------------------------------------------------------------------
# 2. Referential integrity
# ---------------------------------------------------------------------------


def _layer_referential(
    output: PlannerOutput,
    input_data: PlannerInput,
    *,
    success_path: bool,
) -> LayerResult:
    violations: list[PlannerOutputViolation] = []
    if not success_path:
        return LayerResult(
            layer=ValidationLayer.REFERENTIAL_INTEGRITY, passed=True, violations=[]
        )

    skeleton_ids = input_data.skeleton.step_ids()
    required_ids = input_data.skeleton.required_step_ids()
    optional_ids = skeleton_ids - required_ids
    ordered = output.ordered_step_ids
    skipped = set(output.skipped_optional_step_ids)

    entity_keys = {
        f"{e.type}:{e.value}" for e in input_data.intent_accepted.entities
    }
    entity_types = {e.type for e in input_data.intent_accepted.entities}
    allowlist = set(input_data.config.decision_kinds_allowlist)

    for step_id in ordered:
        if step_id not in skeleton_ids:
            violations.append(
                _v(
                    "unknown_step",
                    f"ordered step {step_id!r} is not in the supplied skeleton",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    "ordered_step_ids",
                )
            )

    for step_id in skipped:
        if step_id not in skeleton_ids:
            violations.append(
                _v(
                    "unknown_step",
                    f"skipped step {step_id!r} is not in the supplied skeleton",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    "skipped_optional_step_ids",
                )
            )
        elif step_id not in optional_ids and input_data.config.allow_skip_only_optional_steps:
            violations.append(
                _v(
                    "skip_required_forbidden",
                    f"cannot skip required skeleton step {step_id!r}",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    "skipped_optional_step_ids",
                )
            )

    if set(ordered) & skipped:
        violations.append(
            _v(
                "step_both_selected_and_skipped",
                "a step cannot appear in both ordered_step_ids and skipped_optional_step_ids",
                ValidationLayer.REFERENTIAL_INTEGRITY,
            )
        )

    for step_id in sorted(required_ids - set(ordered)):
        violations.append(
            _v(
                "missing_required_step",
                f"required skeleton step {step_id!r} missing from ordered_step_ids",
                ValidationLayer.REFERENTIAL_INTEGRITY,
                "ordered_step_ids",
            )
        )

    if len(ordered) != len(set(ordered)):
        violations.append(
            _v(
                "duplicate_step",
                "ordered_step_ids must be unique",
                ValidationLayer.REFERENTIAL_INTEGRITY,
                "ordered_step_ids",
            )
        )

    # Ordering must respect skeleton ordinals for selected required steps
    ordinal = {s.id: s.ordinal for s in input_data.skeleton.steps}
    selected_known = [s for s in ordered if s in ordinal]
    if selected_known != sorted(selected_known, key=lambda i: ordinal[i]):
        violations.append(
            _v(
                "invalid_step_order",
                "ordered_step_ids must follow skeleton ordinal order",
                ValidationLayer.REFERENTIAL_INTEGRITY,
                "ordered_step_ids",
            )
        )

    if output.decisions and len({d.id for d in output.decisions}) != len(output.decisions):
        violations.append(
            _v(
                "duplicate_decision_id",
                "decision ids must be unique",
                ValidationLayer.REFERENTIAL_INTEGRITY,
                "decisions",
            )
        )

    for d in output.decisions:
        if d.kind not in allowlist:
            violations.append(
                _v(
                    "decision_kind_forbidden",
                    f"decision kind {d.kind!r} not in config allowlist",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    f"decisions[{d.id}]",
                )
            )
        for sid in d.related_step_ids:
            if sid not in skeleton_ids:
                violations.append(
                    _v(
                        "unknown_step",
                        f"related_step_id {sid!r} not in skeleton",
                        ValidationLayer.REFERENTIAL_INTEGRITY,
                        f"decisions[{d.id}]",
                    )
                )
        if d.kind == DecisionKind.SKIP_OPTIONAL and d.subject in skeleton_ids:
            if d.subject not in optional_ids:
                violations.append(
                    _v(
                        "skip_required_forbidden",
                        f"skip_optional on non-optional step {d.subject!r}",
                        ValidationLayer.REFERENTIAL_INTEGRITY,
                        f"decisions[{d.id}]",
                    )
                )

    for b in output.entity_bindings:
        key = f"{b.entity_type}:{b.entity_value}"
        if key not in entity_keys and b.entity_type not in entity_types:
            violations.append(
                _v(
                    "unbound_entity",
                    f"entity {key!r} not in accepted intent entities",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    f"entity_bindings[{b.entity_type}]",
                )
            )
        if b.target_step_id not in skeleton_ids:
            violations.append(
                _v(
                    "unknown_step",
                    f"binding target_step_id {b.target_step_id!r} not in skeleton",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    "entity_bindings",
                )
            )
        elif b.target_step_id not in ordered:
            violations.append(
                _v(
                    "binding_to_unselected_step",
                    f"binding targets step {b.target_step_id!r} not in ordered_step_ids",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    "entity_bindings",
                )
            )

    for ri in output.required_information:
        if ri.target_step_id and ri.target_step_id not in skeleton_ids:
            violations.append(
                _v(
                    "unknown_step",
                    f"required_information target_step_id {ri.target_step_id!r} not in skeleton",
                    ValidationLayer.REFERENTIAL_INTEGRITY,
                    f"required_information[{ri.id}]",
                )
            )

    for a in output.assumptions:
        for sid in a.related_step_ids:
            if sid not in skeleton_ids:
                violations.append(
                    _v(
                        "unknown_step",
                        f"assumption related_step_id {sid!r} not in skeleton",
                        ValidationLayer.REFERENTIAL_INTEGRITY,
                        f"assumptions[{a.id}]",
                    )
                )

    for u in output.unknown_requirements:
        for sid in u.related_step_ids:
            if sid not in skeleton_ids:
                violations.append(
                    _v(
                        "unknown_step",
                        f"unknown_requirement related_step_id {sid!r} not in skeleton",
                        ValidationLayer.REFERENTIAL_INTEGRITY,
                        f"unknown_requirements[{u.id}]",
                    )
                )

    if output.confidence:
        for sid in output.confidence.per_step:
            if sid not in skeleton_ids:
                violations.append(
                    _v(
                        "unknown_step",
                        f"confidence.per_step key {sid!r} not in skeleton",
                        ValidationLayer.REFERENTIAL_INTEGRITY,
                        "confidence.per_step",
                    )
                )

    if len(output.assumptions) > input_data.config.max_assumptions:
        violations.append(
            _v(
                "max_assumptions",
                f"assumptions exceed max_assumptions={input_data.config.max_assumptions}",
                ValidationLayer.REFERENTIAL_INTEGRITY,
                "assumptions",
            )
        )
    if len(output.unknown_requirements) > input_data.config.max_unknown_requirements:
        violations.append(
            _v(
                "max_unknowns",
                f"unknown_requirements exceed max={input_data.config.max_unknown_requirements}",
                ValidationLayer.REFERENTIAL_INTEGRITY,
                "unknown_requirements",
            )
        )

    passed = not any(v.severity == ViolationSeverity.ERROR for v in violations)
    return LayerResult(
        layer=ValidationLayer.REFERENTIAL_INTEGRITY,
        passed=passed,
        violations=violations,
    )


# ---------------------------------------------------------------------------
# 3. Knowledge-reference validation
# ---------------------------------------------------------------------------


def _layer_knowledge(
    output: PlannerOutput,
    input_data: PlannerInput,
    *,
    success_path: bool,
) -> LayerResult:
    violations: list[PlannerOutputViolation] = []
    if not success_path:
        return LayerResult(
            layer=ValidationLayer.KNOWLEDGE_REFERENCE, passed=True, violations=[]
        )

    pack_docs = input_data.knowledge_pack.document_ids()
    pack_chunks = input_data.knowledge_pack.chunk_ids()
    entity_keys = {
        f"{e.type}:{e.value}" for e in input_data.intent_accepted.entities
    }
    entity_types = {e.type for e in input_data.intent_accepted.entities}
    skeleton_ids = input_data.skeleton.step_ids()
    cited_docs: set[str] = set()

    def check_doc_ids(ids: list[str], path: str) -> None:
        for doc_id in ids:
            if _ENDPOINTISH.search(doc_id.strip()):
                violations.append(
                    _v(
                        "invented_endpoint_ref",
                        f"reference looks like an API endpoint: {doc_id!r}",
                        ValidationLayer.KNOWLEDGE_REFERENCE,
                        path,
                    )
                )
            elif doc_id not in pack_docs:
                violations.append(
                    _v(
                        "invented_knowledge_ref",
                        f"document_id {doc_id!r} is not in KnowledgePack.attribution_index",
                        ValidationLayer.KNOWLEDGE_REFERENCE,
                        path,
                    )
                )
            else:
                cited_docs.add(doc_id)

    def check_attributions(attributions: list, path: str) -> None:
        if input_data.config.require_citation_on_decisions and not attributions:
            violations.append(
                _v(
                    "missing_attribution",
                    "at least one attribution is required",
                    ValidationLayer.KNOWLEDGE_REFERENCE,
                    path,
                )
            )
            return
        for i, attr in enumerate(attributions):
            ap = f"{path}.attributions[{i}]"
            if attr.kind == AttributionKind.KNOWLEDGE_DOCUMENT:
                check_doc_ids([attr.ref], ap)
            elif attr.kind == AttributionKind.KNOWLEDGE_CHUNK:
                if attr.ref not in pack_chunks:
                    violations.append(
                        _v(
                            "invented_chunk_ref",
                            f"attribution chunk {attr.ref!r} not in KnowledgePack",
                            ValidationLayer.KNOWLEDGE_REFERENCE,
                            ap,
                        )
                    )
            elif attr.kind == AttributionKind.INPUT_ENTITY:
                if attr.ref not in entity_keys and attr.ref not in entity_types:
                    violations.append(
                        _v(
                            "unknown_input_entity",
                            f"attribution entity {attr.ref!r} not in accepted entities",
                            ValidationLayer.KNOWLEDGE_REFERENCE,
                            ap,
                        )
                    )
            elif attr.kind == AttributionKind.INPUT_INTENT:
                allowed = {
                    input_data.intent_accepted.user_intent,
                    "user_intent",
                    "journey_type",
                    "platform",
                    "product_domain",
                }
                if attr.ref not in allowed:
                    violations.append(
                        _v(
                            "unknown_intent_attr",
                            f"attribution intent ref {attr.ref!r} is not an accepted intent fact",
                            ValidationLayer.KNOWLEDGE_REFERENCE,
                            ap,
                        )
                    )
            elif attr.kind == AttributionKind.SKELETON_STEP:
                if attr.ref not in skeleton_ids:
                    violations.append(
                        _v(
                            "unknown_skeleton_attr",
                            f"attribution step {attr.ref!r} not in skeleton",
                            ValidationLayer.KNOWLEDGE_REFERENCE,
                            ap,
                        )
                    )
            elif attr.kind == AttributionKind.CONFIG:
                if not attr.ref:
                    violations.append(
                        _v(
                            "invalid_config_attr",
                            "config attribution ref empty",
                            ValidationLayer.KNOWLEDGE_REFERENCE,
                            ap,
                        )
                    )

    for d in output.decisions:
        if input_data.config.require_citation_on_decisions:
            check_attributions(d.attributions, f"decisions[{d.id}]")
        check_doc_ids(d.knowledge_source_ids, f"decisions[{d.id}].knowledge_source_ids")
        for sid in d.related_step_ids:
            step = input_data.skeleton.step_by_id(sid)
            if step and step.allowed_knowledge_source_ids and d.knowledge_source_ids:
                allowed = set(step.allowed_knowledge_source_ids) & pack_docs
                for doc_id in d.knowledge_source_ids:
                    if doc_id in pack_docs and doc_id not in allowed:
                        violations.append(
                            _v(
                                "step_citation_not_allowed",
                                f"document {doc_id!r} not in step {sid!r} allowed_knowledge_source_ids ∩ pack",
                                ValidationLayer.KNOWLEDGE_REFERENCE,
                                f"decisions[{d.id}]",
                            )
                        )

    for b in output.entity_bindings:
        check_attributions(b.attributions, f"entity_bindings[{b.entity_type}]")
        check_doc_ids(b.knowledge_source_ids, "entity_bindings.knowledge_source_ids")

    for ri in output.required_information:
        check_attributions(ri.attributions, f"required_information[{ri.id}]")
        check_doc_ids(ri.knowledge_source_ids, f"required_information[{ri.id}]")

    for a in output.assumptions:
        check_doc_ids(a.knowledge_source_ids, f"assumptions[{a.id}]")

    for u in output.unknown_requirements:
        check_doc_ids(u.knowledge_source_ids, f"unknown_requirements[{u.id}]")

    for doc_id in output.knowledge_references:
        check_doc_ids([doc_id], "knowledge_references")

    declared = set(output.knowledge_references)
    if cited_docs - declared:
        violations.append(
            _v(
                "knowledge_references_incomplete",
                f"cited docs missing from knowledge_references: {sorted(cited_docs - declared)}",
                ValidationLayer.KNOWLEDGE_REFERENCE,
                "knowledge_references",
            )
        )

    # Missing assets must never appear as confirmed knowledge refs
    missing_ids = {m.asset_id for m in input_data.knowledge_pack.missing_knowledge}
    for doc_id in output.knowledge_references:
        if doc_id in missing_ids:
            violations.append(
                _v(
                    "missing_asset_presented_as_knowledge",
                    f"missing_knowledge asset {doc_id!r} cited as confirmed knowledge",
                    ValidationLayer.KNOWLEDGE_REFERENCE,
                    "knowledge_references",
                )
            )

    passed = not any(v.severity == ViolationSeverity.ERROR for v in violations)
    return LayerResult(
        layer=ValidationLayer.KNOWLEDGE_REFERENCE,
        passed=passed,
        violations=violations,
    )


# ---------------------------------------------------------------------------
# 4. Planner business-rule validation
# ---------------------------------------------------------------------------


def _layer_business_rules(
    output: PlannerOutput,
    input_data: PlannerInput,
    *,
    success_path: bool,
) -> LayerResult:
    violations: list[PlannerOutputViolation] = []
    if not success_path:
        return LayerResult(
            layer=ValidationLayer.BUSINESS_RULE, passed=True, violations=[]
        )

    # Blocking missing knowledge must be explicit unknowns
    blocking_missing = [
        m for m in input_data.knowledge_pack.missing_knowledge if m.blocking
    ]
    for miss in blocking_missing:
        acknowledged = any(
            miss.asset_id in (u.id + u.description)
            for u in output.unknown_requirements
        )
        if not acknowledged:
            violations.append(
                _v(
                    "missing_knowledge_not_represented",
                    f"blocking missing knowledge {miss.asset_id!r} must appear in unknown_requirements",
                    ValidationLayer.BUSINESS_RULE,
                    "unknown_requirements",
                )
            )

    # Blocking conflicts must be acknowledged
    blocking_conflicts = [
        c for c in input_data.knowledge_pack.conflicts if c.severity == "blocking"
    ]
    if blocking_conflicts:
        conflict_ids = {c.conflict_id for c in blocking_conflicts}
        acknowledged = any(
            any(cid in (a.id + a.statement) for cid in conflict_ids)
            or "conflict" in a.statement.lower()
            for a in output.assumptions
        ) or any(
            "conflict" in u.description.lower() or u.id.startswith("U_conflict")
            for u in output.unknown_requirements
        )
        if not acknowledged:
            violations.append(
                _v(
                    "unacknowledged_knowledge_conflict",
                    "blocking KnowledgePack conflicts must be surfaced as assumption/unknown",
                    ValidationLayer.BUSINESS_RULE,
                    "assumptions",
                )
            )

    # Assumptions schema / honesty: material assumptions must must_confirm
    for a in output.assumptions:
        if a.risk in {AssumptionRisk.HIGH, AssumptionRisk.MEDIUM} and not a.must_confirm:
            violations.append(
                _v(
                    "assumption_must_confirm_required",
                    f"assumption {a.id} with risk={a.risk} must set must_confirm=true",
                    ValidationLayer.BUSINESS_RULE,
                    f"assumptions[{a.id}]",
                )
            )

    # No unsupported enterprise facts presented as confirmed (scan decision rationales)
    for d in output.decisions:
        if _CONFIRMED_FACT_PATTERNS.search(d.rationale or ""):
            # Allow only if clearly marked unknown/assumption decision
            if d.kind not in {
                DecisionKind.MARK_UNKNOWN_REQUIREMENT,
                DecisionKind.FLAG_ASSUMPTION,
            }:
                violations.append(
                    _v(
                        "unsupported_fact_as_confirmed",
                        f"decision {d.id} appears to assert unsupported enterprise fact in rationale",
                        ValidationLayer.BUSINESS_RULE,
                        f"decisions[{d.id}].rationale",
                    )
                )

    # Status consistency with gaps
    if output.unknown_requirements and output.planner_status == PlannerStatus.PLANNED:
        violations.append(
            _v(
                "status_inconsistent_with_unknowns",
                "planner_status must reflect unknowns when unknown_requirements present",
                ValidationLayer.BUSINESS_RULE,
                "planner_status",
            )
        )

    # Never allow official validation laundering via status strings
    if str(output.planner_status).lower() in {"validated", "approved", "official"}:
        violations.append(
            _v(
                "official_validation_forbidden",
                "Planner must never mark output as officially validated",
                ValidationLayer.BUSINESS_RULE,
                "planner_status",
            )
        )

    passed = not any(v.severity == ViolationSeverity.ERROR for v in violations)
    return LayerResult(
        layer=ValidationLayer.BUSINESS_RULE, passed=passed, violations=violations
    )
