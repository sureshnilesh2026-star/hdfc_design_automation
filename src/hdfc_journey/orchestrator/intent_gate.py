"""Deterministic intent gate — the ONLY component that may accept an intent.

Design law for this module:

    The model proposes a hypothesis. This code decides whether the workflow may
    proceed, and derives every field it can derive rather than trusting the
    model's version of it.

Acceptance criteria, in priority order (model confidence is deliberately LAST):

1. The proposal artifact is structurally valid.
2. ``user_intent`` is a member of the intent registry (closed world).
3. There are no unresolved ambiguities.
4. ``platform`` is derivable from ``channel_hint`` (never from the model).
5. Model confidence clears the configured floor.

Criterion 5 is a coarse backstop, not the gate. A model can be confidently
wrong; it cannot be wrong about registry membership, because it does not decide
membership. This ordering is the architectural point of the whole component.

No LLM is used anywhere in this module.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hdfc_journey.contracts.enums import JourneyType, Platform, Priority
from hdfc_journey.contracts.intent import (
    AcceptedEntity,
    AcceptedIntent,
    IntentGateResult,
    IntentInput,
    IntentOverride,
    IntentProposalOutput,
)
from hdfc_journey.contracts.intent_enums import (
    UNKNOWN_INTENT,
    IntentGateVerdict,
    IntentOverrideReason,
    normalize_intent_id,
)
from hdfc_journey.contracts.intent_validation import (
    IntentProposalValidationReport,
)
from hdfc_journey.logging_config import get_logger

logger = get_logger(__name__)

# Channel -> platform. Configuration as data: adding a channel is a table edit,
# never a model decision and never an agent change.
DEFAULT_CHANNEL_PLATFORM_MAP: dict[str, Platform] = {
    "asknow": Platform.ASKNOW,
    "eva": Platform.EVA_DBU,
    "eva_dbu": Platform.EVA_DBU,
    "dbu": Platform.EVA_DBU,
    "web": Platform.WEB,
    "netbanking": Platform.WEB,
    "mobile": Platform.MOBILE_NATIVE,
    "mobile_native": Platform.MOBILE_NATIVE,
    "mobilebanking": Platform.MOBILE_NATIVE,
}

# Reason codes are machine-readable and drive routing + HITL messaging.
REASON_PROPOSAL_INVALID = "proposal_invalid"
REASON_AGENT_FAILED = "agent_failed"
REASON_INTENT_MISSING = "intent_missing"
REASON_INTENT_UNKNOWN = "intent_unknown"
REASON_INTENT_NOT_ALLOWLISTED = "intent_not_allowlisted"
REASON_AMBIGUOUS = "unresolved_ambiguity"
REASON_PLATFORM_UNDERIVABLE = "platform_underivable"
REASON_PLATFORM_NOT_ALLOWLISTED = "platform_not_allowlisted"
REASON_LOW_CONFIDENCE = "confidence_below_floor"


def derive_platform(
    channel_hint: str | None,
    channel_map: dict[str, Platform] | None = None,
) -> Platform | None:
    """Derive platform from the arrival channel. Returns None when underivable.

    The model's ``platform_hint`` is never consulted here — that is the point.
    """
    if not channel_hint:
        return None
    mapping = channel_map or DEFAULT_CHANNEL_PLATFORM_MAP
    return mapping.get(channel_hint.strip().lower())


def evaluate_intent_gate(
    *,
    output: IntentProposalOutput,
    intent_input: IntentInput,
    report: IntentProposalValidationReport | None,
    intent_allowlist: list[str] | None = None,
    platform_allowlist: list[str] | None = None,
    confidence_floor: float = 0.7,
    default_priority: Priority = Priority.NORMAL,
    channel_map: dict[str, Platform] | None = None,
) -> IntentGateResult:
    """Evaluate a proposal and produce an accept/reject verdict.

    Pure function. No I/O, no state mutation, no LLM. Given the same inputs it
    always returns the same verdict, which is what makes the decision auditable
    and replayable from the config snapshot.
    """
    now = datetime.now(timezone.utc)
    reasons: list[str] = []
    reason_codes: list[str] = []
    overrides: list[IntentOverride] = []
    registry = intent_input.config.registry

    def reject() -> IntentGateResult:
        return IntentGateResult(
            verdict=IntentGateVerdict.REJECTED,
            evaluated_at=now,
            accepted_intent=None,
            reason_codes=reason_codes,
            reasons=reasons,
            overrides=overrides,
            dropped_entity_types=[],
            unresolved_ambiguity_fields=[a.field.value for a in output.ambiguities],
            confidence_floor_applied=confidence_floor,
            model_confidence=output.confidence,
        )

    def fail(code: str, message: str) -> None:
        """Record a rejection reason without short-circuiting.

        Checks accumulate rather than return early so a human operator sees
        every reason at once, and so the Router can apply its
        structural-beats-clarifiable precedence rule over the full set.
        """
        reason_codes.append(code)
        reasons.append(message)

    # -- 0. Agent-level failure ---------------------------------------------
    # This one DOES short-circuit: a failed agent produced no artifact, so no
    # further check has anything meaningful to inspect.
    if not output.proposal_ok:
        code = output.error.code if output.error else "unknown"
        fail(REASON_AGENT_FAILED, f"Intent agent failed ({code}); nothing to accept.")
        return reject()

    # -- 1. Artifact validity ------------------------------------------------
    if report is not None and not report.overall_passed:
        fail(
            REASON_PROPOSAL_INVALID,
            f"Proposal artifact failed deterministic validation: "
            f"{report.error_summary()}",
        )

    # -- 2. Closed-world intent membership -----------------------------------
    raw_intent = output.user_intent
    definition = None
    normalized_intent = None

    if raw_intent is None:
        fail(REASON_INTENT_MISSING, "Proposal carries no user_intent.")
    else:
        # Shared with the validator so both agree on what 'well-formed' means.
        normalized_intent = normalize_intent_id(raw_intent)
        if normalized_intent != raw_intent:
            overrides.append(
                IntentOverride(
                    field="user_intent",
                    reason=IntentOverrideReason.INTENT_CASE_NORMALIZED,
                    model_value=raw_intent,
                    accepted_value=normalized_intent,
                )
            )

        if normalized_intent == UNKNOWN_INTENT:
            fail(
                REASON_INTENT_UNKNOWN,
                "Intent could not be identified from the utterance; "
                "human clarification required rather than a guess.",
            )
        else:
            definition = registry.get(normalized_intent)
            if definition is None:
                fail(
                    REASON_INTENT_NOT_ALLOWLISTED,
                    f"Proposed intent {normalized_intent!r} is not in the enterprise "
                    f"intent registry; refusing to act on an unsupported intent.",
                )
            elif (
                intent_allowlist is not None
                and normalized_intent not in intent_allowlist
            ):
                # A second, independent allowlist (from the run's config snapshot)
                # may narrow the registry further for a given deployment.
                fail(
                    REASON_INTENT_NOT_ALLOWLISTED,
                    f"Intent {normalized_intent!r} is registered but not enabled "
                    f"for this run (config intent_allowlist).",
                )

    # -- 3. Ambiguity is a hard blocker --------------------------------------
    if output.ambiguities:
        fields = ", ".join(sorted({a.field.value for a in output.ambiguities}))
        fail(
            REASON_AMBIGUOUS,
            f"Unresolved ambiguity on: {fields}. The agent explicitly declined to "
            f"guess; clarification is required before the journey is planned.",
        )

    # -- 4. Platform derived from channel, never from the model --------------
    platform = derive_platform(intent_input.utterance.channel_hint, channel_map)
    if platform is None:
        fail(
            REASON_PLATFORM_UNDERIVABLE,
            f"Platform is not derivable from channel_hint "
            f"{intent_input.utterance.channel_hint!r}; the model's platform_hint "
            f"is not authoritative and will not be substituted.",
        )
    else:
        if output.platform_hint is not None and output.platform_hint != platform:
            overrides.append(
                IntentOverride(
                    field="platform",
                    reason=IntentOverrideReason.PLATFORM_FROM_CHANNEL_HINT,
                    model_value=output.platform_hint.value,
                    accepted_value=platform.value,
                )
            )
        elif output.platform_hint is None:
            overrides.append(
                IntentOverride(
                    field="platform",
                    reason=IntentOverrideReason.PLATFORM_FROM_CHANNEL_HINT,
                    model_value=None,
                    accepted_value=platform.value,
                )
            )

        if platform_allowlist is not None and platform.value not in platform_allowlist:
            fail(
                REASON_PLATFORM_NOT_ALLOWLISTED,
                f"Platform {platform.value!r} is not enabled for this run "
                f"(config platform_allowlist).",
            )

    # -- 5. Confidence floor (coarse backstop, deliberately last) ------------
    # Checked last on purpose: membership, ambiguity, and platform derivability
    # are authoritative facts. Model confidence is only a coarse backstop, and a
    # model can be confidently wrong.
    if output.confidence < confidence_floor:
        fail(
            REASON_LOW_CONFIDENCE,
            f"Model confidence {output.confidence:.2f} is below floor "
            f"{confidence_floor:.2f}.",
        )

    if reason_codes:
        return reject()

    assert definition is not None and normalized_intent is not None and platform is not None

    # -- Derivations from the registry (code wins over model) ----------------
    journey_type: JourneyType = definition.journey_type
    if output.journey_type is not None and output.journey_type != journey_type:
        overrides.append(
            IntentOverride(
                field="journey_type",
                reason=IntentOverrideReason.JOURNEY_TYPE_FROM_REGISTRY,
                model_value=output.journey_type.value,
                accepted_value=journey_type.value,
            )
        )

    product_domain = definition.product_domain
    if output.product_domain != product_domain:
        overrides.append(
            IntentOverride(
                field="product_domain",
                reason=IntentOverrideReason.PRODUCT_DOMAIN_FROM_REGISTRY,
                model_value=output.product_domain,
                accepted_value=product_domain,
            )
        )

    if output.priority_hint is not None and output.priority_hint != default_priority:
        overrides.append(
            IntentOverride(
                field="priority",
                reason=IntentOverrideReason.PRIORITY_FROM_CONFIG,
                model_value=output.priority_hint.value,
                accepted_value=default_priority.value,
            )
        )

    # -- Entity filtering: registry-registered types only ---------------------
    allowed_types = set(definition.allowed_entity_types)
    accepted_entities: list[AcceptedEntity] = []
    dropped_types: list[str] = []
    seen: set[tuple[str, str]] = set()

    for ent in output.entities:
        if allowed_types and ent.type not in allowed_types:
            dropped_types.append(ent.type)
            overrides.append(
                IntentOverride(
                    field=f"entities.{ent.type}",
                    reason=IntentOverrideReason.ENTITY_TYPE_NOT_ALLOWED,
                    model_value=ent.type,
                    accepted_value=None,
                )
            )
            continue

        key = (ent.type, ent.value)
        if key in seen:
            overrides.append(
                IntentOverride(
                    field=f"entities.{ent.type}",
                    reason=IntentOverrideReason.ENTITY_DEDUPLICATED,
                    model_value=ent.value,
                    accepted_value=None,
                )
            )
            continue
        seen.add(key)

        clean_value = " ".join(ent.value.split())
        if clean_value != ent.value:
            overrides.append(
                IntentOverride(
                    field=f"entities.{ent.type}",
                    reason=IntentOverrideReason.ENTITY_VALUE_SANITIZED,
                    model_value=ent.value,
                    accepted_value=clean_value,
                )
            )

        accepted_entities.append(
            AcceptedEntity(
                type=ent.type,
                value=clean_value,
                raw_span=ent.raw_span,
                confidence=ent.confidence,
            )
        )

    accepted = AcceptedIntent(
        user_intent=normalized_intent,
        journey_type=journey_type,
        platform=platform,
        product_domain=product_domain,
        entities=accepted_entities,
        confidence=output.confidence,
        ambiguities=[],
        priority=default_priority,
        accepted_by="intent_gate",
        accepted_at=now,
    )

    reasons.append(
        f"Intent {normalized_intent} accepted: registry member, no unresolved "
        f"ambiguity, platform derived from channel, confidence "
        f"{output.confidence:.2f} >= {confidence_floor:.2f}."
    )

    logger.info(
        "intent_gate_accept run_id=%s intent=%s platform=%s entities=%s overrides=%s",
        intent_input.execution.run_id,
        normalized_intent,
        platform.value,
        len(accepted_entities),
        len(overrides),
    )

    return IntentGateResult(
        verdict=IntentGateVerdict.ACCEPTED,
        evaluated_at=now,
        accepted_intent=accepted,
        reason_codes=reason_codes,
        reasons=reasons,
        overrides=overrides,
        dropped_entity_types=sorted(set(dropped_types)),
        unresolved_ambiguity_fields=[],
        confidence_floor_applied=confidence_floor,
        model_confidence=output.confidence,
    )
