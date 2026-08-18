"""Capability-check stage — bridges AcceptedIntent to Platform Capability Agent.

Owns orchestration only: map intent → requirements, call the capability agent,
return a structured verdict. Does not interpret utterances or plan journeys.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hdfc_journey.contracts.intent_capability_map import (
    DEFAULT_INTENT_CAPABILITY_MAP,
    required_capabilities_for_intent,
)
from hdfc_journey.contracts.planner import AcceptedIntent


class CapabilityCheckError(RuntimeError):
    """Raised when the capability stage cannot run (missing map, agent, or KB)."""


def _repo_root() -> Path:
    # src/hdfc_journey/orchestrator/capability_check.py → repo root
    return Path(__file__).resolve().parents[3]


def _ensure_capability_agent_on_path() -> Path:
    """Make ``platform-capability-agent`` importable without a package install."""
    agent_root = _repo_root() / "platform-capability-agent"
    if not agent_root.is_dir():
        raise CapabilityCheckError(
            f"platform-capability-agent not found at {agent_root}"
        )
    root_str = str(agent_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return agent_root


def default_shared_knowledge_dir() -> Path:
    """Level-3 directory holding ``*-capabilities.md`` companions."""
    return _repo_root() / "Knowledge_Base" / "Level 3 - Platform Knowledge"


@dataclass(frozen=True)
class CapabilityCheckResult:
    """Thin wrapper so hdfc_journey callers need not import AgentResponse."""

    platform: str
    status: str
    supported: bool
    requested_capabilities: list[str]
    supported_capabilities: list[str]
    unsupported_capabilities: list[str]
    capabilities_needing_investigation: list[str]
    confidence: float
    reasoning: list[str]
    knowledge_sources: list[str]
    user_intent: str
    raw: dict[str, Any]


def build_capability_request(accepted_intent: AcceptedIntent) -> Any:
    """Map AcceptedIntent → CapabilityRequest (platform + required_capabilities)."""
    _ensure_capability_agent_on_path()
    from agent.schema import CapabilityRequest  # noqa: WPS433

    caps = required_capabilities_for_intent(accepted_intent.user_intent)
    return CapabilityRequest(
        platform=accepted_intent.platform.value,
        required_capabilities=caps,
    )


def run_capability_check(
    accepted_intent: AcceptedIntent,
    *,
    knowledge_dir: str | Path | None = None,
    capability_map: dict[str, tuple[str, ...]] | None = None,
) -> CapabilityCheckResult:
    """Evaluate whether the accepted intent's platform can support the journey."""
    if accepted_intent is None:
        raise CapabilityCheckError("accepted_intent is required")

    _ensure_capability_agent_on_path()
    from agent import PlatformCapabilityAgent  # noqa: WPS433
    from agent.schema import CapabilityRequest  # noqa: WPS433

    kb = Path(knowledge_dir) if knowledge_dir else default_shared_knowledge_dir()
    if not kb.is_dir():
        raise CapabilityCheckError(f"Knowledge directory not found: {kb}")

    caps = required_capabilities_for_intent(
        accepted_intent.user_intent,
        capability_map=capability_map or DEFAULT_INTENT_CAPABILITY_MAP,
    )
    request = CapabilityRequest(
        platform=accepted_intent.platform.value,
        required_capabilities=caps,
    )
    agent = PlatformCapabilityAgent(knowledge_dir=str(kb))
    resp = agent.evaluate(request)
    return CapabilityCheckResult(
        platform=resp.platform,
        status=resp.status,
        supported=resp.supported,
        requested_capabilities=list(resp.requested_capabilities),
        supported_capabilities=list(resp.supported_capabilities),
        unsupported_capabilities=list(resp.unsupported_capabilities),
        capabilities_needing_investigation=list(
            resp.capabilities_needing_investigation
        ),
        confidence=resp.confidence,
        reasoning=list(resp.reasoning),
        knowledge_sources=list(resp.knowledge_sources),
        user_intent=accepted_intent.user_intent,
        raw=resp.to_dict(),
    )
