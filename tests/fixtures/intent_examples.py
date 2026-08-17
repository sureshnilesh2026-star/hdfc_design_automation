"""Shared fixtures for Intent Recognition tests and examples."""

from __future__ import annotations

from uuid import uuid4

from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.contracts.enums import JourneyType, Platform, Priority
from hdfc_journey.contracts.intent import (
    IntentAgentConfig,
    IntentAmbiguity,
    IntentExecutionContext,
    IntentInput,
    IntentProposalOutput,
    IntentUtterance,
    ProposedEntity,
)
from hdfc_journey.contracts.intent_enums import (
    UNKNOWN_INTENT,
    AmbiguityField,
    IntentStatus,
)
from hdfc_journey.contracts.intent_registry import IntentRegistry
from hdfc_journey.contracts.state import (
    JourneyGenerationState,
    NormalizedInput,
    RawInput,
)


def make_intent_input(
    *,
    raw_text: str = "I want to update my address",
    channel_hint: str | None = "asknow",
    modality: str = "text",
    locale: str = "en-IN",
    repair_pass: int = 0,
    registry: IntentRegistry | None = None,
) -> IntentInput:
    """A valid IntentInput for the address-change happy path."""
    return IntentInput(
        utterance=IntentUtterance(
            raw_text=raw_text,
            modality=modality,  # type: ignore[arg-type]
            channel_hint=channel_hint,
            locale=locale,
        ),
        config=IntentAgentConfig(
            intent_prompt_version=INTENT_PROMPT_VERSION,
            registry=registry or IntentRegistry(),
        ),
        execution=IntentExecutionContext(run_id=uuid4(), repair_pass=repair_pass),
    )


def make_clean_proposal(
    *,
    user_intent: str = "UPDATE_ADDRESS",
    confidence: float = 0.88,
    entities: list[ProposedEntity] | None = None,
    journey_type: JourneyType | None = JourneyType.SERVICING,
    product_domain: str | None = "accounts",
    platform_hint: Platform | None = None,
    priority_hint: Priority | None = None,
) -> IntentProposalOutput:
    """An unambiguous, registry-valid proposal that the gate should accept."""
    return IntentProposalOutput(
        intent_status=IntentStatus.PROPOSED,
        proposal_ok=True,
        user_intent=user_intent,
        journey_type=journey_type,
        product_domain=product_domain,
        platform_hint=platform_hint,
        entities=entities
        if entities is not None
        else [
            ProposedEntity(
                type="address_type", value="home", raw_span="home", confidence=0.8
            )
        ],
        confidence=confidence,
        ambiguities=[],
        priority_hint=priority_hint,
        rationale="Utterance names an address update.",
    )


def make_ambiguous_proposal(
    *, field: AmbiguityField = AmbiguityField.USER_INTENT
) -> IntentProposalOutput:
    """A proposal that correctly refuses to guess."""
    return IntentProposalOutput(
        intent_status=IntentStatus.PROPOSED_WITH_AMBIGUITY,
        proposal_ok=True,
        user_intent="BLOCK_CARD",
        journey_type=JourneyType.SERVICING,
        product_domain="cards",
        entities=[],
        confidence=0.55,
        ambiguities=[
            IntentAmbiguity(
                field=field,
                candidates=["BLOCK_CARD", "UPDATE_ADDRESS"],
                note="Utterance could mean either.",
            )
        ],
        rationale="Two readings are equally supported.",
    )


def make_unknown_proposal() -> IntentProposalOutput:
    """A proposal that correctly declines to map the utterance."""
    return IntentProposalOutput(
        intent_status=IntentStatus.UNKNOWN,
        proposal_ok=True,
        user_intent=UNKNOWN_INTENT,
        journey_type=None,
        product_domain=None,
        entities=[],
        confidence=0.2,
        ambiguities=[
            IntentAmbiguity(
                field=AmbiguityField.USER_INTENT,
                candidates=[],
                note="No registry intent matched.",
            )
        ],
        rationale="Utterance does not map to a supported intent.",
    )


def make_state(
    *,
    raw_text: str = "I want to update my address",
    channel_hint: str | None = "asknow",
    modality: str = "text",
    intent_allowlist: list[str] | None = None,
    platform_allowlist: list[str] | None = None,
    confidence_floor: float = 0.7,
) -> JourneyGenerationState:
    """A JourneyGenerationState sealed at intake, ready for the intent stage."""
    state = JourneyGenerationState()
    state.business.input.raw = RawInput(
        modality=modality, text=raw_text, channel_hint=channel_hint
    )
    state.business.input.normalized = NormalizedInput(
        request_id=uuid4(),
        modality=modality,
        raw_text=raw_text,
        channel_hint=channel_hint,
        locale="en-IN",
    )
    state.execution.config_snapshot.intent_allowlist = (
        intent_allowlist
        if intent_allowlist is not None
        else ["APPLY_CREDIT_CARD", "UPDATE_ADDRESS", "BLOCK_CARD", "CHECK_BALANCE"]
    )
    state.execution.config_snapshot.platform_allowlist = (
        platform_allowlist
        if platform_allowlist is not None
        else ["asknow", "eva_dbu", "web", "mobile_native"]
    )
    state.execution.config_snapshot.confidence_floor = confidence_floor
    return state
