"""Deterministic Planner Router unit tests."""

from __future__ import annotations

from hdfc_journey.contracts.enums import AssumptionRisk, AttributionKind, PlannerStatus
from hdfc_journey.contracts.planner import DecisionAttribution, PlannerError
from hdfc_journey.contracts.validation import validate_planner_output_report
from hdfc_journey.orchestrator.router import (
    FailureClass,
    PlannerRouteAction,
    route_planner_result,
)
from tests.fixtures.planner_examples import (
    example_planner_input,
    example_planner_output,
)


def test_valid_plan_with_blocking_gap_escalates() -> None:
    out = example_planner_output()
    report = validate_planner_output_report(out, example_planner_input())
    assert report.overall_passed
    decision = route_planner_result(
        output=out, report=report, repair_pass=0, max_repairs=1
    )
    assert decision.action == PlannerRouteAction.ESCALATE
    assert decision.failure_class == FailureClass.BLOCKING_KNOWLEDGE_GAP
    assert decision.allow_continue is False


def test_valid_plan_without_gaps_continues() -> None:
    out = example_planner_output().model_copy(deep=True)
    out.unknown_requirements = []
    out.assumptions = []
    out.planner_status = PlannerStatus.PLANNED
    # Drop unknown-marking decision that would fail status/business rules
    out.decisions = [d for d in out.decisions if d.id != "d_unknown_api"]
    inp = example_planner_input()
    # Clear blocking missing from pack for this unit route test — validation uses pack
    pack = inp.knowledge_pack.model_copy(deep=True)
    pack.missing_knowledge = []
    inp = inp.model_copy(update={"knowledge_pack": pack})
    report = validate_planner_output_report(out, inp)
    assert report.overall_passed, report.error_summary()
    decision = route_planner_result(
        output=out, report=report, repair_pass=0, max_repairs=1
    )
    assert decision.action == PlannerRouteAction.CONTINUE
    assert decision.failure_class == FailureClass.NONE
    assert decision.allow_continue is True


def test_high_risk_assumption_escalates() -> None:
    out = example_planner_output().model_copy(deep=True)
    out.unknown_requirements = [
        u.model_copy(update={"blocking_hint": False}) for u in out.unknown_requirements
    ]
    assert any(a.risk == AssumptionRisk.HIGH and a.must_confirm for a in out.assumptions)
    report = validate_planner_output_report(out, example_planner_input())
    decision = route_planner_result(
        output=out, report=report, repair_pass=0, max_repairs=1
    )
    assert decision.action == PlannerRouteAction.ESCALATE
    assert decision.failure_class == FailureClass.UNRESOLVED_HIGH_RISK_ASSUMPTION


def test_repairable_validation_grants_one_repair() -> None:
    out = example_planner_output().model_copy(deep=True)
    # Fail to represent pack.missing_knowledge → repairable business-rule code
    out.unknown_requirements = []
    out.assumptions = []
    out.decisions = [d for d in out.decisions if d.id != "d_unknown_api"]
    out.planner_status = PlannerStatus.PLANNED
    report = validate_planner_output_report(out, example_planner_input())
    assert not report.overall_passed
    assert any(v.code == "missing_knowledge_not_represented" for v in report.violations)
    decision = route_planner_result(
        output=out, report=report, repair_pass=0, max_repairs=1
    )
    assert decision.action == PlannerRouteAction.REPAIR
    assert decision.failure_class == FailureClass.REPAIRABLE_VALIDATION
    assert "missing_knowledge_not_represented" in decision.repairable_codes


def test_structural_invented_ref_escalates_without_repair() -> None:
    out = example_planner_output().model_copy(deep=True)
    out.decisions[0].knowledge_source_ids = ["INVENTED-DOC"]
    out.decisions[0].attributions = [
        DecisionAttribution(kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="INVENTED-DOC")
    ]
    out.knowledge_references = list(out.knowledge_references) + ["INVENTED-DOC"]
    report = validate_planner_output_report(out, example_planner_input())
    assert not report.overall_passed
    decision = route_planner_result(
        output=out, report=report, repair_pass=0, max_repairs=1
    )
    assert decision.action == PlannerRouteAction.ESCALATE
    assert decision.failure_class == FailureClass.STRUCTURAL
    assert "invented_knowledge_ref" in decision.structural_codes


def test_second_failure_escalates_repair_exhausted() -> None:
    out = example_planner_output().model_copy(deep=True)
    out.unknown_requirements = []
    out.assumptions = []
    out.decisions = [d for d in out.decisions if d.id != "d_unknown_api"]
    out.planner_status = PlannerStatus.PLANNED
    report = validate_planner_output_report(out, example_planner_input())
    decision = route_planner_result(
        output=out, report=report, repair_pass=1, max_repairs=1
    )
    assert decision.action == PlannerRouteAction.ESCALATE
    assert decision.failure_class == FailureClass.REPAIR_EXHAUSTED


def test_max_repairs_hard_capped_at_one() -> None:
    out = example_planner_output().model_copy(deep=True)
    out.planner_ok = False
    out.planner_status = PlannerStatus.FAILED
    out.error = PlannerError(code="llm_failure", message="down", retriable=True)
    out.ordered_step_ids = []
    out.decisions = []
    out.assumptions = []
    out.unknown_requirements = []
    out.entity_bindings = []
    out.required_information = []
    out.knowledge_references = []
    report = validate_planner_output_report(out, example_planner_input())
    d0 = route_planner_result(output=out, report=report, repair_pass=0, max_repairs=99)
    assert d0.max_repairs == 1
    assert d0.action == PlannerRouteAction.REPAIR
    d1 = route_planner_result(output=out, report=report, repair_pass=1, max_repairs=99)
    assert d1.action == PlannerRouteAction.ESCALATE
