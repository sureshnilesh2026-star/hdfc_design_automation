"""Deterministic Decision/Router for Intent gate outcomes.

The Intent agent never decides whether it gets another attempt.
Max one clarify pass. No open-ended agent loop.

Routing vocabulary differs slightly from the Planner's: the Intent stage's
"repair" is a CLARIFY — a question put to a human — because the fix for an
ambiguous utterance is more information from the user, not a better guess from
the model. Re-running the model on identical input would just produce the same
proposal.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hdfc_journey.contracts.intent import IntentGateResult, IntentProposalOutput
from hdfc_journey.contracts.intent_enums import (
    IntentFailureClass,
    IntentRouteAction,
)
from hdfc_journey.contracts.intent_validation import IntentProposalValidationReport
from hdfc_journey.orchestrator.intent_gate import (
    REASON_AGENT_FAILED,
    REASON_AMBIGUOUS,
    REASON_INTENT_MISSING,
    REASON_INTENT_NOT_ALLOWLISTED,
    REASON_INTENT_UNKNOWN,
    REASON_LOW_CONFIDENCE,
    REASON_PLATFORM_NOT_ALLOWLISTED,
    REASON_PLATFORM_UNDERIVABLE,
    REASON_PROPOSAL_INVALID,
)

# Rejections a human question can plausibly fix — worth one clarify round.
CLARIFIABLE_REASONS: frozenset[str] = frozenset(
    {
        REASON_AMBIGUOUS,
        REASON_INTENT_UNKNOWN,
        REASON_LOW_CONFIDENCE,
    }
)

# Rejections no amount of asking the customer will fix. These are configuration
# or capability facts, and they go straight to a human operator.
STRUCTURAL_REASONS: frozenset[str] = frozenset(
    {
        REASON_PROPOSAL_INVALID,
        REASON_INTENT_MISSING,
        REASON_INTENT_NOT_ALLOWLISTED,
        REASON_PLATFORM_UNDERIVABLE,
        REASON_PLATFORM_NOT_ALLOWLISTED,
    }
)


class IntentRouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: IntentRouteAction
    failure_class: IntentFailureClass
    reason: str
    repair_pass: int = 0
    max_clarifications: int = 1
    gate_accepted: bool
    validation_passed: bool
    reason_codes: list[str] = Field(default_factory=list)
    clarifiable_codes: list[str] = Field(default_factory=list)
    structural_codes: list[str] = Field(default_factory=list)
    clarify_fields: list[str] = Field(default_factory=list)
    allow_continue: bool = False


class IntentClarificationRecord(BaseModel):
    """Audit trail for at most one clarify round."""

    model_config = ConfigDict(extra="forbid")

    original_proposal: dict[str, Any] = Field(default_factory=dict)
    original_validation: dict[str, Any] = Field(default_factory=dict)
    original_gate: dict[str, Any] = Field(default_factory=dict)
    clarify_attempted: bool = False
    repair_pass: int = 0
    clarified_proposal: dict[str, Any] | None = None
    clarified_validation: dict[str, Any] | None = None
    clarified_gate: dict[str, Any] | None = None
    routing_decisions: list[dict[str, Any]] = Field(default_factory=list)
    final_action: IntentRouteAction | None = None
    final_failure_class: IntentFailureClass | None = None


def _failure_class_for(codes: list[str]) -> IntentFailureClass:
    """Most specific failure class wins, for readable HITL reasons."""
    if REASON_AGENT_FAILED in codes:
        return IntentFailureClass.AGENT_FAILED
    if REASON_PROPOSAL_INVALID in codes:
        return IntentFailureClass.STRUCTURAL
    if REASON_INTENT_NOT_ALLOWLISTED in codes:
        return IntentFailureClass.NOT_ALLOWLISTED
    if REASON_PLATFORM_UNDERIVABLE in codes or REASON_PLATFORM_NOT_ALLOWLISTED in codes:
        return IntentFailureClass.PLATFORM_UNDERIVABLE
    # UNKNOWN_INTENT before AMBIGUOUS: an unidentifiable intent usually also
    # carries an ambiguity record, and the unknown intent is the root cause.
    if REASON_INTENT_UNKNOWN in codes:
        return IntentFailureClass.UNKNOWN_INTENT
    if REASON_AMBIGUOUS in codes:
        return IntentFailureClass.AMBIGUOUS
    if REASON_LOW_CONFIDENCE in codes:
        return IntentFailureClass.LOW_CONFIDENCE
    if REASON_INTENT_MISSING in codes:
        return IntentFailureClass.STRUCTURAL
    return IntentFailureClass.STRUCTURAL


def route_intent_result(
    *,
    output: IntentProposalOutput,
    report: IntentProposalValidationReport | None,
    gate_result: IntentGateResult,
    repair_pass: int,
    max_clarifications: int = 1,
) -> IntentRouterDecision:
    """
    Deterministic routing after Intent proposal + gate.

    The agent does not choose clarify/escalate — this function does.
    """
    max_clarifications = max(0, min(max_clarifications, 1))  # hard cap: one
    codes = list(gate_result.reason_codes)
    clarifiable = sorted(set(codes) & CLARIFIABLE_REASONS)
    structural = sorted(set(codes) & STRUCTURAL_REASONS)
    # Unknown codes fail closed to structural.
    unknown = sorted(set(codes) - CLARIFIABLE_REASONS - STRUCTURAL_REASONS)
    if unknown and REASON_AGENT_FAILED not in unknown:
        structural = sorted(set(structural) | set(unknown))

    validation_passed = bool(report and report.overall_passed)
    accepted = gate_result.is_accepted()

    def decide(
        action: IntentRouteAction,
        failure_class: IntentFailureClass,
        reason: str,
        *,
        allow_continue: bool = False,
        clarify_fields: list[str] | None = None,
    ) -> IntentRouterDecision:
        return IntentRouterDecision(
            action=action,
            failure_class=failure_class,
            reason=reason,
            repair_pass=repair_pass,
            max_clarifications=max_clarifications,
            gate_accepted=accepted,
            validation_passed=validation_passed,
            reason_codes=codes,
            clarifiable_codes=clarifiable,
            structural_codes=structural,
            clarify_fields=clarify_fields or [],
            allow_continue=allow_continue,
        )

    if accepted:
        return decide(
            IntentRouteAction.CONTINUE,
            IntentFailureClass.NONE,
            "Intent accepted by deterministic gate; proceed to knowledge retrieval.",
            allow_continue=True,
        )

    failure_class = _failure_class_for(codes)

    # Agent hard failure — a retriable transport error earns one re-run.
    if REASON_AGENT_FAILED in codes:
        retriable = bool(output.error and output.error.retriable)
        if retriable and repair_pass < max_clarifications:
            return decide(
                IntentRouteAction.CLARIFY,
                IntentFailureClass.AGENT_FAILED,
                "Intent agent failed with a retriable error; router grants one retry.",
            )
        return decide(
            IntentRouteAction.ESCALATE,
            IntentFailureClass.AGENT_FAILED
            if repair_pass == 0
            else IntentFailureClass.REPAIR_EXHAUSTED,
            "Intent agent failed; escalate.",
        )

    # Structural beats clarifiable — asking the customer cannot fix an
    # unsupported intent or an underivable platform.
    if structural:
        return decide(
            IntentRouteAction.ESCALATE,
            failure_class,
            f"Structural intent failure {structural}; workflow must not continue.",
        )

    if clarifiable and repair_pass < max_clarifications:
        fields = list(gate_result.unresolved_ambiguity_fields) or ["user_intent"]
        return decide(
            IntentRouteAction.CLARIFY,
            failure_class,
            f"Clarifiable intent gap {clarifiable}; one clarification round granted.",
            clarify_fields=fields,
        )

    return decide(
        IntentRouteAction.ESCALATE,
        IntentFailureClass.REPAIR_EXHAUSTED
        if repair_pass >= max_clarifications
        else failure_class,
        "Intent rejected without clarification budget remaining; escalate to human.",
    )
