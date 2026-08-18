"""E2E: Intent stage → capability mapper → Platform Capability Agent (shared KB)."""

from __future__ import annotations

from pathlib import Path

from hdfc_journey.agents.intent.agent import IntentRecognitionAgent
from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.config import IntentAgentSettings
from hdfc_journey.contracts.intent_capability_map import required_capabilities_for_intent
from hdfc_journey.llm.deterministic_intent import deterministic_intent_llm_handler
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.capability_check import (
    build_capability_request,
    default_shared_knowledge_dir,
    run_capability_check,
)
from hdfc_journey.orchestrator.intent import run_intent_stage
from tests.fixtures.intent_examples import make_state

SHARED_KB = default_shared_knowledge_dir()


def _make_intent_agent() -> IntentRecognitionAgent:
    return IntentRecognitionAgent(
        llm_client=StubStructuredClient(deterministic_intent_llm_handler),
        settings=IntentAgentSettings(prompt_version=INTENT_PROMPT_VERSION),
    )


def test_shared_kb_companions_exist():
    assert SHARED_KB.is_dir()
    assert (SHARED_KB / "3.1-eva-capabilities.md").is_file()
    assert (SHARED_KB / "3.2-asknow-capabilities.md").is_file()


def test_credit_card_on_eva_intent_to_capability():
    state = make_state(raw_text="I want a credit card", channel_hint="eva")
    state, proposal, gate = run_intent_stage(state, agent=_make_intent_agent())

    assert gate.is_accepted()
    assert gate.accepted_intent is not None
    assert proposal.user_intent == "APPLY_CREDIT_CARD"
    assert gate.accepted_intent.user_intent == "APPLY_CREDIT_CARD"
    assert gate.accepted_intent.platform.value == "eva_dbu"

    caps = required_capabilities_for_intent(gate.accepted_intent.user_intent)
    assert "authentication" in caps
    assert "otp_verification" in caps

    req = build_capability_request(gate.accepted_intent)
    assert req.platform == "eva_dbu"
    assert req.required_capabilities == caps

    result = run_capability_check(gate.accepted_intent, knowledge_dir=SHARED_KB)
    assert result.platform == "eva_dbu"
    assert result.user_intent == "APPLY_CREDIT_CARD"
    assert result.status == "fully_supported"
    assert result.supported is True
    assert result.confidence == 1.0
    assert "3.1-eva-capabilities.md" in result.knowledge_sources


def test_address_change_on_eva_intent_to_capability():
    state = make_state(raw_text="I want to change my address", channel_hint="eva")
    state, _, gate = run_intent_stage(state, agent=_make_intent_agent())
    assert gate.accepted_intent is not None
    assert gate.accepted_intent.user_intent == "UPDATE_ADDRESS"

    result = run_capability_check(gate.accepted_intent, knowledge_dir=SHARED_KB)
    assert result.status == "fully_supported"
    assert result.supported is True


def test_credit_card_on_asknow_resolves_known_platform():
    state = make_state(raw_text="I want a credit card", channel_hint="asknow")
    state, _, gate = run_intent_stage(state, agent=_make_intent_agent())
    assert gate.accepted_intent is not None
    assert gate.accepted_intent.platform.value == "asknow"

    result = run_capability_check(gate.accepted_intent, knowledge_dir=SHARED_KB)
    assert result.platform == "asknow"
    assert result.status == "fully_supported"
    assert "3.2-asknow-capabilities.md" in result.knowledge_sources


def test_eva_alias_input_still_hits_shared_kb():
    """Capability agent aliases EVA → eva_dbu against shared companions."""
    import sys

    agent_root = Path(__file__).resolve().parents[1] / "platform-capability-agent"
    sys.path.insert(0, str(agent_root))
    from agent import CapabilityRequest, PlatformCapabilityAgent  # noqa: WPS433

    agent = PlatformCapabilityAgent(knowledge_dir=str(SHARED_KB))
    resp = agent.evaluate(
        CapabilityRequest(
            platform="EVA",
            required_capabilities=["authentication", "form_input"],
        )
    )
    assert resp.platform == "eva_dbu"
    assert resp.status == "fully_supported"
