"""Orchestrator: Journey Planner stage — build input, invoke agent, merge state.

Validation outcomes are routed by the deterministic Decision/Router.
The Planner never decides whether it gets another attempt.
Maximum of one Planner repair; no open-ended agent loop.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from hdfc_journey.agents.planner.agent import JourneyPlannerAgent
from hdfc_journey.agents.planner.prompts import PLANNER_PROMPT_VERSION
from hdfc_journey.contracts.planner import (
    AcceptedIntent,
    PlannerConfig,
    PlannerExecutionContext,
    PlannerInput,
    PlannerOutput,
    ReplanContext,
)
from hdfc_journey.contracts.skeleton import JourneySkeleton
from hdfc_journey.contracts.state import (
    BusinessError,
    BusinessStatus,
    DecisionEvent,
    JourneyGenerationState,
    PlanningAssumptionState,
    StageHistoryEntry,
)
from hdfc_journey.contracts.state_mapping import planning_state_patch_from_output
from hdfc_journey.logging_config import get_logger
from hdfc_journey.orchestrator.router import (
    FailureClass,
    PlannerRepairRecord,
    PlannerRouteAction,
    PlannerRouterDecision,
    route_planner_result,
)

logger = get_logger(__name__)


class PlanningStageError(ValueError):
    """Raised when state is not ready for the Planner stage."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_planner_input_from_state(
    state: JourneyGenerationState,
    skeleton: JourneySkeleton,
    *,
    replan_context: ReplanContext | None = None,
) -> PlannerInput:
    """
    Read-only projection from JourneyGenerationState → PlannerInput.

    Reads: business.input (indirect via accepted intent context),
    business.intent.accepted, business.knowledge, execution config.
    Does not mutate state.
    """
    if state.business.intent.accepted is None:
        raise PlanningStageError("business.intent.accepted is required before planning")
    if state.business.knowledge is None:
        raise PlanningStageError("business.knowledge is required before planning")
    if not state.business.planning.skeleton_id:
        raise PlanningStageError("business.planning.skeleton_id must be set by orchestrator")
    if skeleton.skeleton_id != state.business.planning.skeleton_id:
        raise PlanningStageError(
            f"skeleton.skeleton_id {skeleton.skeleton_id!r} != "
            f"state.planning.skeleton_id {state.business.planning.skeleton_id!r}"
        )

    accepted = state.business.intent.accepted
    intent_accepted = AcceptedIntent.model_validate(accepted.model_dump(mode="json"))

    cfg = state.execution.config_snapshot
    planner_config = PlannerConfig(
        planner_prompt_version=cfg.planner_prompt_version or PLANNER_PROMPT_VERSION,
    )

    repair_pass = state.execution.agents.planner.repair_pass
    execution = PlannerExecutionContext(
        run_id=state.execution.run_id,
        state_id=state.state_id,
        current_stage="planning",
        orchestrator_version=state.execution.orchestrator_version,
        repair_pass=repair_pass,
    )

    return PlannerInput(
        intent_accepted=intent_accepted,
        knowledge_pack=state.business.knowledge,
        skeleton=skeleton,
        config=planner_config,
        execution=execution,
        replan_context=replan_context,
    )


