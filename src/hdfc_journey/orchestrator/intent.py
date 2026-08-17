"""Orchestrator: Intent Recognition stage — build input, invoke agent, gate, merge.

Acceptance is performed by the deterministic gate; outcomes are routed by the
deterministic Router. The Intent agent never decides whether it is accepted and
never decides whether it gets another attempt. Maximum one clarification round;
no open-ended agent loop.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from hdfc_journey.agents.intent.agent import IntentRecognitionAgent
from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.contracts.enums import Priority
from hdfc_journey.contracts.intent import (
    IntentAgentConfig,
    IntentClarificationContext,
    IntentExecutionContext,
    IntentGateResult,
    IntentInput,
    IntentProposalOutput,
    IntentUtterance,
)
from hdfc_journey.contracts.intent_enums import IntentFailureClass, IntentRouteAction
from hdfc_journey.contracts.intent_registry import IntentRegistry
from hdfc_journey.contracts.intent_state_mapping import (
    intent_accepted_state_patch,
    intent_proposal_state_patch,
)
from hdfc_journey.contracts.state import (
    BusinessError,
    BusinessStatus,
    DecisionEvent,
    JourneyGenerationState,
    StageHistoryEntry,
)
from hdfc_journey.logging_config import get_logger
from hdfc_journey.orchestrator.intent_gate import evaluate_intent_gate
from hdfc_journey.orchestrator.intent_router import (
    IntentClarificationRecord,
    IntentRouterDecision,
    route_intent_result,
)

logger = get_logger(__name__)


class IntentStageError(ValueError):
    """Raised when state is not ready for the Intent stage."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_intent_input_from_state(
    state: JourneyGenerationState,
    *,
    registry: IntentRegistry | None = None,
    clarification_context: IntentClarificationContext | None = None,
) -> IntentInput:
    """
    Read-only projection from JourneyGenerationState → IntentInput.

    Reads: business.input.normalized, execution config/run metadata.
    Does not mutate state.
    """
    normalized = state.business.input.normalized
    if not normalized.raw_text.strip():
        raise IntentStageError(
            "business.input.normalized.raw_text is required before intent recognition"
        )
    if normalized.modality not in ("text", "voice"):
        raise IntentStageError(
            f"unsupported modality {normalized.modality!r} for intent recognition"
        )

    cfg = state.execution.config_snapshot
    agent_config = IntentAgentConfig(
        intent_prompt_version=getattr(cfg, "intent_prompt_version", None)
        or INTENT_PROMPT_VERSION,
        registry=registry or IntentRegistry(),
    )

    execution = IntentExecutionContext(
        run_id=state.execution.run_id,
        state_id=state.state_id,
        current_stage="intent",
        orchestrator_version=state.execution.orchestrator_version,
        repair_pass=state.execution.agents.intent.repair_pass,
    )

    return IntentInput(
        utterance=IntentUtterance(
            raw_text=normalized.raw_text,
            modality=normalized.modality,  # type: ignore[arg-type]
            channel_hint=normalized.channel_hint,
            locale=normalized.locale,
            customer_context=dict(normalized.customer_context),
        ),
        config=agent_config,
        execution=execution,
        clarification_context=clarification_context,
    )


