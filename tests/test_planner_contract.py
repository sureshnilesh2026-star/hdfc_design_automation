"""Contract tests for Journey Planner — no LLM."""

from __future__ import annotations

from uuid import uuid4

import pytest

from hdfc_journey.contracts.enums import (
    AssumptionRisk,
    AttributionKind,
    DecisionKind,
    JourneyType,
    Platform,
    PlannerStatus,
    RequiredInfoSource,
    SkeletonStepType,
    UnknownRequirementKind,
)
from hdfc_journey.contracts.knowledge_pack import (
    AttributionIndex,
    KnowledgePack,
    KnowledgeReference,
)
from hdfc_journey.contracts.planner import (
    AcceptedEntity,
    AcceptedIntent,
    DecisionAttribution,
    EntityBinding,
    PlannerConfig,
    PlannerExecutionContext,
    PlannerInput,
    PlannerOutput,
    PlanningAssumption,
    PlanningConfidence,
    PlanningDecision,
    RequiredInformation,
    UnknownRequirement,
)
from hdfc_journey.contracts.skeleton import JourneySkeleton, SkeletonStep
from hdfc_journey.contracts.state_mapping import planning_state_patch_from_output
from hdfc_journey.contracts.validation import validate_planner_output


def _pack() -> KnowledgePack:
    return KnowledgePack(
        pack_id="APPLY_CREDIT_CARD|asknow|test",
        references=[
            KnowledgeReference(asset_id="PROD-CC-001", level=2),
            KnowledgeReference(asset_id="PLT-ASK-001", level=3),
            KnowledgeReference(asset_id="JOURNEY-CC-APPLY-STUB", level=4, status="stub"),
        ],
        attribution_index=AttributionIndex(
            by_document=["PROD-CC-001", "PLT-ASK-001", "JOURNEY-CC-APPLY-STUB"]
        ),
    )


def _skeleton() -> JourneySkeleton:
    return JourneySkeleton(
        skeleton_id="JOURNEY-CC-APPLY-STUB",
        journey_id="JN-CC-APPLY",
        intent="APPLY_CREDIT_CARD",
        platform="asknow",
        journey_type="acquisition",
        product_domain="credit_cards",
        steps=[
            SkeletonStep(
                id="auth_gate",
                type=SkeletonStepType.AUTH_GATE,
                name="Authenticate",
                ordinal=0,
                optional=False,
            ),
            SkeletonStep(
                id="collect_profile",
                type=SkeletonStepType.INTERACTION,
                name="Collect profile",
                ordinal=1,
                optional=False,
                required_entity_types=["product"],
            ),
            SkeletonStep(
                id="optional_upsell",
                type=SkeletonStepType.INTERACTION,
                name="Optional upsell",
                ordinal=2,
                optional=True,
            ),
            SkeletonStep(
                id="submit",
                type=SkeletonStepType.TERMINAL,
                name="Submit",
                ordinal=3,
                optional=False,
            ),
        ],
    )


def _input() -> PlannerInput:
    return PlannerInput(
        intent_accepted=AcceptedIntent(
            user_intent="APPLY_CREDIT_CARD",
            journey_type=JourneyType.ACQUISITION,
            platform=Platform.ASKNOW,
            product_domain="credit_cards",
            entities=[AcceptedEntity(type="product", value="credit_card", confidence=0.9)],
            confidence=0.88,
        ),
        knowledge_pack=_pack(),
        skeleton=_skeleton(),
        config=PlannerConfig(planner_prompt_version="planner-v1"),
        execution=PlannerExecutionContext(run_id=uuid4()),
    )


def _attr_doc(doc_id: str = "JOURNEY-CC-APPLY-STUB") -> DecisionAttribution:
    return DecisionAttribution(kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=doc_id)