def merge_planner_output_into_state(
    state: JourneyGenerationState,
    output: PlannerOutput,
    *,
    latency_ms: float,
    model_name: str | None,
    prompt_version: str,
    validation_report: dict[str, Any] | None = None,
    workflow_status: BusinessStatus | None = None,
    stage_outcome: str | None = None,
    skip_status_update: bool = False,
) -> JourneyGenerationState:
    """
    Orchestrator-owned merge.

    Writes: business.planning (proposal fields), business.status, execution
    planner metadata, stage_history, trace, errors (on failure).

    Does NOT write: intent.accepted, knowledge, validation, output, hitl,
    generation.blueprint_*, execution.gates.

    HITL / escalation flags are applied separately via apply_planner_router_decision.
    """
    # Snapshot forbidden fields to assert no accidental mutation path.
    intent_accepted_before = (
        state.business.intent.accepted.model_dump(mode="json")
        if state.business.intent.accepted
        else None
    )
    knowledge_before = (
        state.business.knowledge.model_dump(mode="json")
        if state.business.knowledge
        else None
    )
    validation_before = state.business.validation.model_dump(mode="json")
    output_before = state.business.output.model_dump(mode="json")
    hitl_before = state.business.hitl.model_dump(mode="json")
    blueprint_final_before = state.business.generation.blueprint_final
    gates_before = state.execution.gates.model_dump(mode="json")
    skeleton_id = state.business.planning.skeleton_id

    patch = planning_state_patch_from_output(output)

    # Apply planning patch
    planning = state.business.planning
    planning.skeleton_id = skeleton_id  # orchestrator-owned; never cleared by patch

    if "decisions" in patch:
        planning.decisions = patch["decisions"]
    if "assumptions" in patch:
        planning.assumptions = [
            PlanningAssumptionState.model_validate(a) for a in patch["assumptions"]
        ]
    if "unknown_requirements" in patch:
        planning.unknown_requirements = patch["unknown_requirements"]
    if "entity_bindings" in patch:
        planning.entity_bindings = patch["entity_bindings"]
    if "required_information" in patch:
        planning.required_information = patch["required_information"]
    if "ordered_step_ids" in patch:
        planning.ordered_step_ids = patch["ordered_step_ids"]
    if "skipped_optional_step_ids" in patch:
        planning.skipped_optional_step_ids = patch["skipped_optional_step_ids"]
    if "selected_step_ids" in patch:
        planning.selected_step_ids = patch["selected_step_ids"]
    if "knowledge_references" in patch:
        planning.knowledge_references = patch["knowledge_references"]
    if "confidence" in patch:
        planning.confidence = patch["confidence"]
    if "planner_status" in patch:
        from hdfc_journey.contracts.enums import PlannerStatus

        planning.planner_status = PlannerStatus(patch["planner_status"])
    if "plan_artifact_type" in patch:
        planning.plan_artifact_type = patch["plan_artifact_type"]
    if "plan_schema_version" in patch:
        planning.plan_schema_version = patch["plan_schema_version"]
    if "error" in patch:
        planning.error = patch["error"]

    # Attach deterministic planner-output contract report (never blueprint validation).
    if validation_report is not None:
        planning.contract_validation_report = validation_report
        if validation_report.get("official_journey_validation") is True:
            raise RuntimeError(
                "Planner contract report must not set official_journey_validation=true"
            )

    # Status — Router may override via workflow_status after routing.
    if not skip_status_update:
        if workflow_status is not None:
            state.business.status = workflow_status
            resolved_outcome = stage_outcome or (
                "success" if workflow_status == "planned" else "error"
            )
            decision = f"planning_{workflow_status}"
        elif output.planner_ok:
            state.business.status = "planned"
            resolved_outcome = stage_outcome or "success"
            decision = "planning_completed"
        else:
            state.business.status = "failed"
            resolved_outcome = stage_outcome or "error"
            decision = "planning_failed"
            state.business.errors.append(
                BusinessError(
                    code=output.error.code if output.error else "planner_failed",
                    message=output.error.message if output.error else "Planner failed",
                    stage="planning",
                    source="planner_agent",
                    retriable=bool(output.error.retriable) if output.error else False,
                )
            )
    else:
        resolved_outcome = stage_outcome or "pending"
        decision = "planning_output_merged_pending_router"

    # Agent metadata
    structured_ok = output.planner_ok and output.artifact_type == "journey_plan"
    state.execution.agents.planner.model = model_name
    state.execution.agents.planner.prompt_version = prompt_version
    state.execution.agents.planner.latency_ms = latency_ms
    state.execution.agents.planner.structured_output_ok = structured_ok

    # Stage history: close open planning entry or append complete entry
    now = _utcnow()
    if (
        state.execution.stage_history
        and state.execution.stage_history[-1].stage == "planning"
        and state.execution.stage_history[-1].exited_at is None
    ):
        if not skip_status_update:
            state.execution.stage_history[-1].exited_at = now
            state.execution.stage_history[-1].outcome = resolved_outcome
    else:
        state.execution.stage_history.append(
            StageHistoryEntry(
                stage="planning",
                entered_at=now,
                exited_at=None if skip_status_update else now,
                outcome=None if skip_status_update else resolved_outcome,
            )
        )

    state.execution.current_stage = "planning"

    evidence = list(output.knowledge_references)
    if not evidence and output.planner_ok:
        evidence = [
            ref
            for d in output.decisions
            for ref in d.knowledge_source_ids
        ]

    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=now,
            stage="planning",
            actor="llm" if output.planner_ok or structured_ok else "code",
            component="journey_planner_agent",
            decision=decision,
            evidence_refs=sorted(set(evidence)),
            detail={
                "planner_status": output.planner_status.value,
                "planner_ok": output.planner_ok,
                "skeleton_id": output.skeleton_id,
                "ordered_step_ids": list(output.ordered_step_ids),
                "assumption_ids": [a.id for a in output.assumptions],
                "unknown_requirement_ids": [u.id for u in output.unknown_requirements],
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
                "official_journey_validation": False,
                "repair_pass": state.execution.agents.planner.repair_pass,
            },
        )
    )

    # Orchestrator merge event (deterministic)
    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=_utcnow(),
            stage="planning",
            actor="code",
            component="orchestrator.planning_merge",
            decision="merged_planner_output_into_business_planning",
            evidence_refs=sorted(set(evidence)),
            detail={
                "written_paths": [
                    "business.planning.decisions",
                    "business.planning.assumptions",
                    "business.planning.unknown_requirements",
                    "business.planning.entity_bindings",
                    "business.planning.required_information",
                    "business.planning.ordered_step_ids",
                    "business.status",
                    "execution.agents.planner",
                    "execution.trace",
                ],
                "forbidden_paths_untouched": [
                    "business.intent.accepted",
                    "business.knowledge",
                    "business.validation",
                    "business.output",
                    "business.hitl",
                    "business.generation.blueprint_final",
                    "execution.gates",
                ],
            },
        )
    )

    # Integrity: forbidden fields unchanged
    intent_accepted_after = (
        state.business.intent.accepted.model_dump(mode="json")
        if state.business.intent.accepted
        else None
    )
    knowledge_after = (
        state.business.knowledge.model_dump(mode="json")
        if state.business.knowledge
        else None
    )
    if intent_accepted_after != intent_accepted_before:
        raise RuntimeError("merge violated: business.intent.accepted was mutated")
    if knowledge_after != knowledge_before:
        raise RuntimeError("merge violated: business.knowledge was mutated")
    if state.business.validation.model_dump(mode="json") != validation_before:
        raise RuntimeError("merge violated: business.validation was mutated")
    if state.business.output.model_dump(mode="json") != output_before:
        raise RuntimeError("merge violated: business.output was mutated")
    if state.business.hitl.model_dump(mode="json") != hitl_before:
        raise RuntimeError("merge violated: business.hitl was mutated")
    if state.business.generation.blueprint_final != blueprint_final_before:
        raise RuntimeError("merge violated: blueprint_final was mutated")
    if state.execution.gates.model_dump(mode="json") != gates_before:
        raise RuntimeError("merge violated: execution.gates was mutated")

    state.touch()
    return state


