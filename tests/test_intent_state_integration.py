"""Intent stage ↔ JourneyGenerationState integration tests.

These pin the write-permission model: the agent's proposal may land in
``business.intent.proposal`` and nowhere else, and only the gate may write
``business.intent.accepted``.
"""

from __future__ import annotations

import pytest

from hdfc_journey.agents.intent.agent import IntentRecognitionAgent
from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.config import IntentAgentSettings
from hdfc_journey.contracts.intent_state_mapping import (
    AGENT_WRITABLE_STATE_PATHS,
    GATE_ONLY_STATE_PATHS,
    intent_accepted_state_patch,
)
from hdfc_journey.llm.deterministic_intent import deterministic_intent_llm_handler
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.intent import (
    IntentStageError,
    build_intent_input_from_state,
    run_intent_stage,
)
from hdfc_journey.orchestrator.intent_gate import evaluate_intent_gate
from tests.fixtures.intent_examples import make_intent_input, make_state


def make_agent() -> IntentRecognitionAgent:
    return IntentRecognitionAgent(
        llm_client=StubStructuredClient(deterministic_intent_llm_handler),
        settings=IntentAgentSettings(prompt_version=INTENT_PROMPT_VERSION),
    )


class TestBuildInput:
    def test_projects_normalized_input(self):
        state = make_state(raw_text="I want to change my address")
        intent_input = build_intent_input_from_state(state)
        assert intent_input.utterance.raw_text == "I want to change my address"
        assert intent_input.utterance.channel_hint == "asknow"
        assert intent_input.execution.run_id == state.execution.run_id

    def test_build_does_not_mutate_state(self):
        state = make_state()
        before = state.model_dump_json()
        build_intent_input_from_state(state)
        assert state.model_dump_json() == before

    def test_missing_text_raises(self):
        state = make_state()
        state.business.input.normalized.raw_text = "   "
        with pytest.raises(IntentStageError):
            build_intent_input_from_state(state)

    def test_unsupported_modality_raises(self):
        state = make_state()
        state.business.input.normalized.modality = "telepathy"
        with pytest.raises(IntentStageError):
            build_intent_input_from_state(state)


class TestAcceptedPath:
    def test_accepted_intent_written_and_status_advanced(self):
        state = make_state(raw_text="I want to change my address")
        state, output, gate = run_intent_stage(state, agent=make_agent())

        assert gate.is_accepted()
        assert state.business.intent.accepted is not None
        assert state.business.intent.accepted.user_intent == "UPDATE_ADDRESS"
        assert state.business.status == "intent_resolved"
        assert state.execution.gates.intent_gate == "passed"

    def test_proposal_also_recorded(self):
        """Both the hypothesis and the decision are auditable."""
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        assert state.business.intent.proposal is not None
        assert state.business.intent.proposal.user_intent == "UPDATE_ADDRESS"

    def test_downstream_sections_untouched(self):
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        assert state.business.knowledge is None
        assert state.business.planning.skeleton_id is None
        assert state.business.generation.blueprint_final is None
        assert state.business.validation.result == "pending"
        assert state.business.hitl.required is False

    def test_input_remains_sealed(self):
        state = make_state(raw_text="I want to change my address")
        before = state.business.input.model_dump_json()
        state, _, _ = run_intent_stage(state, agent=make_agent())
        assert state.business.input.model_dump_json() == before


class TestRejectedPath:
    def test_unknown_utterance_escalates_without_accepting(self):
        state = make_state(raw_text="tell me a joke about bananas")
        state, output, gate = run_intent_stage(state, agent=make_agent())

        assert not gate.is_accepted()
        assert state.business.intent.accepted is None
        assert state.business.status == "escalated"
        assert state.execution.gates.intent_gate == "failed"
        assert state.business.hitl.required is True
        assert state.business.output.kind == "escalation"

    def test_hitl_carries_actionable_questions(self):
        state = make_state(raw_text="tell me a joke about bananas")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        assert state.business.hitl.pending_questions
        assert state.business.hitl.reasons

    def test_clarify_is_attempted_once_then_escalates(self):
        """One clarification round, then a human. No infinite loop."""
        state = make_state(raw_text="tell me a joke about bananas")
        state, _, _ = run_intent_stage(state, agent=make_agent())

        route_events = [
            e
            for e in state.execution.trace
            if e.component == "orchestrator.intent_router"
            and e.decision.startswith("route_eval_")
        ]
        assert len(route_events) == 2  # initial + one clarify attempt
        assert state.business.status == "escalated"

    def test_underivable_platform_escalates(self):
        state = make_state(raw_text="I want to change my address", channel_hint=None)
        state, _, gate = run_intent_stage(state, agent=make_agent())
        assert not gate.is_accepted()
        assert state.business.intent.accepted is None


class TestObservability:
    def test_trace_records_agent_gate_and_router(self):
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        components = {e.component for e in state.execution.trace}
        assert "intent_recognition_agent" in components
        assert "orchestrator.intent_gate" in components
        assert "orchestrator.intent_router" in components

    def test_gate_event_records_overrides(self):
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        gate_events = [
            e for e in state.execution.trace if e.component == "orchestrator.intent_gate"
        ]
        assert gate_events
        assert "overrides" in gate_events[0].detail

    def test_stage_history_opened_and_closed(self):
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        entries = [e for e in state.execution.stage_history if e.stage == "intent"]
        assert entries
        assert entries[-1].exited_at is not None
        assert entries[-1].outcome == "success"

    def test_agent_metadata_recorded(self):
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        meta = state.execution.agents.intent
        assert meta.prompt_version == INTENT_PROMPT_VERSION
        assert meta.latency_ms is not None
        assert meta.structured_output_ok is True

    def test_trace_never_claims_acceptance_from_the_agent(self):
        state = make_state(raw_text="I want to change my address")
        state, _, _ = run_intent_stage(state, agent=make_agent())
        agent_events = [
            e
            for e in state.execution.trace
            if e.component == "intent_recognition_agent"
        ]
        for e in agent_events:
            assert e.detail["grants_acceptance"] is False


class TestWritePermissions:
    def test_agent_writable_paths_are_proposal_only(self):
        assert AGENT_WRITABLE_STATE_PATHS == {"business.intent.proposal"}

    def test_accepted_is_gate_only(self):
        assert "business.intent.accepted" in GATE_ONLY_STATE_PATHS
        assert "business.intent.accepted" not in AGENT_WRITABLE_STATE_PATHS

    def test_accepted_patch_refuses_rejected_result(self):
        """There is no such thing as a partially accepted intent."""
        from tests.fixtures.intent_examples import make_ambiguous_proposal

        intent_input = make_intent_input()
        gate = evaluate_intent_gate(
            output=make_ambiguous_proposal(),
            intent_input=intent_input,
            report=None,
        )
        with pytest.raises(ValueError):
            intent_accepted_state_patch(gate)
