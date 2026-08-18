"""Deterministic intent → required platform capabilities map.

This is a temporary bridge until Journey Planner / knowledge retrieval derive
requirements. It must not live inside the Intent agent (propose-only boundary).
"""

from __future__ import annotations

from typing import Mapping, Sequence

# Closed table: adding a registry intent here is a data change, not agent logic.
DEFAULT_INTENT_CAPABILITY_MAP: Mapping[str, tuple[str, ...]] = {
    "APPLY_CREDIT_CARD": (
        "authentication",
        "form_input",
        "document_upload",
        "api_action",
        "otp_verification",
    ),
    "UPDATE_ADDRESS": (
        "authentication",
        "form_input",
        "document_upload",
        "api_action",
    ),
    "BLOCK_CARD": (
        "authentication",
        "otp_verification",
        "api_action",
    ),
    "CHECK_BALANCE": (
        "authentication",
        "api_action",
        "status_tracking",
    ),
}


def required_capabilities_for_intent(
    user_intent: str,
    capability_map: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Return the capability list for an accepted intent id.

    Raises ``KeyError`` when the intent has no mapping — callers must not invent
    requirements.
    """
    table = capability_map or DEFAULT_INTENT_CAPABILITY_MAP
    key = user_intent.strip()
    if key not in table:
        raise KeyError(f"No capability mapping for intent {key!r}")
    return list(table[key])
