"""Demo: Intent Recognition → capability map → Platform Capability Agent.

    PYTHONPATH=src:. python examples/run_intent_capability_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

from hdfc_journey.agents.intent.agent import IntentRecognitionAgent
from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.config import IntentAgentSettings
from hdfc_journey.llm.deterministic_intent import deterministic_intent_llm_handler
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.capability_check import run_capability_check
from hdfc_journey.orchestrator.intent import run_intent_stage
from tests.fixtures.intent_examples import make_state

OUT_DIR = Path(__file__).parent / "intent_capability_demo"

SCENARIOS = [
    ("credit_card_eva", "I want a credit card", "eva"),
    ("credit_card_asknow", "I want a credit card", "asknow"),
    ("address_change_eva", "I want to change my address", "eva"),
]


def make_agent() -> IntentRecognitionAgent:
    return IntentRecognitionAgent(
        llm_client=StubStructuredClient(deterministic_intent_llm_handler),
        settings=IntentAgentSettings(prompt_version=INTENT_PROMPT_VERSION),
    )


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    agent = make_agent()
    summary = []

    for name, utterance, channel in SCENARIOS:
        state = make_state(raw_text=utterance, channel_hint=channel)
        state, proposal, gate = run_intent_stage(state, agent=agent)

        print("=" * 72)
        print(name)
        print(f"  utterance      : {utterance!r}")
        print(f"  channel        : {channel!r}")
        print(f"  proposed intent: {proposal.user_intent}")
        print(f"  GATE VERDICT   : {gate.verdict.value.upper()}")

        row: dict = {
            "scenario": name,
            "utterance": utterance,
            "channel_hint": channel,
            "gate_verdict": gate.verdict.value,
            "accepted_intent": None,
            "accepted_platform": None,
            "capability_status": None,
            "capability_supported": None,
        }

        if gate.accepted_intent is None:
            print("  (stopped before capability check)")
            for reason in gate.reasons:
                print(f"    - {reason}")
        else:
            ai = gate.accepted_intent
            print(f"  accepted       : {ai.user_intent} @ {ai.platform.value}")
            result = run_capability_check(ai)
            print(
                f"  CAPABILITY     : {result.status.upper()} "
                f"(supported={result.supported}, confidence={result.confidence})"
            )
            print(f"  requested      : {', '.join(result.requested_capabilities)}")
            print(f"  sources        : {', '.join(result.knowledge_sources)}")
            row.update(
                {
                    "accepted_intent": ai.user_intent,
                    "accepted_platform": ai.platform.value,
                    "capability_status": result.status,
                    "capability_supported": result.supported,
                    "confidence": result.confidence,
                    "knowledge_sources": result.knowledge_sources,
                }
            )
            (OUT_DIR / f"{name}_capability.json").write_text(
                json.dumps(result.raw, indent=2)
            )

        summary.append(row)

    (OUT_DIR / "demo_summary.json").write_text(json.dumps(summary, indent=2))
    print("=" * 72)
    print(f"Artifacts written to {OUT_DIR}")


if __name__ == "__main__":
    main()