def merge_intent_proposal_into_state(
    state: JourneyGenerationState,
    output: IntentProposalOutput,
    *,
    latency_ms: float,
    model_name: str | None,
    prompt_version: str,
    validation_report: dict[str, Any] | None = None,
) -> JourneyGenerationState:
    """
    Orchestrator-owned merge of the PROPOSAL only.

    Writes: business.intent.proposal, execution.agents.intent, stage_history, trace.

    Does NOT write: business.intent.accepted, execution.gates, knowledge,
    planning, generation, validation, hitl, output. Those are asserted unchanged.
    """
    accepted_before = (
        state.business.intent.accepted.model_dump(mode="json")
        if state.business.intent.accepted
        else None
    )
    gates_before = state.execution.gates.model_dump(mode="json")
    knowledge_before = (
        state.business.knowledge.model_dump(mode="json")
        if state.business.knowledge
        else None
    )
    planning_before = state.business.planning.model_dump(mode="json")
    validation_before = state.business.validation.model_dump(mode="json")
    hitl_before = state.business.hitl.model_dump(mode="json")
    output_before = state.business.output.model_dump(mode="json")
    input_before = state.business.input.model_dump(mode="json")

    patch = intent_proposal_state_patch(output)
    state.business.intent.proposal = patch["proposal"]

    # Agent metadata
    structured_ok = output.proposal_ok and output.artifact_type == "intent_proposal"
    state.execution.agents.intent.model = model_name
    state.execution.agents.intent.prompt_version = prompt_version
    state.execution.agents.intent.latency_ms = latency_ms
    state.execution.agents.intent.structured_output_ok = structured_ok

    now = _utcnow()
    state.execution.current_stage = "intent"

    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=now,
            stage="intent",
            actor="llm" if structured_ok else "code",
            component="intent_recognition_agent",
            decision="intent_proposal_emitted",
            evidence_refs=[],
            detail={
                "intent_status": output.intent_status.value,
                "proposal_ok": output.proposal_ok,
                "user_intent": output.user_intent,
                "confidence": output.confidence,
                "ambiguity_fields": [a.field.value for a in output.ambiguities],
                "entity_types": sorted({e.type for e in output.entities}),
                "model": model_name,
                "prompt_version": prompt_version,
                "latency_ms": latency_ms,
                "structured_output_ok": structured_ok,
                "error": output.error.model_dump(mode="json") if output.error else None,
                "contract_validation_passed": (
                    None
                    if validation_report is None
                    else validation_report.get("overall_passed")
                ),
                "grants_acceptance": False,
                "repair_pass": state.execution.agents.intent.repair_pass,
            },
        )
    )

    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=_utcnow(),
            stage="intent",
            actor="code",
            component="orchestrator.intent_merge",
            decision="merged_intent_proposal_into_business_intent",
            evidence_refs=[],
            detail={
                "written_paths": [
                    "business.intent.proposal",
                    "execution.agents.intent",
                    "execution.trace",
                ],
                "forbidden_paths_untouched": [
                    "business.intent.accepted",
                    "business.input",
                    "business.knowledge",
                    "business.planning",
                    "business.validation",
                    "business.hitl",
                    "business.output",
                    "execution.gates",
                ],
            },
        )
    )

    # Integrity: forbidden fields unchanged.
    accepted_after = (
        state.business.intent.accepted.model_dump(mode="json")
        if state.business.intent.accepted
        else None
    )
    if accepted_after != accepted_before:
        raise RuntimeError("merge violated: business.intent.accepted was mutated")
    if state.execution.gates.model_dump(mode="json") != gates_before:
        raise RuntimeError("merge violated: execution.gates was mutated")
    if state.business.input.model_dump(mode="json") != input_before:
        raise RuntimeError("merge violated: business.input was mutated")
    knowledge_after = (
        state.business.knowledge.model_dump(mode="json")
        if state.business.knowledge
        else None
    )
    if knowledge_after != knowledge_before:
        raise RuntimeError("merge violated: business.knowledge was mutated")
    if state.business.planning.model_dump(mode="json") != planning_before:
        raise RuntimeError("merge violated: business.planning was mutated")
    if state.business.validation.model_dump(mode="json") != validation_before:
        raise RuntimeError("merge violated: business.validation was mutated")
    if state.business.hitl.model_dump(mode="json") != hitl_before:
        raise RuntimeError("merge violated: business.hitl was mutated")
    if state.business.output.model_dump(mode="json") != output_before:
        raise RuntimeError("merge violated: business.output was mutated")

    state.touch()
    return state


def apply_intent_gate_result(
    state: JourneyGenerationState,
    gate_result: IntentGateResult,
) -> JourneyGenerationState:
    """
    Write the gate verdict. The ONLY function that may set business.intent.accepted.

    The Intent agent must never call this.
    """
    state.execution.gates.intent_gate = (
        "passed" if gate_result.is_accepted() else "failed"
    )

    if gate_result.is_accepted():
        patch = intent_accepted_state_patch(gate_result)
        state.business.intent.accepted = patch["accepted"]

    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=_utcnow(),
            stage="intent",
            actor="code",
            component="orchestrator.intent_gate",
            decision=(
                "intent_accepted" if gate_result.is_accepted() else "intent_rejected"
            ),
            evidence_refs=[],
            detail={
                "verdict": gate_result.verdict.value,
                "gate_id": gate_result.gate_id,
                "reason_codes": gate_result.reason_codes,
                "reasons": gate_result.reasons,
                "overrides": [o.model_dump(mode="json") for o in gate_result.overrides],
                "dropped_entity_types": gate_result.dropped_entity_types,
                "unresolved_ambiguity_fields": gate_result.unresolved_ambiguity_fields,
                "model_confidence": gate_result.model_confidence,
                "confidence_floor_applied": gate_result.confidence_floor_applied,
            },
        )
    )
    state.touch()
    return state


