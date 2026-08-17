"""Controlled UPDATE_ADDRESS / AskNow fixtures for E2E Planner tests."""

from __future__ import annotations

from uuid import UUID

from hdfc_journey.contracts.enums import JourneyType, Platform, SkeletonStepType
from hdfc_journey.contracts.knowledge_pack import (
    AttributionIndex,
    KnowledgeExcerpt,
    KnowledgePack,
    KnowledgeReference,
    MissingKnowledge,
)
from hdfc_journey.contracts.planner import AcceptedEntity
from hdfc_journey.contracts.skeleton import JourneySkeleton, SkeletonStep
from hdfc_journey.contracts.state import (
    BusinessInput,
    ConfigSnapshot,
    IntentAccepted,
    IntentState,
    JourneyGenerationState,
    NormalizedInput,
    RawInput,
)

ADDRESS_CHANGE_RUN_ID = UUID("22222222-2222-2222-2222-222222222222")
ADDRESS_CHANGE_STATE_ID = UUID("33333333-3333-3333-3333-333333333333")
USER_UTTERANCE = "I want to change my address."


def address_change_knowledge_pack() -> KnowledgePack:
    """Small pack: enough to plan, intentionally incomplete (no Level 5 APIs)."""
    return KnowledgePack(
        pack_id="UPDATE_ADDRESS|asknow|v1",
        registry_version="test-registry-address-1",
        references=[
            KnowledgeReference(
                asset_id="ENT-PROFILE-001",
                level=1,
                sections=["Customer profile servicing"],
                status="loaded",
            ),
            KnowledgeReference(
                asset_id="PLT-ASK-001",
                level=3,
                sections=["Authentication", "Journey Layer"],
                status="loaded",
            ),
            KnowledgeReference(
                asset_id="JOURNEY-ADDR-UPDATE-STUB",
                level=4,
                sections=["Steps", "Required information"],
                status="stub",
            ),
        ],
        excerpts=[
            KnowledgeExcerpt(
                chunk_id="PLT-ASK-001#auth",
                document_id="PLT-ASK-001",
                section_path=["Authentication"],
                text=(
                    "Protected servicing activities on AskNow require authentication "
                    "before profile changes are accepted."
                ),
                relevance=0.94,
            ),
            KnowledgeExcerpt(
                chunk_id="JOURNEY-ADDR-UPDATE-STUB#steps",
                document_id="JOURNEY-ADDR-UPDATE-STUB",
                section_path=["Steps"],
                text=(
                    "Address change journey skeleton: authenticate, confirm customer, "
                    "capture new address, review, submit. Optional communication preference "
                    "step may be skipped."
                ),
                relevance=0.99,
            ),
            KnowledgeExcerpt(
                chunk_id="ENT-PROFILE-001#addr",
                document_id="ENT-PROFILE-001",
                section_path=["Customer profile servicing"],
                text=(
                    "Customers may request updates to communication or residential address "
                    "through approved digital servicing journeys."
                ),
                relevance=0.9,
            ),
        ],
        missing_knowledge=[
            MissingKnowledge(
                asset_id="TECH-ADDR-UPDATE-APIS",
                level=5,
                reason="required_but_absent",
                blocking=True,
            )
        ],
        attribution_index=AttributionIndex(
            by_document=[
                "ENT-PROFILE-001",
                "PLT-ASK-001",
                "JOURNEY-ADDR-UPDATE-STUB",
            ],
            by_chunk=[
                "PLT-ASK-001#auth",
                "JOURNEY-ADDR-UPDATE-STUB#steps",
                "ENT-PROFILE-001#addr",
            ],
        ),
        retrieval_policy="journey > product > platform > enterprise",
    )


def address_change_skeleton() -> JourneySkeleton:
    return JourneySkeleton(
        skeleton_id="JOURNEY-ADDR-UPDATE-STUB",
        journey_id="JN-ADDR-UPDATE",
        intent="UPDATE_ADDRESS",
        platform="asknow",
        journey_type="servicing",
        product_domain="customer_profile",
        version="1.0.0",
        steps=[
            SkeletonStep(
                id="auth_gate",
                type=SkeletonStepType.AUTH_GATE,
                name="Authenticate customer",
                ordinal=0,
                optional=False,
                description="Verify customer before profile mutation",
                allowed_knowledge_source_ids=["PLT-ASK-001", "JOURNEY-ADDR-UPDATE-STUB"],
            ),
            SkeletonStep(
                id="confirm_customer",
                type=SkeletonStepType.INTERACTION,
                name="Confirm customer context",
                ordinal=1,
                optional=False,
                required_entity_types=["customer_id"],
                suggested_field_ids=["customer_id"],
            ),
            SkeletonStep(
                id="capture_new_address",
                type=SkeletonStepType.INTERACTION,
                name="Capture new address",
                ordinal=2,
                optional=False,
                required_entity_types=["address_type"],
                suggested_field_ids=[
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "address_type",
                ],
            ),
            SkeletonStep(
                id="optional_comm_pref",
                type=SkeletonStepType.INTERACTION,
                name="Update communication preferences",
                ordinal=3,
                optional=True,
                suggested_field_ids=["preferred_channel"],
            ),
            SkeletonStep(
                id="review_and_submit",
                type=SkeletonStepType.TERMINAL,
                name="Review and submit address change",
                ordinal=4,
                optional=False,
                suggested_field_ids=["confirmation_ack"],
            ),
        ],
    )


def address_change_state() -> JourneyGenerationState:
    skeleton = address_change_skeleton()
    state = JourneyGenerationState(
        state_id=ADDRESS_CHANGE_STATE_ID,
    )
    state.execution.run_id = ADDRESS_CHANGE_RUN_ID
    state.execution.orchestrator_version = "0.1.0"
    state.execution.config_snapshot = ConfigSnapshot(
        intent_allowlist=["UPDATE_ADDRESS"],
        platform_allowlist=["asknow"],
        confidence_floor=0.7,
        max_planner_repairs=1,
        planner_prompt_version="planner-system-v1",
        llm_model="deterministic-planner-v1",
    )
    state.business.status = "knowledge_loaded"
    state.business.input = BusinessInput(
        raw=RawInput(
            modality="text",
            text=USER_UTTERANCE,
            channel_hint="asknow",
            locale="en-IN",
        ),
        normalized=NormalizedInput(
            request_id=ADDRESS_CHANGE_RUN_ID,
            modality="text",
            raw_text=USER_UTTERANCE,
            channel_hint="asknow",
            locale="en-IN",
            customer_context={"auth_state": "unknown", "segment_hint": "ETB"},
        ),
    )
    state.business.intent = IntentState(
        accepted=IntentAccepted(
            user_intent="UPDATE_ADDRESS",
            journey_type=JourneyType.SERVICING,
            platform=Platform.ASKNOW,
            product_domain="customer_profile",
            entities=[
                AcceptedEntity(
                    type="customer_id",
                    value="CUST-88991",
                    raw_span=None,
                    confidence=0.91,
                ),
                AcceptedEntity(
                    type="address_type",
                    value="residential",
                    raw_span="address",
                    confidence=0.8,
                ),
            ],
            confidence=0.9,
            ambiguities=[],
            priority="normal",
            accepted_by="intent_gate",
        )
    )
    state.business.knowledge = address_change_knowledge_pack()
    state.business.planning.skeleton_id = skeleton.skeleton_id
    state.execution.gates.intent_gate = "passed"
    state.execution.gates.knowledge_gate = "passed"
    return state
