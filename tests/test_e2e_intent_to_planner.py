"""End-to-end: Intent Recognition → intent gate → Journey Planner.

This is the integration test that matters. It proves the Intent slice's output
is consumable by the existing Planner slice with **zero glue code**: the same
``AcceptedIntent`` object the gate produces is what ``PlannerInput`` requires.

If someone later changes the intent contract in a way that breaks the Planner
handoff, this test fails loudly rather than at runtime in a later stage.
"""

from __future__ import annotations

from hdfc_journey.agents.intent.agent import IntentRecognitionAgent
from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.agents.planner.agent import JourneyPlannerAgent
from hdfc_journey.config import IntentAgentSettings, PlannerAgentSettings
from hdfc_journey.contracts.enums import JourneyType, Platform
from hdfc_journey.contracts.intent_registry import (
    IntentDefinition,
    IntentRegistry,
)
from hdfc_journey.contracts.planner import AcceptedIntent, PlannerInput
from hdfc_journey.llm.deterministic_intent import deterministic_intent_llm_handler
from hdfc_journey.llm.deterministic_planner import deterministic_planner_llm_handler
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.intent import run_intent_stage
from hdfc_journey.orchestrator.planning import (
    build_planner_input_from_state,
    run_planning_stage,
)
from tests.fixtures.address_change import (
    address_change_knowledge_pack,
    address_change_skeleton,
)
from tests.fixtures.intent_examples import make_state

# The Planner fixtures target the AskNow address-update journey, so the intent
# registry used here is scoped to exactly that.
ADDRESS_REGISTRY = IntentRegistry(
    definitions=(
        IntentDefinition(
            intent_id="UPDATE_ADDRESS",
            journey_type=JourneyType.SERVICING,
            product_domain="accounts",
            description="Customer wants to update a registered address.",
            allowed_entity_types=("address_type", "address_line", "city", "pincode"),
            keyword_hints=("change address", "change my address", "update address"),
        ),
    )
)


def make_intent_agent() -> IntentRecognitionAgent:
    return IntentRecognitionAgent(
        llm_client=StubStructuredClient(deterministic_intent_llm_handler),
        settings=IntentAgentSettings(prompt_version=INTENT_PROMPT_VERSION),
    )


def make_planner_agent() -> JourneyPlannerAgent:
    return JourneyPlannerAgent(
        llm_client=StubStructuredClient(deterministic_planner_llm_handler),
        settings=PlannerAgentSettings(),
    )


def run_intent_then_prepare_planning():
    """Run the intent stage, then wire the state for the planning stage."""
    state = make_state(
        raw_text="I want to change my address",
        channel_hint="asknow",
        intent_allowlist=["UPDATE_ADDRESS"],
        platform_allowlist=["asknow"],
    )
    state, output, gate = run_intent_stage(
        state, agent=make_intent_agent(), registry=ADDRESS_REGISTRY
    )

    # Knowledge retrieval and skeleton selection are other slices' work; here
    # they are supplied from the Planner slice's own fixtures.
    state.business.knowledge = address_change_knowledge_pack()
    skeleton = address_change_skeleton()
    state.business.planning.skeleton_id = skeleton.skeleton_id
    return state, output, gate, skeleton


class TestHandoffContract:
    def test_gate_emits_the_planner_input_type(self):
        _, _, gate, _ = run_intent_then_prepare_planning()
        assert isinstance(gate.accepted_intent, AcceptedIntent)

    def test_accepted_intent_satisfies_planner_input_without_glue(self):
        """The exact object the gate produced is accepted by PlannerInput."""
        state, _, gate, skeleton = run_intent_then_prepare_planning()

        planner_input = PlannerInput(
            intent_accepted=gate.accepted_intent,
            knowledge_pack=state.business.knowledge,
            skeleton=skeleton,
            config=build_planner_input_from_state(state, skeleton).config,
            execution=build_planner_input_from_state(state, skeleton).execution,
        )
        assert planner_input.intent_accepted.user_intent == "UPDATE_ADDRESS"
        assert planner_input.intent_accepted.platform == Platform.ASKNOW

    def test_state_projection_matches_gate_output(self):
        """What the gate decided is what the Planner reads off the state."""
        state, _, gate, skeleton = run_intent_then_prepare_planning()
        planner_input = build_planner_input_from_state(state, skeleton)

        assert planner_input.intent_accepted.user_intent == gate.accepted_intent.user_intent
        assert planner_input.intent_accepted.platform == gate.accepted_intent.platform
        assert (
            planner_input.intent_accepted.journey_type
            == gate.accepted_intent.journey_type
        )

    def test_planner_cross_check_passes(self):
        """PlannerInput cross-validates skeleton.intent against accepted intent.

        This is the assertion that would fail if the intent registry drifted
        away from the enterprise's real journey ids.
        """
        state, _, _, skeleton = run_intent_then_prepare_planning()
        planner_input = build_planner_input_from_state(state, skeleton)
        assert planner_input.skeleton.intent == planner_input.intent_accepted.user_intent


class TestFullPipeline:
    def test_utterance_to_plan(self):
        """Raw sentence in, structured journey plan out."""
        state, _, gate, skeleton = run_intent_then_prepare_planning()
        assert gate.is_accepted()

        state, planner_output = run_planning_stage(
            state, agent=make_planner_agent(), skeleton=skeleton
        )
        assert planner_output.skeleton_id == skeleton.skeleton_id
        assert planner_output.ordered_step_ids

    def test_trace_spans_both_stages(self):
        state, _, _, skeleton = run_intent_then_prepare_planning()
        state, _ = run_planning_stage(
            state, agent=make_planner_agent(), skeleton=skeleton
        )
        stages = {e.stage for e in state.execution.trace}
        assert {"intent", "planning"} <= stages

        components = {e.component for e in state.execution.trace}
        assert "intent_recognition_agent" in components
        assert "orchestrator.intent_gate" in components
        assert "journey_planner_agent" in components

    def test_planning_never_runs_on_rejected_intent(self):
        """The gate is a real barrier: no acceptance, no accepted intent to plan from."""
        from hdfc_journey.orchestrator.planning import PlanningStageError

        state = make_state(
            raw_text="tell me a joke about bananas",
            intent_allowlist=["UPDATE_ADDRESS"],
        )
        state, _, gate = run_intent_stage(
            state, agent=make_intent_agent(), registry=ADDRESS_REGISTRY
        )
        assert not gate.is_accepted()
        assert state.business.intent.accepted is None

        state.business.knowledge = address_change_knowledge_pack()
        skeleton = address_change_skeleton()
        state.business.planning.skeleton_id = skeleton.skeleton_id

        try:
            build_planner_input_from_state(state, skeleton)
            raise AssertionError("Planner input must not build without accepted intent")
        except PlanningStageError:
            pass

    def test_intent_stage_leaves_planning_untouched(self):
        state = make_state(
            raw_text="I want to change my address", intent_allowlist=["UPDATE_ADDRESS"]
        )
        planning_before = state.business.planning.model_dump(mode="json")
        state, _, _ = run_intent_stage(
            state, agent=make_intent_agent(), registry=ADDRESS_REGISTRY
        )
        assert state.business.planning.model_dump(mode="json") == planning_before
