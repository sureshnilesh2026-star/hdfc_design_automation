"""Tests for layered deterministic Planner output validation."""

from __future__ import annotations

from hdfc_journey.contracts.enums import AttributionKind, DecisionKind, PlannerStatus
from hdfc_journey.contracts.planner import DecisionAttribution, PlanningDecision
from hdfc_journey.contracts.validation import (
    validate_planner_output,
    validate_planner_output_report,
)
from hdfc_journey.llm.deterministic_planner import plan_from_planner_input
from tests.fixtures.adversarial import _pack, make_input
from tests.fixtures.planner_examples import example_planner_input, example_planner_output


def test_layered_report_passes_for_valid_plan() -> None:
    inp = example_planner_input()
    out = example_planner_output()
    report = validate_planner_output_report(out, inp)
    assert report.overall_passed
    assert report.official_journey_validation is False
    assert report.validator_id == "planner_output_deterministic_v1"
    assert {layer.layer for layer in report.layers} == {
        "schema",
        "referential_integrity",
        "knowledge_reference",
        "business_rule",
    }
    assert all(layer.passed for layer in report.layers)


def test_schema_layer_rejects_blueprint_fields_via_wrapper() -> None:
    # validate_planner_output remains compatible
    result = validate_planner_output(example_planner_output(), example_planner_input())
    assert result.ok
    assert result.report is not None
    assert result.report.official_journey_validation is False


def test_referential_layer_rejects_unknown_step() -> None:
    inp = example_planner_input()
    out = example_planner_output().model_copy(deep=True)
    out.ordered_step_ids = list(out.ordered_step_ids) + ["kyc_biometric_scan"]
    out.selected_step_ids = list(out.ordered_step_ids)
    report = validate_planner_output_report(out, inp)
    assert not report.overall_passed
    assert any(v.layer.value == "referential_integrity" for v in report.violations)
    assert any(v.code == "unknown_step" for v in report.violations)


def test_knowledge_layer_rejects_invented_doc() -> None:
    inp = example_planner_input()
    out = example_planner_output().model_copy(deep=True)
    out.knowledge_references = list(out.knowledge_references) + ["FAKE-DOC-999"]
    report = validate_planner_output_report(out, inp)
    assert not report.overall_passed
    assert any(v.layer.value == "knowledge_reference" for v in report.violations)
    assert any(v.code == "invented_knowledge_ref" for v in report.violations)


def test_business_rule_requires_blocking_missing_as_unknown() -> None:
    inp = make_input(pack=_pack(missing_api=True))
    out = plan_from_planner_input(inp)
    # Strip unknowns to simulate dishonest "confirmed" plan
    dishonest = out.model_copy(
        update={
            "unknown_requirements": [],
            "assumptions": [],
            "planner_status": PlannerStatus.PLANNED,
        }
    )
    # Remove mark_unknown decisions that mention the missing asset? business rule checks unknowns list
    report = validate_planner_output_report(dishonest, inp)
    assert not report.overall_passed
    assert any(v.code == "missing_knowledge_not_represented" for v in report.violations)
    assert any(v.layer.value == "business_rule" for v in report.violations)


def test_business_rule_rejects_unsupported_fact_in_rationale() -> None:
    inp = example_planner_input()
    out = example_planner_output().model_copy(deep=True)
    out.decisions = list(out.decisions) + [
        PlanningDecision(
            id="d_bad_fact",
            kind=DecisionKind.USE_SKELETON_STEP,
            subject="submit",
            rationale="annual fee is ₹0 guaranteed for all applicants",
            related_step_ids=["submit"],
            knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
            attributions=[
                DecisionAttribution(
                    kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                    ref="JOURNEY-CC-APPLY-STUB",
                )
            ],
        )
    ]
    report = validate_planner_output_report(out, inp)
    assert not report.overall_passed
    assert any(v.code == "unsupported_fact_as_confirmed" for v in report.violations)


def test_report_never_marks_official_validation() -> None:
    report = validate_planner_output_report(
        example_planner_output(), example_planner_input()
    )
    dumped = report.model_dump(mode="json")
    assert dumped["official_journey_validation"] is False
    assert "validated" not in str(dumped["output_planner_status"])
