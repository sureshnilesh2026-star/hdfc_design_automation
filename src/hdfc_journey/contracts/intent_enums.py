"""Enums owned by the Intent Recognition slice.

Kept in a dedicated module (rather than appended to ``contracts.enums``) so the
Intent slice can land without touching a file the Planner slice also edits.
Shared vocabulary (JourneyType, Platform, Priority) is imported from
``contracts.enums`` and never redefined here.
"""

from __future__ import annotations

from enum import StrEnum

# Reserved sentinel. The proposer MUST emit this rather than guess when it
# cannot map the utterance to an allowlisted intent.
UNKNOWN_INTENT = "UNKNOWN"


class IntentStatus(StrEnum):
    """Status of the *proposal* artifact — never an acceptance verdict."""

    PROPOSED = "proposed"
    PROPOSED_WITH_AMBIGUITY = "proposed_with_ambiguity"
    UNKNOWN = "unknown"
    FAILED = "failed"


class IntentGateVerdict(StrEnum):
    """Deterministic gate outcome. Only the gate may produce these."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class IntentRouteAction(StrEnum):
    CONTINUE = "continue"
    CLARIFY = "clarify"
    ESCALATE = "escalate"


class IntentFailureClass(StrEnum):
    NONE = "none"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS = "ambiguous"
    UNKNOWN_INTENT = "unknown_intent"
    NOT_ALLOWLISTED = "not_allowlisted"
    PLATFORM_UNDERIVABLE = "platform_underivable"
    STRUCTURAL = "structural"
    REPAIR_EXHAUSTED = "repair_exhausted"
    AGENT_FAILED = "agent_failed"


class AmbiguityField(StrEnum):
    """Which slot the proposer could not resolve."""

    USER_INTENT = "user_intent"
    JOURNEY_TYPE = "journey_type"
    PRODUCT_DOMAIN = "product_domain"
    ENTITY = "entity"
    SCOPE = "scope"


class IntentOverrideReason(StrEnum):
    """Why deterministic code overrode a model-proposed value.

    Every override is recorded so the accepted intent is fully explainable.
    """

    PLATFORM_FROM_CHANNEL_HINT = "platform_from_channel_hint"
    JOURNEY_TYPE_FROM_REGISTRY = "journey_type_from_registry"
    PRODUCT_DOMAIN_FROM_REGISTRY = "product_domain_from_registry"
    PRIORITY_FROM_CONFIG = "priority_from_config"
    INTENT_CASE_NORMALIZED = "intent_case_normalized"
    ENTITY_TYPE_NOT_ALLOWED = "entity_type_not_allowed"
    ENTITY_VALUE_SANITIZED = "entity_value_sanitized"
    ENTITY_DEDUPLICATED = "entity_deduplicated"


def normalize_intent_id(raw: str) -> str:
    """Canonicalize an intent id to UPPER_SNAKE.

    Single source of truth, shared by the validator and the gate. Without this,
    the two components can disagree about what "well-formed" means: the
    validator would reject a merely badly-cased id as malformed before the gate
    ever got the chance to normalize it, making normalization dead code.

    Case, surrounding whitespace, hyphens, and internal spaces are treated as
    recoverable formatting. Anything still non-conforming afterwards is a real
    contract violation.
    """
    return raw.strip().upper().replace(" ", "_").replace("-", "_")
