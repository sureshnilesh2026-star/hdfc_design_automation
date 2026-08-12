"""
Input/output data contracts for the Platform Capability Agent.

Keeping these as plain dataclasses (rather than passing dicts around) means the
shape of a request/response is enforced by the type checker and is easy for another
engineer to read in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional


class SupportStatus(str, Enum):
    FULLY_SUPPORTED = "fully_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    NOT_SUPPORTED = "not_supported"
    UNKNOWN_PLATFORM = "unknown_platform"
    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"
    # A knowledge document exists for this platform but hasn't cleared
    # governance (status != approved) — distinct from UNKNOWN_PLATFORM
    # ("no documentation exists at all") so a caller can route the two
    # cases differently (e.g. "onboard this platform" vs. "chase down the
    # pending approval") without parsing free-text `reasoning`.
    PLATFORM_PENDING_APPROVAL = "platform_pending_approval"


@dataclass
class CapabilityRequest:
    """What the caller (journey planner, or a human) is asking the agent."""

    platform: str
    required_capabilities: List[str]


@dataclass
class Conflict:
    capability: str
    supported_in: List[str]
    unsupported_in: List[str]
    # Informational only — the higher authority_rank source, if the two sides
    # differ. Never used to auto-resolve the conflict; a human still decides.
    higher_authority_source: Optional[str] = None


@dataclass
class KnowledgeSourceRef:
    """A structured pointer to one knowledge document, per the metadata contract."""
    document_id: str
    source_file: str
    authority_rank: Optional[int] = None
    status: str = "approved"


@dataclass
class AgentResponse:
    platform: str
    status: str
    supported: bool
    requested_capabilities: List[str]
    supported_capabilities: List[str]
    unsupported_capabilities: List[str]
    capabilities_needing_investigation: List[str]
    conflicts: List[Conflict]
    constraints: List[str]
    knowledge_sources: List[str]
    confidence: float
    reasoning: List[str]
    knowledge_source_documents: List[KnowledgeSourceRef] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # asdict() turns Conflict/KnowledgeSourceRef dataclasses into dicts automatically.
        return d
