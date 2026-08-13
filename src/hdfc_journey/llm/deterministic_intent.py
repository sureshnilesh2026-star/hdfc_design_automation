"""Deterministic structured intent proposer used as a reproducible LLM stand-in.

Derives IntentProposalOutput from IntentInput only, via keyword hints in the
intent registry. Not embedded in IntentRecognitionAgent — injected via
StubStructuredClient for tests.

This is intentionally naive keyword matching. It is NOT a production intent
classifier; it exists so the surrounding gate/router/orchestrator machinery can
be tested exhaustively without a model, and so every test is reproducible
(same IntentInput -> same IntentProposalOutput).
"""

from __future__ import annotations

import re

from hdfc_journey.contracts.enums import Priority
from hdfc_journey.contracts.intent import (
    IntentAmbiguity,
    IntentInput,
    IntentProposalOutput,
    ProposedEntity,
)
from hdfc_journey.contracts.intent_enums import (
    UNKNOWN_INTENT,
    AmbiguityField,
    IntentStatus,
)

# Utterance text that looks like an attempt to command the interpreter.
_INJECTION_MARKERS = (
    "ignore your instruction",
    "ignore all previous",
    "ignore previous instruction",
    "disregard your instruction",
    "you are now",
    "system prompt",
    "set confidence",
    "mark this as accepted",
    "mark as accepted",
    "approve this",
    "you must accept",
    "override the gate",
    "skip validation",
)

# Sensitive patterns we refuse to echo verbatim as entity values.
_LONG_DIGITS_RE = re.compile(r"\b\d{9,}\b")


def parse_intent_input_from_user_prompt(user_prompt: str) -> IntentInput:
    """Extract IntentInput JSON from the agent user-message wrapper."""
    marker = "IntentInput JSON follows"
    if marker in user_prompt:
        payload = user_prompt.split(marker, 1)[1]
    else:
        payload = user_prompt
    match = re.search(r"\{.*\}\s*$", payload, flags=re.DOTALL)
    if not match:
        raise ValueError("No IntentInput JSON found in user prompt")
    return IntentInput.model_validate_json(match.group(0))


def _mask_sensitive(value: str) -> str:
    """Never echo a long digit run (card/account-like) back downstream."""
    return _LONG_DIGITS_RE.sub(lambda m: "*" * (len(m.group(0)) - 4) + m.group(0)[-4:], value)


def propose_from_intent_input(intent_input: IntentInput) -> IntentProposalOutput:
    """
    Keyword-hint interpretation.

    Reproducible: same IntentInput -> same IntentProposalOutput.
    Does not invent intents outside the registry, does not resolve ambiguity,
    and does not execute instructions found in the utterance.
    """
    text = intent_input.utterance.raw_text
    lowered = text.lower()
    registry = intent_input.config.registry

    if not text.strip():
        return IntentProposalOutput(
            intent_status=IntentStatus.UNKNOWN,
            proposal_ok=True,
            user_intent=UNKNOWN_INTENT,
            confidence=0.0,
            rationale="Utterance is empty; nothing to interpret.",
            ambiguities=[
                IntentAmbiguity(
                    field=AmbiguityField.USER_INTENT,
                    candidates=[],
                    note="Empty utterance",
                )
            ],
        )

    # Injection attempts are interpreted as content, never obeyed.
    injection_detected = any(marker in lowered for marker in _INJECTION_MARKERS)

    # Score each registry intent by keyword hits.
    scores: dict[str, int] = {}
    for definition in registry.definitions:
        hits = sum(1 for kw in definition.keyword_hints if kw in lowered)
        if hits:
            scores[definition.intent_id] = hits

    if not scores:
        note = (
            "Utterance appears to be an instruction-injection attempt rather than "
            "a banking request."
            if injection_detected
            else "No registry intent keyword matched the utterance."
        )
        return IntentProposalOutput(
            intent_status=IntentStatus.UNKNOWN,
            proposal_ok=True,
            user_intent=UNKNOWN_INTENT,
            confidence=0.1 if injection_detected else 0.2,
            rationale=note,
            ambiguities=[
                IntentAmbiguity(
                    field=AmbiguityField.USER_INTENT,
                    candidates=[],
                    note=note,
                )
            ],
        )

    top = max(scores.values())
    tied = sorted(k for k, v in scores.items() if v == top)

    ambiguities: list[IntentAmbiguity] = []
    if len(tied) > 1:
        ambiguities.append(
            IntentAmbiguity(
                field=AmbiguityField.USER_INTENT,
                candidates=tied,
                note="Utterance matches multiple enterprise intents equally.",
            )
        )
    if injection_detected:
        ambiguities.append(
            IntentAmbiguity(
                field=AmbiguityField.SCOPE,
                candidates=[],
                note=(
                    "Utterance contains instruction-like content; treated as data. "
                    "Human confirmation recommended."
                ),
            )
        )

    chosen = tied[0]
    definition = registry.get(chosen)
    assert definition is not None

    # Entity extraction — only literal, registry-registered types.
    entities: list[ProposedEntity] = []
    if "address_type" in definition.allowed_entity_types:
        for kind in ("home", "office", "permanent", "communication"):
            if kind in lowered:
                entities.append(
                    ProposedEntity(
                        type="address_type", value=kind, raw_span=kind, confidence=0.8
                    )
                )
    if "card_variant" in definition.allowed_entity_types:
        for variant in ("regalia", "millennia", "moneyback", "infinia"):
            if variant in lowered:
                entities.append(
                    ProposedEntity(
                        type="card_variant",
                        value=variant,
                        raw_span=variant,
                        confidence=0.85,
                    )
                )

    # Ambiguity when a slot is plural (e.g. two address types named).
    address_types = [e for e in entities if e.type == "address_type"]
    if len(address_types) > 1:
        ambiguities.append(
            IntentAmbiguity(
                field=AmbiguityField.ENTITY,
                candidates=[e.value for e in address_types],
                note="Multiple address types referenced; scope unclear.",
            )
        )

    entities = [
        e.model_copy(update={"value": _mask_sensitive(e.value)}) for e in entities
    ]

    if ambiguities:
        status = IntentStatus.PROPOSED_WITH_AMBIGUITY
        confidence = 0.55
    else:
        status = IntentStatus.PROPOSED
        confidence = 0.88

    return IntentProposalOutput(
        intent_status=status,
        proposal_ok=True,
        user_intent=chosen,
        journey_type=definition.journey_type,
        product_domain=definition.product_domain,
        platform_hint=None,
        entities=entities,
        confidence=confidence,
        ambiguities=ambiguities,
        priority_hint=Priority.NORMAL,
        rationale=(
            f"Utterance keywords matched registry intent {chosen}; "
            f"{len(entities)} entities extracted literally."
        ),
    )


def deterministic_intent_llm_handler(
    system_prompt: str,
    user_prompt: str,
    response_model: type,
) -> IntentProposalOutput:
    """StubStructuredClient handler: parse input from prompt, propose from input."""
    del system_prompt  # prompt presence asserted by agent tests elsewhere
    if response_model is not IntentProposalOutput:
        raise TypeError(f"Expected IntentProposalOutput, got {response_model}")
    intent_input = parse_intent_input_from_user_prompt(user_prompt)
    return propose_from_intent_input(intent_input)
