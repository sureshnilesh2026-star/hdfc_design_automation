"""Shared fixtures for Planner tests and examples."""

from __future__ import annotations

from uuid import UUID, uuid4

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
    KnowledgeExcerpt,
    KnowledgePack,
    KnowledgeReference,
    MissingKnowledge,
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

EXAMPLE_RUN_ID = UUID("11111111-1111-1111-1111-111111111111")


def example_knowledge_pack() -> KnowledgePack:
    return KnowledgePack(
        pack_id="APPLY_CREDIT_CARD|asknow|v1",
        registry_version="test-registry-1",
        references=[
            KnowledgeReference(asset_id="PROD-CC-001", level=2, status="loaded"),
            KnowledgeReference(asset_id="PLT-ASK-001", level=3, status="loaded"),
            KnowledgeReference(
                asset_id="JOURNEY-CC-APPLY-STUB", level=4, status="stub"
            ),
        ],
        excerpts=[
            KnowledgeExcerpt(
                chunk_id="PLT-ASK-001#auth",
                document_id="PLT-ASK-001",
                section_path=["Authentication"],
                text="Protected activities require authentication before execution.",
                relevance=0.95,
            ),
            KnowledgeExcerpt(
                chunk_id="JOURNEY-CC-APPLY-STUB#steps",
                document_id="JOURNEY-CC-APPLY-STUB",
                section_path=["Steps"],
                text="Skeleton steps: auth_gate, collect_profile, optional_upsell, submit.",
                relevance=0.99,
            ),
        ],
        missing_knowledge=[
            MissingKnowledge(
                asset_id="TECH-CC-APPLY-APIS",
                level=5,
                reason="required_but_absent",
                blocking=True,
            )
        ],
        attribution_index=AttributionIndex(
            by_document=["PROD-CC-001", "PLT-ASK-001", "JOURNEY-CC-APPLY-STUB"],
            by_chunk=["PLT-ASK-001#auth", "JOURNEY-CC-APPLY-STUB#steps"],
        ),
    )


def example_skeleton() -> JourneySkeleton:
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
                suggested_field_ids=["product_interest", "full_name"],
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
                name="Submit application",
                ordinal=3,
                optional=False,
            ),
        ],
    )


def example_planner_input(*, run_id: UUID | None = None) -> PlannerInput:
    return PlannerInput(
        intent_accepted=AcceptedIntent(
            user_intent="APPLY_CREDIT_CARD",
            journey_type=JourneyType.ACQUISITION,
            platform=Platform.ASKNOW,
            product_domain="credit_cards",
            entities=[
                AcceptedEntity(type="product", value="credit_card", confidence=0.92)
            ],
            confidence=0.88,
            ambiguities=[],
            priority="normal",
        ),
        knowledge_pack=example_knowledge_pack(),
        skeleton=example_skeleton(),
        config=PlannerConfig(planner_prompt_version="planner-system-v1"),
        execution=PlannerExecutionContext(
            run_id=run_id or EXAMPLE_RUN_ID,
            current_stage="planning",
            repair_pass=0,
        ),
    )


def example_planner_output() -> PlannerOutput:
    """Canonical successful plan matching example_planner_input()."""
    return PlannerOutput(
        planner_status=PlannerStatus.PLANNED_WITH_UNKNOWNS,
        planner_ok=True,
        skeleton_id="JOURNEY-CC-APPLY-STUB",
        ordered_step_ids=["auth_gate", "collect_profile", "submit"],
        skipped_optional_step_ids=["optional_upsell"],
        selected_step_ids=["auth_gate", "collect_profile", "submit"],
        decisions=[
            PlanningDecision(
                id="d_auth",
                kind=DecisionKind.REQUIRE_AUTH,
                subject="auth_gate",
                rationale="Protected apply actions require authentication",
                related_step_ids=["auth_gate", "submit"],
                knowledge_source_ids=["PLT-ASK-001"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="PLT-ASK-001"
                    ),
                    DecisionAttribution(
                        kind=AttributionKind.SKELETON_STEP, ref="auth_gate"
                    ),
                ],
            ),
            PlanningDecision(
                id="d_use_collect",
                kind=DecisionKind.USE_SKELETON_STEP,
                subject="collect_profile",
                rationale="Collect required applicant profile data from skeleton",
                related_step_ids=["collect_profile"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                        ref="JOURNEY-CC-APPLY-STUB",
                    )
                ],
            ),
            PlanningDecision(
                id="d_skip_upsell",
                kind=DecisionKind.SKIP_OPTIONAL,
                subject="optional_upsell",
                rationale="Optional upsell not required for core apply path",
                related_step_ids=["optional_upsell"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                        ref="JOURNEY-CC-APPLY-STUB",
                    )
                ],
            ),
            PlanningDecision(
                id="d_bind_product",
                kind=DecisionKind.BIND_ENTITY,
                subject="product:credit_card",
                rationale="Bind accepted product entity to collect_profile",
                related_step_ids=["collect_profile"],
                knowledge_source_ids=["PROD-CC-001"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.INPUT_ENTITY, ref="product:credit_card"
                    ),
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="PROD-CC-001"
                    ),
                ],
            ),
            PlanningDecision(
                id="d_unknown_api",
                kind=DecisionKind.MARK_UNKNOWN_REQUIREMENT,
                subject="TECH-CC-APPLY-APIS",
                rationale="Level 5 API bindings missing from KnowledgePack",
                related_step_ids=["submit"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                        ref="JOURNEY-CC-APPLY-STUB",
                    )
                ],
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
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="PROD-CC-001"
                    ),
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
                data_type_hint="string",
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                        ref="JOURNEY-CC-APPLY-STUB",
                    ),
                    DecisionAttribution(
                        kind=AttributionKind.SKELETON_STEP, ref="collect_profile"
                    ),
                ],
            )
        ],
        assumptions=[
            PlanningAssumption(
                id="A1",
                statement="Submit API contract is unknown until Level 5 knowledge is added",
                risk=AssumptionRisk.HIGH,
                must_confirm=True,
                related_step_ids=["submit"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
            )
        ],
        unknown_requirements=[
            UnknownRequirement(
                id="U_TECH-CC-APPLY-APIS",
                kind=UnknownRequirementKind.API,
                description="TECH-CC-APPLY-APIS application submit API binding not present in KnowledgePack",
                blocking_hint=True,
                related_step_ids=["submit"],
                knowledge_source_ids=["JOURNEY-CC-APPLY-STUB"],
            )
        ],
        knowledge_references=["PLT-ASK-001", "PROD-CC-001", "JOURNEY-CC-APPLY-STUB"],
        confidence=PlanningConfidence(
            overall=0.78,
            per_step={"auth_gate": 0.9, "collect_profile": 0.85, "submit": 0.55},
            notes="Submit confidence lowered due to missing Level 5 API knowledge",
        ),
        error=None,
    )


def random_run_input() -> PlannerInput:
    return example_planner_input(run_id=uuid4())