def _valid_output() -> PlannerOutput:
    return PlannerOutput(
        planner_status=PlannerStatus.PLANNED,
        planner_ok=True,
        skeleton_id="JOURNEY-CC-APPLY-STUB",
        ordered_step_ids=["auth_gate", "collect_profile", "submit"],
        skipped_optional_step_ids=["optional_upsell"],
        decisions=[
            PlanningDecision(
                id="d1",
                kind=DecisionKind.USE_SKELETON_STEP,
                subject="auth_gate",
                rationale="Auth required before protected apply actions",
                related_step_ids=["auth_gate"],
                knowledge_source_ids=["PLT-ASK-001"],
                attributions=[_attr_doc("PLT-ASK-001")],
            ),
            PlanningDecision(
                id="d2",
                kind=DecisionKind.SKIP_OPTIONAL,
                subject="optional_upsell",
                rationale="Not required for core apply path",
                related_step_ids=["optional_upsell"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
                attributions=[_attr_doc()],
            ),
            PlanningDecision(
                id="d3",
                kind=DecisionKind.REQUIRE_AUTH,
                subject="submit",
                rationale="Submit is protected",
                related_step_ids=["submit"],
                knowledge_source_ids=["PLT-ASK-001"],
                attributions=[_attr_doc("PLT-ASK-001")],
            ),
        ],
        entity_bindings=[
            EntityBinding(
                entity_type="product",
                entity_value="credit_card",
                target_step_id="collect_profile",
                target_field_hint="product_interest",
                knowledge_source_ids=["PROD-CC-001"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.INPUT_ENTITY, ref="product:credit_card"
                    ),
                    _attr_doc("PROD-CC-001"),
                ],
            )
        ],
        required_information=[
            RequiredInformation(
                id="full_name",
                name="Full name",
                required=True,
                source=RequiredInfoSource.USER,
                pii=True,
                target_step_id="collect_profile",
                attributions=[_attr_doc()],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
            )
        ],
        assumptions=[
            PlanningAssumption(
                id="A1",
                statement="Level 5 submit API shape is unknown and must be confirmed",
                risk=AssumptionRisk.HIGH,
                must_confirm=True,
                related_step_ids=["submit"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
            )
        ],
        unknown_requirements=[
            UnknownRequirement(
                id="U1",
                kind=UnknownRequirementKind.API,
                description="Submit application API binding not in pack",
                blocking_hint=True,
                related_step_ids=["submit"],
            )
        ],
        knowledge_references=["PLT-ASK-001", "PROD-CC-001", "JOURNEY-CC-APPLY-STUB"],
        confidence=PlanningConfidence(overall=0.8, per_step={"auth_gate": 0.9}),
    )


def test_valid_plan_passes_contract_validation() -> None:
    result = validate_planner_output(_valid_output(), _input())
    assert result.ok, result.violations


def test_invented_document_id_rejected() -> None:
    out = _valid_output()
    out.decisions[0].knowledge_source_ids = ["FAKE-DOC-999"]
    out.decisions[0].attributions = [
        DecisionAttribution(kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="FAKE-DOC-999")
    ]
    out.knowledge_references = ["FAKE-DOC-999", "PLT-ASK-001", "PROD-CC-001", "JOURNEY-CC-APPLY-STUB"]
    result = validate_planner_output(out, _input())
    assert not result.ok
    assert any(v.code == "invented_knowledge_ref" for v in result.violations)


def test_unknown_skeleton_step_rejected() -> None:
    out = _valid_output()
    out.ordered_step_ids = ["auth_gate", "collect_profile", "invented_step", "submit"]
    result = validate_planner_output(out, _input())
    assert not result.ok
    assert any(v.code == "unknown_step" for v in result.violations)


def test_skip_required_step_rejected() -> None:
    out = _valid_output()
    out.skipped_optional_step_ids = ["auth_gate"]
    out.ordered_step_ids = ["collect_profile", "submit"]
    result = validate_planner_output(out, _input())
    assert not result.ok
    assert any(v.code in {"skip_required_forbidden", "missing_required_step"} for v in result.violations)


def test_planner_output_is_not_blueprint() -> None:
    out = _valid_output()
    assert out.artifact_type == "journey_plan"
    assert not hasattr(out, "views")
    patch = planning_state_patch_from_output(out)
    assert "blueprint_id" not in patch
    assert patch["plan_artifact_type"] == "journey_plan"
    assert patch["assumptions"][0]["resolved"] is False


def test_frozen_input_rejects_mutation() -> None:
    inp = _input()
    with pytest.raises(Exception):
        inp.skeleton_id = "x"  # type: ignore[attr-defined]