def apply_intent_router_decision(
    state: JourneyGenerationState,
    decision: IntentRouterDecision,
    *,
    gate_result: IntentGateResult,
    clarification_audit: IntentClarificationRecord,
) -> JourneyGenerationState:
    """
    Apply the deterministic Router outcome to status + HITL.

    The Intent agent must never call this.
    """
    if decision.action == IntentRouteAction.CONTINUE and decision.allow_continue:
        status: BusinessStatus = "intent_resolved"
        stage_outcome = "success"
        route_decision = "router_continue"
    elif decision.action == IntentRouteAction.ESCALATE:
        status = "escalated"
        stage_outcome = "escalated"
        route_decision = "router_escalate"
        state.business.hitl.required = True
        reasons = [
            decision.reason,
            f"failure_class={decision.failure_class.value}",
            *gate_result.reasons,
        ]
        if decision.structural_codes:
            reasons.append("structural_codes=" + ",".join(decision.structural_codes))
        state.business.hitl.reasons = reasons
        state.business.output.kind = "escalation"

        # A clarifiable rejection that ran out of budget still deserves a
        # concrete question for the human operator.
        if gate_result.unresolved_ambiguity_fields:
            state.business.hitl.pending_questions = [
                {
                    "field": field,
                    "question": (
                        f"The customer's request is ambiguous on '{field}'. "
                        "Please confirm the intended reading."
                    ),
                }
                for field in gate_result.unresolved_ambiguity_fields
            ]

        if decision.failure_class in (
            IntentFailureClass.STRUCTURAL,
            IntentFailureClass.NOT_ALLOWLISTED,
            IntentFailureClass.PLATFORM_UNDERIVABLE,
        ):
            state.business.errors.append(
                BusinessError(
                    code="intent_structural_failure",
                    message=decision.reason,
                    stage="intent",
                    source="orchestrator.intent_router",
                    retriable=False,
                )
            )
    else:
        # CLARIFY should never be applied as a terminal decision.
        status = "failed"
        stage_outcome = "error"
        route_decision = "router_unexpected_terminal"

    state.business.status = status

    now = _utcnow()
    if (
        state.execution.stage_history
        and state.execution.stage_history[-1].stage == "intent"
        and state.execution.stage_history[-1].exited_at is None
    ):
        state.execution.stage_history[-1].exited_at = now
        state.execution.stage_history[-1].outcome = stage_outcome

    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=now,
            stage="intent",
            actor="code",
            component="orchestrator.intent_router",
            decision=route_decision,
            evidence_refs=[],
            detail={
                "action": decision.action.value,
                "failure_class": decision.failure_class.value,
                "reason": decision.reason,
                "repair_pass": decision.repair_pass,
                "max_clarifications": decision.max_clarifications,
                "gate_accepted": decision.gate_accepted,
                "validation_passed": decision.validation_passed,
                "allow_continue": decision.allow_continue,
                "reason_codes": decision.reason_codes,
                "structural_codes": decision.structural_codes,
                "clarifiable_codes": decision.clarifiable_codes,
                "clarify_attempted": clarification_audit.clarify_attempted,
            },
        )
    )
    state.touch()
    return state


