#!/usr/bin/env python3
"""
Live demo for the Platform Capability Agent.

Walks a viewer through seven realistic HDFC journey questions, in order of
increasing difficulty, calling the real agent against the real sample
knowledge base for each one — nothing here is scripted output, every verdict
below is computed live by `agent/capability_agent.py`.

    python3 demo.py            paced for a live audience (~35s total)
    python3 demo.py --fast     no pauses, for a quick sanity check
    python3 demo.py --no-color plain text, e.g. when piping to a log/OBS text source
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import PlatformCapabilityAgent, CapabilityRequest, SupportStatus  # noqa: E402

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, RED, YELLOW, MAGENTA, BLUE, CYAN = (
    "\033[32m", "\033[31m", "\033[33m", "\033[35m", "\033[34m", "\033[36m",
)

STATUS_LABEL = {
    SupportStatus.FULLY_SUPPORTED.value: "FULLY SUPPORTED",
    SupportStatus.PARTIALLY_SUPPORTED.value: "PARTIALLY SUPPORTED",
    SupportStatus.NOT_SUPPORTED.value: "NOT SUPPORTED",
    SupportStatus.UNKNOWN_PLATFORM.value: "UNKNOWN PLATFORM",
    SupportStatus.PLATFORM_PENDING_APPROVAL.value: "PENDING APPROVAL",
    SupportStatus.INSUFFICIENT_KNOWLEDGE.value: "INSUFFICIENT KNOWLEDGE",
}
STATUS_COLOR = {
    SupportStatus.FULLY_SUPPORTED.value: GREEN,
    SupportStatus.PARTIALLY_SUPPORTED.value: YELLOW,
    SupportStatus.NOT_SUPPORTED.value: RED,
    SupportStatus.UNKNOWN_PLATFORM.value: MAGENTA,
    SupportStatus.PLATFORM_PENDING_APPROVAL.value: BLUE,
    SupportStatus.INSUFFICIENT_KNOWLEDGE.value: YELLOW,
}

SCENARIOS = [
    {
        "title": "Address-change journey on EVA",
        "ask": "Product wants customers to update their registered address through "
               "EVA. Can we build it?",
        "platform": "EVA",
        "requirements": ["authentication", "form_input", "document_upload", "api_action"],
    },
    {
        "title": "Same journey, now with a live selfie-with-ID step",
        "ask": "Compliance wants a live camera capture of the ID instead of a "
               "scanned upload. Does EVA support that?",
        "platform": "EVA",
        "requirements": ["authentication", "form_input", "document_upload",
                          "api_action", "native_camera_capture"],
    },
    {
        "title": "The same journey, over phone banking",
        "ask": "Can the identical address-update journey run over the IVR "
               "channel instead?",
        "platform": "IVR",
        "requirements": ["form_input", "document_upload", "native_camera_capture"],
    },
    {
        "title": "A brand-new channel nobody has documented yet",
        "ask": "Growth wants to launch this on a WhatsApp bot next quarter. "
               "Is that ready to check?",
        "platform": "WHATSAPP_BOT",
        "requirements": ["authentication", "form_input"],
    },
    {
        "title": "A requirement nobody has written knowledge for yet",
        "ask": "Compliance is now asking for biometric liveness verification "
               "on EVA. Do we actually know if that's possible?",
        "platform": "EVA",
        "requirements": ["authentication", "biometric_liveness_check"],
    },
    {
        "title": "Legacy Portal — two knowledge documents disagree",
        "ask": "Can customers still upload documents through the old "
               "self-service portal?",
        "platform": "LEGACY_PORTAL",
        "requirements": ["document_upload", "authentication"],
    },
    {
        "title": "The next-gen portal, still in design review",
        "ask": "Marketing wants to preview the address-change journey on the "
               "new portal before it ships.",
        "platform": "NEW_PORTAL",
        "requirements": ["form_input", "document_upload"],
    },
]


def c(text: str, color: str, use_color: bool) -> str:
    return f"{color}{text}{RESET}" if use_color else text


def pace(seconds: float, fast: bool) -> None:
    if not fast:
        time.sleep(seconds)


def rule(use_color: bool, char: str = "-", width: int = 72) -> str:
    return c(char * width, DIM, use_color)


def print_intro(use_color: bool, fast: bool) -> None:
    print(rule(use_color, "="))
    print(c("  PLATFORM CAPABILITY AGENT — LIVE DEMO", BOLD, use_color))
    print(c('  Answers one question: "Can this journey be implemented on this platform?"',
             DIM, use_color))
    print(rule(use_color, "="))
    print()
    pace(0.8, fast)
    print("  Every verdict below is computed live, by comparing requested")
    print("  capabilities against a real markdown knowledge base — the agent")
    print("  never asks an LLM to guess what a platform supports.")
    print()
    pace(1.2, fast)


def print_scenario(agent: PlatformCapabilityAgent, n: int, total: int,
                    scenario: dict, use_color: bool, fast: bool):
    print(rule(use_color))
    print(c(f"SCENARIO {n} of {total} — {scenario['title']}", BOLD + CYAN, use_color))
    print(rule(use_color))
    print(f'  "{scenario["ask"]}"')
    print()
    pace(0.6, fast)

    print(f"  {c('platform:', DIM, use_color)}     {scenario['platform']}")
    print(f"  {c('requirements:', DIM, use_color)}  {', '.join(scenario['requirements'])}")
    print()
    pace(0.5, fast)
    print(c("  -> retrieving knowledge, comparing against requirements...", DIM, use_color))
    pace(0.9, fast)

    resp = agent.evaluate(CapabilityRequest(
        platform=scenario["platform"], required_capabilities=scenario["requirements"],
    ))

    status_color = STATUS_COLOR.get(resp.status, RESET)
    label = STATUS_LABEL.get(resp.status, resp.status.upper())
    print()
    print(f"  {c('VERDICT:', BOLD, use_color)} "
          f"{c(label, BOLD + status_color, use_color)}  "
          f"{c(f'(confidence {resp.confidence:.2f})', DIM, use_color)}")

    if resp.supported_capabilities:
        print(f"    {c('[SUPPORTED]', GREEN, use_color)}     "
              f"{', '.join(resp.supported_capabilities)}")
    if resp.unsupported_capabilities:
        print(f"    {c('[UNSUPPORTED]', RED, use_color)}   "
              f"{', '.join(resp.unsupported_capabilities)}")
    if resp.capabilities_needing_investigation:
        print(f"    {c('[NEEDS INVESTIGATION]', YELLOW, use_color)} "
              f"{', '.join(resp.capabilities_needing_investigation)}")
    if resp.conflicts:
        for conflict in resp.conflicts:
            print(f"    {c('[CONFLICT]', MAGENTA, use_color)}  "
                  f"'{conflict.capability}' — supported in {conflict.supported_in}, "
                  f"unsupported in {conflict.unsupported_in}")
            if conflict.higher_authority_source:
                print(f"                 likely current: {conflict.higher_authority_source}")
    if resp.constraints:
        print(f"    {c('constraints:', DIM, use_color)}")
        for constraint in resp.constraints:
            print(f"      - {constraint}")
    if resp.knowledge_sources:
        print(f"    {c('sources:', DIM, use_color)} {', '.join(resp.knowledge_sources)}")
    print()
    pace(1.4, fast)
    return resp


def print_summary(results: list, use_color: bool) -> None:
    print(rule(use_color, "="))
    print(c("  SUMMARY", BOLD, use_color))
    print(rule(use_color, "="))
    for scenario, resp in results:
        label = STATUS_LABEL.get(resp.status, resp.status.upper())
        color_ = STATUS_COLOR.get(resp.status, RESET)
        platform_col = c(f"{scenario['platform']:<14}", DIM, use_color)
        label_col = c(f"{label:<24}", color_, use_color)
        print(f"  {platform_col} {label_col} {scenario['title']}")
    print(rule(use_color, "="))


def main() -> None:
    parser = argparse.ArgumentParser(description="Live demo of the Platform Capability Agent")
    parser.add_argument("--fast", action="store_true", help="Skip pacing delays")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    args = parser.parse_args()

    use_color = sys.stdout.isatty() and not args.no_color

    knowledge_dir = str(Path(__file__).resolve().parent / "knowledge")
    agent = PlatformCapabilityAgent(knowledge_dir=knowledge_dir)

    print_intro(use_color, args.fast)

    results = []
    for i, scenario in enumerate(SCENARIOS, start=1):
        resp = print_scenario(agent, i, len(SCENARIOS), scenario, use_color, args.fast)
        results.append((scenario, resp))

    print_summary(results, use_color)


if __name__ == "__main__":
    main()