def apply_planner_router_decision(
    state: JourneyGenerationState,
    decision: PlannerRouterDecision,
    *,
    repair_audit: PlannerRepairRecord,
) -> JourneyGenerationState:
    """
    Apply deterministic Router outcome to status + HITL.

    Planner must never call this. Does not mutate intent/knowledge/validation/gates.
    """
    state.business.planning.router_decision = decision.model_dump(mode="json")
    state.business.planning.repair_audit = repair_audit.model_dump(mode="json")

    if decision.action == PlannerRouteAction.CONTINUE and decision.allow_continue:
        state.business.status = "planned"
        stage_outcome = "success"
        route_decision = "router_continue"
    elif decision.action == PlannerRouteAction.ESCALATE:
        state.business.status = "escalated"
        state.business.hitl.required = True
        reasons = [decision.reason, f"failure_class={decision.failure_class.value}"]
        if decision.blocking_knowledge_gaps:
            reasons.append(
                "blocking_knowledge_gaps="
                + ",".join(decision.blocking_knowledge_gaps)
            )
        if decision.high_risk_assumption_ids:
            reasons.append(
                "high_risk_assumptions="
                + ",".join(decision.high_risk_assumption_ids)
            )
        if decision.structural_codes:
            reasons.append("structural_codes=" + ",".join(decision.structural_codes))
        state.business.hitl.reasons = reasons
        state.business.output.kind = "escalation"
        stage_outcome = "escalated"
        route_decision = "router_escalate"
        if decision.failure_class == FailureClass.STRUCTURAL:
            state.business.errors.append(
                BusinessError(
                    code="planner_structural_failure",
                    message=decision.reason,
                    stage="planning",
                    source="orchestrator.router",
                    retriable=False,
                )
            )
    else:
        # REPAIR should never be applied as a terminal decision.
        state.business.status = "failed"
        stage_outcome = "error"
        route_decision = "router_unexpected_terminal"

    # Close planning stage history if still open
    now = _utcnow()
    if (
        state.execution.stage_history
        and state.execution.stage_history[-1].stage == "planning"
        and state.execution.stage_history[-1].exited_at is None
    ):
        state.execution.stage_history[-1].exited_at = now
        state.execution.stage_history[-1].outcome = stage_outcome
    elif state.execution.stage_history and state.execution.stage_history[-1].stage == "planning":
        state.execution.stage_history[-1].outcome = stage_outcome

    state.execution.trace.append(
        DecisionEvent(
            event_id=uuid4(),
            at=now,
            stage="planning",
            actor="code",
            component="orchestrator.router",
            decision=route_decision,
            evidence_refs=[],
            detail={
                "action": decision.action.value,
                "failure_class": decision.failure_class.value,
                "reason": decision.reason,
                "repair_pass": decision.repair_pass,
                "max_repairs": decision.max_repairs,
                "validation_passed": decision.validation_passed,
                "allow_continue": decision.allow_continue,
                "blocking_knowledge_gaps": decision.blocking_knowledge_gaps,
                "high_risk_assumption_ids": decision.high_risk_assumption_ids,
                "structural_codes": decision.structural_codes,
                "repairable_codes": decision.repairable_codes,
                "repair_attempted": repair_audit.repair_attempted,
                "official_journey_validation": False,
            },
        )
    )
    state.touch()
    return state


