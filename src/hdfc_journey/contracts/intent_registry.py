"""Intent registry — deterministic configuration, not model reasoning.

Adding a new supported intent is a *data* change here (plus knowledge/skeleton
assets downstream). It must never require editing the agent, the prompt, or the
gate. This is the Intent-slice analogue of "a new Markdown document expands
capability without a new agent implementation".

The registry is the authority for:
- which intents are allowlisted at all
- the ``journey_type`` each intent belongs to
- the ``product_domain`` each intent belongs to
- which entity types are meaningful for that intent

The model may *propose* journey_type / product_domain; the gate overwrites them
from this table whenever the table has an entry. Model agreement is recorded,
model disagreement is overridden and traced — never silently trusted.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from hdfc_journey.contracts.enums import JourneyType


class IntentDefinition(BaseModel):
    """One allowlisted enterprise intent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_id: str = Field(..., min_length=1)
    journey_type: JourneyType
    product_domain: str | None = None
    description: str = ""
    # Entity types the gate will retain for this intent. Anything else the model
    # emits is dropped (recorded as an override) rather than passed downstream.
    allowed_entity_types: tuple[str, ...] = ()
    # Utterance-level hints, used ONLY by the deterministic stand-in planner in
    # tests. The production path uses the LLM; these keep tests reproducible.
    keyword_hints: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Default registry — the v1 vertical slice
# ---------------------------------------------------------------------------

DEFAULT_INTENT_DEFINITIONS: tuple[IntentDefinition, ...] = (
    IntentDefinition(
        intent_id="APPLY_CREDIT_CARD",
        journey_type=JourneyType.ACQUISITION,
        product_domain="credit_cards",
        description="Customer wants to apply for a new credit card.",
        allowed_entity_types=("card_variant", "employment_type", "income_band", "city"),
        keyword_hints=("apply", "new credit card", "get a credit card", "want a card"),
    ),
    IntentDefinition(
        intent_id="UPDATE_ADDRESS",
        journey_type=JourneyType.SERVICING,
        product_domain="accounts",
        description="Customer wants to update a registered address.",
        allowed_entity_types=("address_type", "address_line", "city", "pincode"),
        keyword_hints=(
            "change address",
            "change my address",
            "update address",
            "update my address",
            "new address",
        ),
    ),
    IntentDefinition(
        intent_id="BLOCK_CARD",
        journey_type=JourneyType.SERVICING,
        product_domain="cards",
        description="Customer wants to block or freeze a card.",
        allowed_entity_types=("card_variant", "card_last4", "reason"),
        keyword_hints=("block", "freeze", "stolen", "lost card"),
    ),
    IntentDefinition(
        intent_id="CHECK_BALANCE",
        journey_type=JourneyType.INFORMATION,
        product_domain="accounts",
        description="Customer wants to view an account balance.",
        allowed_entity_types=("account_type", "account_last4"),
        keyword_hints=("balance", "how much money", "available funds"),
    ),
)


class IntentRegistry(BaseModel):
    """Lookup surface over the intent definitions."""

    model_config = ConfigDict(extra="forbid")

    definitions: tuple[IntentDefinition, ...] = DEFAULT_INTENT_DEFINITIONS

    def get(self, intent_id: str) -> IntentDefinition | None:
        for d in self.definitions:
            if d.intent_id == intent_id:
                return d
        return None

    def intent_ids(self) -> list[str]:
        return [d.intent_id for d in self.definitions]

    def allowed_entity_types(self, intent_id: str) -> tuple[str, ...]:
        d = self.get(intent_id)
        return d.allowed_entity_types if d else ()

    def vocabulary_for_prompt(self) -> str:
        """Render the closed intent vocabulary for the system prompt.

        This is supplied as *vocabulary*, not as authority: the gate re-checks
        membership regardless of what the model emits.
        """
        lines = []
        for d in self.definitions:
            product = d.product_domain or "-"
            lines.append(
                f"- {d.intent_id} (journey_type={d.journey_type.value}, "
                f"product_domain={product}): {d.description}"
            )
        return "\n".join(lines)


def default_registry() -> IntentRegistry:
    return IntentRegistry()
