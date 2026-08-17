"""Deterministic Decision/Router for Planner validation outcomes.

The Planner never decides whether it gets another attempt.
Max one Planner repair. No open-ended agent loop.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hdfc_journey.contracts.enums import AssumptionRisk
from hdfc_journey.contracts.planner import PlannerOutput
from hdfc_journey.contracts.validation import PlannerOutputValidationReport


class PlannerRouteAction(StrEnum):
    CONTINUE = "continue"
    REPAIR = "repair"
    ESCALATE = "escalate"


class FailureClass(StrEnum):
    NONE = "none"
    REPAIRABLE_VALIDATION = "repairable_validation"
    STRUCTURAL = "structural"
    BLOCKING_KNOWLEDGE_GAP = "blocking_knowledge_gap"
    UNRESOLVED_HIGH_RISK_ASSUMPTION = "unresolved_high_risk_assumption"
    REPAIR_EXHAUSTED = "repair_exhausted"
    PLANNER_FAILED = "planner_failed"


# Codes that must not continue and are not worth a blind LLM repair.
STRUCTURAL_CODES: frozenset[str] = frozenset(
    {
        "unknown_step",
        "skeleton_mismatch",
        "schema_invalid",
        "empty_plan",
        "invalid_step_order",
        "unbound_entity",
        "blueprint_fields_forbidden",
        "official_validation_forbidden",
        "skip_required_forbidden",
        "duplicate_step",
        "step_both_selected_and_skipped",
        "missing_required_step",
        "invented_knowledge_ref",
        "invented_chunk_ref",
        "invented_endpoint_ref",
        "missing_asset_presented_as_knowledge",
        "missing_required_field",
        "invalid_enum",
        "invalid_artifact_type",
        "uncitable_step",
        "binding_to_unselected_step",
    }
)

# Codes the LLM may fix on a single constrained repair pass.
REPAIRABLE_CODES: frozenset[str] = frozenset(
    {
        "knowledge_references_incomplete",
        "missing_attribution",
        "status_inconsistent_with_unknowns",
        "assumption_must_confirm_required",
        "missing_knowledge_not_represented",
        "unacknowledged_knowledge_conflict",
        "unsupported_fact_as_confirmed",
        "max_assumptions",
        "max_unknowns",
        "decision_kind_forbidden",
        "step_citation_not_allowed",
        "unknown_input_entity",
        "unknown_intent_attr",
        "unknown_skeleton_attr",
        "invalid_config_attr",
        "duplicate_decision_id",
    }
)


class PlannerRouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: PlannerRouteAction
    failure_class: FailureClass
    reason: str
    repair_pass: int = 0
    max_repairs: int = 1
    validation_passed: bool
    blocking_knowledge_gaps: list[str] = Field(default_factory=list)
    high_risk_assumption_ids: list[str] = Field(default_factory=list)
    structural_codes: list[str] = Field(default_factory=list)
    repairable_codes: list[str] = Field(default_factory=list)
    allow_continue: bool = False


class PlannerRepairRecord(BaseModel):
    """Audit trail for at most one Planner repair."""

    model_config = ConfigDict(extra="forbid")

    original_output: dict[str, Any] = Field(default_factory=dict)
    original_validation: dict[str, Any] = Field(default_factory=dict)
    validation_errors: list[str] = Field(default_factory=list)
    repair_attempted: bool = False
    repair_pass: int = 0
    repaired_output: dict[str, Any] | None = None
    repaired_validation: dict[str, Any] | None = None
    final_validation: dict[str, Any] | None = None
    routing_decisions: list[dict[str, Any]] = Field(default_factory=list)
    final_action: PlannerRouteAction | None = None
    final_failure_class: FailureClass | None = None


def _error_codes(report: PlannerOutputValidationReport | None) -> list[str]:
    if report is None:
        return []
    return [v.code for v in report.violations]


def _blocking_gaps(output: PlannerOutput) -> list[str]:
    gaps: list[str] = []
    for u in output.unknown_requirements:
        if u.blocking_hint:
            gaps.append(u.id)
    return gaps


def _high_risk_unresolved(output: PlannerOutput) -> list[str]:
    # Planner never resolves assumptions; unresolved == present with must_confirm.
    return [
        a.id
        for a in output.assumptions
        if a.must_confirm and a.risk == AssumptionRisk.HIGH
    ]


def route_planner_result(
    *,
    output: PlannerOutput,
    report: PlannerOutputValidationReport | None,
    repair_pass: int,
    max_repairs: int = 1,
) -> PlannerRouterDecision:
    """
    Deterministic routing after Planner + validation.

    Planner does not choose repair/escalate — this function does.
    """
    max_repairs = max(0, min(max_repairs, 1))  # hard cap: one repair
    codes = _error_codes(report)
    structural = sorted(set(codes) & STRUCTURAL_CODES)
    repairable = sorted(set(codes) & REPAIRABLE_CODES)
    # Unknown codes default to structural (fail closed)
    unknown_codes = sorted(set(codes) - STRUCTURAL_CODES - REPAIRABLE_CODES)
    if unknown_codes:
        structural = sorted(set(structural) | set(unknown_codes))

    validation_passed = bool(report and report.overall_passed)
    gaps = _blocking_gaps(output) if output.planner_ok else []
    high_risk = _high_risk_unresolved(output) if output.planner_ok else []

    def decide(
        action: PlannerRouteAction,
        failure_class: FailureClass,
        reason: str,
        *,
        allow_continue: bool = False,
    ) -> PlannerRouterDecision:
        return PlannerRouterDecision(
            action=action,
            failure_class=failure_class,
            reason=reason,
            repair_pass=repair_pass,
            max_repairs=max_repairs,
            validation_passed=validation_passed,
            blocking_knowledge_gaps=gaps,
            high_risk_assumption_ids=high_risk,
            structural_codes=structural,
            repairable_codes=repairable,
            allow_continue=allow_continue,
        )

    # Hard planner failure (LLM/schema) — repairable only if retriable llm/schema and budget left
    if not output.planner_ok or output.planner_status.value == "failed":
        err_code = output.error.code if output.error else "planner_failed"
        retriable = bool(output.error and output.error.retriable)
        if (
            retriable
            and err_code in {"llm_failure", "schema_invalid", "contract_violation"}
            and repair_pass < max_repairs
        ):
            return decide(
                PlannerRouteAction.REPAIR,
                FailureClass.REPAIRABLE_VALIDATION,
                f"Planner failed with retriable {err_code}; router grants one repair",
            )
        return decide(
            PlannerRouteAction.ESCALATE,
            FailureClass.PLANNER_FAILED
            if repair_pass == 0
            else FailureClass.REPAIR_EXHAUSTED,
            f"Planner failed ({err_code}); escalate",
        )

    if not validation_passed:
        if structural and not repairable:
            return decide(
                PlannerRouteAction.ESCALATE,
                FailureClass.STRUCTURAL,
                f"Structural validation failure: {structural}; workflow must not continue",
            )
        if structural and repairable:
            # Mixed: structural wins — do not repair invented steps/docs
            return decide(
                PlannerRouteAction.ESCALATE,
                FailureClass.STRUCTURAL,
                f"Structural issues present {structural}; refuse repair/continue",
            )
        if repairable and repair_pass < max_repairs:
            return decide(
                PlannerRouteAction.REPAIR,
                FailureClass.REPAIRABLE_VALIDATION,
                f"Repairable validation errors: {repairable}",
            )
        return decide(
            PlannerRouteAction.ESCALATE,
            FailureClass.REPAIR_EXHAUSTED
            if repair_pass >= max_repairs
            else FailureClass.STRUCTURAL,
            "Validation failed without repair budget or without repairable codes",
        )

    # Validation passed — still may escalate on policy gates
    if gaps:
        return decide(
            PlannerRouteAction.ESCALATE,
            FailureClass.BLOCKING_KNOWLEDGE_GAP,
            f"Blocking knowledge gaps require HITL: {gaps}",
        )
    if high_risk:
        return decide(
            PlannerRouteAction.ESCALATE,
            FailureClass.UNRESOLVED_HIGH_RISK_ASSUMPTION,
            f"Unresolved high-risk assumptions require HITL: {high_risk}",
        )

    return decide(
        PlannerRouteAction.CONTINUE,
        FailureClass.NONE,
        "Planner output valid; no blocking gaps or high-risk assumptions",
        allow_continue=True,
    )
