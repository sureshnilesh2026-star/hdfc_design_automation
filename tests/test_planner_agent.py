"""Journey Planner Agent tests — mock LLM only (no network)."""

from __future__ import annotations

import pytest

from hdfc_journey.agents.planner.agent import JourneyPlannerAgent, create_planner_agent
from hdfc_journey.agents.planner.errors import PlannerBoundaryError
from hdfc_journey.agents.planner.prompts import JOURNEY_PLANNER_SYSTEM_PROMPT
from hdfc_journey.config import PlannerAgentSettings
from hdfc_journey.contracts.enums import AttributionKind, PlannerStatus
from hdfc_journey.contracts.planner import DecisionAttribution, PlannerOutput
from hdfc_journey.contracts.validation import validate_planner_output
from hdfc_journey.llm.openai_client import LLMInvocationError
from hdfc_journey.llm.stub_client import StubStructuredClient
from tests.fixtures.planner_examples import (
    example_planner_input,
    example_planner_output,
)


def test_plan_returns_typed_output_from_structured_llm() -> None:
    expected = example_planner_output()

    def handler(system: str, user: str, model: type) -> PlannerOutput:
        assert model is PlannerOutput
        assert "Journey Planner Agent" in system or "constrained planning" in system
        assert "APPLY_CREDIT_CARD" in user
        assert "JOURNEY-CC-APPLY-STUB" in user
        return expected

    agent = JourneyPlannerAgent(
        llm_client=StubStructuredClient(handler),
        settings=PlannerAgentSettings(enforce_contract_validation=True),
    )
    out = agent.plan(example_planner_input())
    assert isinstance(out, PlannerOutput)
    assert out.planner_ok is True
    assert out.artifact_type == "journey_plan"
    assert out.ordered_step_ids == ["auth_gate", "collect_profile", "submit"]
    assert "FAKE" not in out.knowledge_references


def test_propose_returns_invalid_plan_for_router() -> None:
    """propose must not fail-close — Router needs the invalid artifact."""
    bad = example_planner_output().model_copy(deep=True)
    bad.decisions[0].knowledge_source_ids = ["INVENTED-DOC"]
    bad.decisions[0].attributions = [
        DecisionAttribution(kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="INVENTED-DOC")
    ]
    bad.knowledge_references = list(bad.knowledge_references) + ["INVENTED-DOC"]

    agent = JourneyPlannerAgent(
        llm_client=StubStructuredClient(lambda *_: bad),
        settings=PlannerAgentSettings(enforce_contract_validation=True),
    )
    out = agent.propose(example_planner_input())
    assert out.planner_ok is True
    assert "INVENTED-DOC" in out.knowledge_references
    assert agent.last_validation_report is not None
    assert agent.last_validation_report.overall_passed is False


def test_plan_rejects_invented_knowledge_refs_via_contract_check() -> None:
    bad = example_planner_output().model_copy(deep=True)
    bad.decisions[0].knowledge_source_ids = ["INVENTED-DOC"]
    bad.decisions[0].attributions = [
        DecisionAttribution(kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="INVENTED-DOC")
    ]
    bad.knowledge_references = list(bad.knowledge_references) + ["INVENTED-DOC"]

    agent = JourneyPlannerAgent(
        llm_client=StubStructuredClient(lambda *_: bad),
        settings=PlannerAgentSettings(enforce_contract_validation=True),
    )
    out = agent.plan(example_planner_input())
    assert out.planner_ok is False
    assert out.planner_status == PlannerStatus.FAILED
    assert out.error is not None
    assert out.error.code == "contract_violation"


def test_llm_failure_returns_failed_output() -> None:
    class BoomClient:
        def complete_structured(self, **kwargs):
            raise LLMInvocationError("provider down")

    agent = JourneyPlannerAgent(llm_client=BoomClient())  # type: ignore[arg-type]
    out = agent.plan(example_planner_input())
    assert out.planner_ok is False
    assert out.error is not None
    assert out.error.code == "llm_failure"
    assert out.error.retriable is True


def test_boundary_methods_are_blocked() -> None:
    agent = JourneyPlannerAgent(
        llm_client=StubStructuredClient(lambda *_: example_planner_output())
    )
    with pytest.raises(PlannerBoundaryError):
        agent.merge_into_state({})
    with pytest.raises(PlannerBoundaryError):
        agent.retrieve("x")
    with pytest.raises(PlannerBoundaryError):
        agent.search_knowledge("x")
    with pytest.raises(PlannerBoundaryError):
        agent.validate_journey({})
    with pytest.raises(PlannerBoundaryError):
        agent.route("next")


def test_create_planner_agent_requires_client_for_stub_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HDFC_LLM_PROVIDER", "stub")
    from hdfc_journey.config import get_planner_settings

    get_planner_settings.cache_clear()
    with pytest.raises(PlannerBoundaryError):
        create_planner_agent()
    get_planner_settings.cache_clear()


def test_example_output_valid_against_example_input() -> None:
    result = validate_planner_output(example_planner_output(), example_planner_input())
    assert result.ok, result.violations


def test_system_prompt_loaded() -> None:
    assert "Do not invent APIs" in JOURNEY_PLANNER_SYSTEM_PROMPT
    assert "journey_plan" in JOURNEY_PLANNER_SYSTEM_PROMPT