def _validation_error_list(report: Any) -> list[str]:
    if report is None:
        return []
    return [f"{v.code}:{v.message}" for v in report.violations]


def _build_replan_context(
    output: PlannerOutput,
    report: Any,
) -> ReplanContext:
    errors = _validation_error_list(report)
    if report is not None and hasattr(report, "error_summary"):
        summary = report.error_summary()
        if summary and summary not in errors:
            errors.insert(0, summary)
    return ReplanContext(
        validation_errors=errors,
        prior_decision_ids=[d.id for d in output.decisions],
    )


def run_planning_stage(
    state: JourneyGenerationState,
    *,
    agent: JourneyPlannerAgent,
    skeleton: JourneySkeleton,
    replan_context: ReplanContext | None = None,
    model_name: str | None = None,
) -> tuple[JourneyGenerationState, PlannerOutput]:
    """
    Full Planner stage for the orchestrator.

    1) Open stage_history planning entry
    2) Propose via agent (no state mutation; no self-retry)
    3) Deterministic Router decides continue / one repair / escalate
    4) At most one repair pass, then merge + apply routing

    Hard cap: ``min(1, config.max_planner_repairs)`` Planner repairs.
    """
    now = _utcnow()
    state.execution.current_stage = "planning"
    state.execution.stage_history.append(
        StageHistoryEntry(stage="planning", entered_at=now, exited_at=None, outcome=None)
    )
    state.touch()

    max_repairs = min(1, max(0, state.execution.config_snapshot.max_planner_repairs))
    resolved_model = model_name or state.execution.config_snapshot.llm_model

    repair_audit = PlannerRepairRecord()
    active_replan = replan_context
    total_latency_ms = 0.0
    final_output: PlannerOutput | None = None
    final_report_dump: dict[str, Any] | None = None
    final_decision: PlannerRouterDecision | None = None

    # Bounded loop: initial propose + at most one repair (never open-ended).
    for repair_pass in range(0, max_repairs + 1):
        state.execution.agents.planner.repair_pass = repair_pass
        planner_input = build_planner_input_from_state(
            state, skeleton, replan_context=active_replan
        )

        t0 = time.perf_counter()
        output = agent.propose(planner_input)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        total_latency_ms += latency_ms

        report = agent.last_validation_report
        report_dump = report.model_dump(mode="json") if report is not None else None

        decision = route_planner_result(
            output=output,
            report=report,
            repair_pass=repair_pass,
            max_repairs=max_repairs,
        )

        state.execution.trace.append(
            DecisionEvent(
                event_id=uuid4(),
                at=_utcnow(),
                stage="planning",
                actor="code",
                component="orchestrator.router",
                decision=f"route_eval_{decision.action.value}",
                evidence_refs=[],
                detail={
                    "action": decision.action.value,
                    "failure_class": decision.failure_class.value,
                    "reason": decision.reason,
                    "repair_pass": repair_pass,
                    "max_repairs": max_repairs,
                    "validation_passed": decision.validation_passed,
                },
            )
        )

        if repair_pass == 0:
            repair_audit.original_output = output.model_dump(mode="json")
            repair_audit.original_validation = report_dump or {}
            repair_audit.validation_errors = _validation_error_list(report)
        else:
            repair_audit.repaired_output = output.model_dump(mode="json")
            repair_audit.repaired_validation = report_dump

        repair_audit.routing_decisions.append(decision.model_dump(mode="json"))

        if decision.action == PlannerRouteAction.REPAIR and repair_pass < max_repairs:
            repair_audit.repair_attempted = True
            repair_audit.repair_pass = repair_pass + 1
            active_replan = _build_replan_context(output, report)
            logger.info(
                "planner_repair_granted run_id=%s pass=%s reason=%s",
                state.execution.run_id,
                repair_pass + 1,
                decision.reason,
            )
            continue

        # Terminal: continue or escalate (including after exhausted repair).
        final_output = output
        final_report_dump = report_dump
        final_decision = decision
        repair_audit.final_validation = report_dump
        repair_audit.final_action = decision.action
        repair_audit.final_failure_class = decision.failure_class
        break
    else:
        # Defensive: loop completed without terminal break (should not happen).
        raise RuntimeError("Planner repair loop exited without a terminal router decision")

    assert final_output is not None and final_decision is not None

    logger.info(
        "planning_stage_complete run_id=%s planner_ok=%s route=%s "
        "failure_class=%s repair_attempted=%s latency_ms=%.1f",
        state.execution.run_id,
        final_output.planner_ok,
        final_decision.action.value,
        final_decision.failure_class.value,
        repair_audit.repair_attempted,
        total_latency_ms,
    )

    # Merge final Planner artifact first (HITL still untouched).
    state = merge_planner_output_into_state(
        state,
        final_output,
        latency_ms=total_latency_ms,
        model_name=resolved_model,
        prompt_version=agent.prompt_version,
        validation_report=final_report_dump,
        skip_status_update=True,
    )
    # Router owns continue vs escalate (and HITL).
    state = apply_planner_router_decision(
        state, final_decision, repair_audit=repair_audit
    )
    return state, final_output