def run_intent_stage(
    state: JourneyGenerationState,
    *,
    agent: IntentRecognitionAgent,
    registry: IntentRegistry | None = None,
    clarification_context: IntentClarificationContext | None = None,
    model_name: str | None = None,
    max_clarifications: int = 1,
) -> tuple[JourneyGenerationState, IntentProposalOutput, IntentGateResult]:
    """
    Full Intent stage for the orchestrator.

    1) Open a stage_history intent entry
    2) Propose via agent (no state mutation; no self-retry)
    3) Deterministic gate decides accept/reject
    4) Deterministic Router decides continue / one clarify / escalate
    5) Merge proposal, apply gate verdict, apply routing

    Hard cap: one clarification round.
    """
    now = _utcnow()
    state.execution.current_stage = "intent"
    state.execution.stage_history.append(
        StageHistoryEntry(stage="intent", entered_at=now, exited_at=None, outcome=None)
    )
    state.touch()

    cfg = state.execution.config_snapshot
    max_clarifications = min(1, max(0, max_clarifications))
    resolved_model = model_name or cfg.llm_model

    audit = IntentClarificationRecord()
    active_clarification = clarification_context
    total_latency_ms = 0.0

    final_output: IntentProposalOutput | None = None
    final_gate: IntentGateResult | None = None
    final_decision: IntentRouterDecision | None = None
    final_report_dump: dict[str, Any] | None = None

    for repair_pass in range(0, max_clarifications + 1):
        state.execution.agents.intent.repair_pass = repair_pass
        intent_input = build_intent_input_from_state(
            state, registry=registry, clarification_context=active_clarification
        )

        t0 = time.perf_counter()
        output = agent.propose(intent_input)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        total_latency_ms += latency_ms

        report = agent.last_validation_report
        report_dump = report.model_dump(mode="json") if report is not None else None

        gate_result = evaluate_intent_gate(
            output=output,
            intent_input=intent_input,
            report=report,
            intent_allowlist=cfg.intent_allowlist or None,
            platform_allowlist=cfg.platform_allowlist or None,
            confidence_floor=cfg.confidence_floor,
            default_priority=Priority.NORMAL,
        )

        decision = route_intent_result(
            output=output,
            report=report,
            gate_result=gate_result,
            repair_pass=repair_pass,
            max_clarifications=max_clarifications,
        )

        state.execution.trace.append(
            DecisionEvent(
                event_id=uuid4(),
                at=_utcnow(),
                stage="intent",
                actor="code",
                component="orchestrator.intent_router",
                decision=f"route_eval_{decision.action.value}",
                evidence_refs=[],
                detail={
                    "action": decision.action.value,
                    "failure_class": decision.failure_class.value,
                    "reason": decision.reason,
                    "repair_pass": repair_pass,
                    "max_clarifications": max_clarifications,
                    "gate_accepted": decision.gate_accepted,
                },
            )
        )

        if repair_pass == 0:
            audit.original_proposal = output.model_dump(mode="json")
            audit.original_validation = report_dump or {}
            audit.original_gate = gate_result.model_dump(mode="json")
        else:
            audit.clarified_proposal = output.model_dump(mode="json")
            audit.clarified_validation = report_dump
            audit.clarified_gate = gate_result.model_dump(mode="json")

        audit.routing_decisions.append(decision.model_dump(mode="json"))

        if decision.action == IntentRouteAction.CLARIFY and repair_pass < max_clarifications:
            audit.clarify_attempted = True
            audit.repair_pass = repair_pass + 1
            active_clarification = IntentClarificationContext(
                question_asked=None,
                human_answer=None,
                prior_ambiguity_fields=list(gate_result.unresolved_ambiguity_fields),
                validation_errors=list(report.codes()) if report else [],
            )
            logger.info(
                "intent_clarify_granted run_id=%s pass=%s reason=%s",
                state.execution.run_id,
                repair_pass + 1,
                decision.reason,
            )
            continue

        final_output = output
        final_gate = gate_result
        final_decision = decision
        final_report_dump = report_dump
        audit.final_action = decision.action
        audit.final_failure_class = decision.failure_class
        break
    else:
        raise RuntimeError("Intent clarify loop exited without a terminal decision")

    assert final_output is not None
    assert final_gate is not None
    assert final_decision is not None

    logger.info(
        "intent_stage_complete run_id=%s accepted=%s route=%s failure_class=%s "
        "clarify_attempted=%s latency_ms=%.1f",
        state.execution.run_id,
        final_gate.is_accepted(),
        final_decision.action.value,
        final_decision.failure_class.value,
        audit.clarify_attempted,
        total_latency_ms,
    )

    state = merge_intent_proposal_into_state(
        state,
        final_output,
        latency_ms=total_latency_ms,
        model_name=resolved_model,
        prompt_version=agent.prompt_version,
        validation_report=final_report_dump,
    )
    state = apply_intent_gate_result(state, final_gate)
    state = apply_intent_router_decision(
        state, final_decision, gate_result=final_gate, clarification_audit=audit
    )
    return state, final_output, final_gate
