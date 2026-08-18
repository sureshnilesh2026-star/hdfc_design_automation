"""Intent Recognition Agent — formal input/output contracts.

The Intent agent produces a *proposal* artifact only. It must never emit an
accepted intent, a routing directive, an escalation, or a Journey Blueprint.
Acceptance is performed exclusively by the deterministic intent gate.

Contract split (the core discipline of this slice):

    IntentProposalOutput   <- LLM may write this        (a hypothesis)
    AcceptedIntent         <- ONLY the gate may write   (a decision)

``AcceptedIntent`` is deliberately NOT redefined here — it is imported from
``contracts.planner`` so the Planner consumes this slice's output with zero glue.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hdfc_journey.contracts.enums import JourneyType, Platform, Priority
from hdfc_journey.contracts.intent_enums import (
    AmbiguityField,
    IntentGateVerdict,
    IntentOverrideReason,
    IntentStatus,
)
from hdfc_journey.contracts.intent_registry import IntentRegistry

# Re-exported so downstream code has one obvious import site for the handoff.
from hdfc_journey.contracts.planner import AcceptedEntity, AcceptedIntent  # noqa: F401

INTENT_CONTRACT_VERSION = "1.0.0"

# Hard ceilings. Defence-in-depth against a model that pads output, and against
# an utterance crafted to blow up downstream payload sizes.
MAX_ENTITIES = 20
MAX_AMBIGUITIES = 10
MAX_ENTITY_VALUE_CHARS = 256
MAX_RATIONALE_CHARS = 500


# ---------------------------------------------------------------------------
# Agent INPUT
# ---------------------------------------------------------------------------


class IntentUtterance(BaseModel):
    """The normalized user input. Treated strictly as DATA, never instructions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_text: str = Field(..., min_length=1)
    modality: Literal["text", "voice"] = "text"
    # channel_hint is the ONLY authoritative source of platform. The model does
    # not get to choose the platform; see IntentGate.
    channel_hint: str | None = None
    locale: str = "en-IN"
    customer_context: dict[str, Any] = Field(default_factory=dict)


class IntentAgentConfig(BaseModel):
    """Orchestrator-supplied configuration. Immutable for the agent call."""

    model_config = ConfigDict(extra="forbid")

    intent_prompt_version: str = Field(..., min_length=1)
    registry: IntentRegistry = Field(default_factory=IntentRegistry)
    max_entities: int = Field(default=MAX_ENTITIES, ge=0, le=100)
    max_ambiguities: int = Field(default=MAX_AMBIGUITIES, ge=0, le=50)
    # Supplied to the model as vocabulary only; the gate re-enforces it.
    expose_vocabulary_to_model: bool = True


class IntentExecutionContext(BaseModel):
    """Tracing metadata only — maps to JourneyGenerationState.execution."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    state_id: UUID | None = None
    current_stage: Literal["intent"] = "intent"
    orchestrator_version: str | None = None
    repair_pass: int = Field(default=0, ge=0)


class IntentClarificationContext(BaseModel):
    """Optional second-pass context after a clarify round.

    Carries the question asked and the human's answer. Never carries a
    suggested intent — the model must re-derive it.
    """

    model_config = ConfigDict(extra="forbid")

    question_asked: str | None = None
    human_answer: str | None = None
    prior_ambiguity_fields: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class IntentInput(BaseModel):
    """Strongly typed Intent agent input, built by the orchestrator from state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.0"] = INTENT_CONTRACT_VERSION
    utterance: IntentUtterance
    config: IntentAgentConfig
    execution: IntentExecutionContext
    clarification_context: IntentClarificationContext | None = None


# ---------------------------------------------------------------------------
# Agent OUTPUT (proposal only)
# ---------------------------------------------------------------------------


class ProposedEntity(BaseModel):
    """An entity the model believes it saw. Unverified until the gate filters it."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1, max_length=MAX_ENTITY_VALUE_CHARS)
    raw_span: str | None = Field(default=None, max_length=MAX_ENTITY_VALUE_CHARS)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class IntentAmbiguity(BaseModel):
    """An explicitly declared unresolved slot.

    Emitting one of these is a SUCCESS, not a failure. It is how the agent
    refuses to guess. The gate treats a non-empty ambiguity list as a hard
    blocker on acceptance.
    """

    model_config = ConfigDict(extra="forbid")

    field: AmbiguityField
    candidates: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=300)


class IntentError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "llm_failure",
        "schema_invalid",
        "contract_violation",
        "empty_utterance",
        "unsupported_modality",
    ]
    message: str
    retriable: bool = False


class IntentProposalOutput(BaseModel):
    """The ONLY artifact the Intent agent may produce.

    Note what is absent by design: no ``accepted`` flag, no ``priority``, no
    routing directive, no escalation request. Those are not the model's to make.
    ``platform`` is present only as a non-authoritative hint.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = INTENT_CONTRACT_VERSION
    artifact_type: Literal["intent_proposal"] = "intent_proposal"

    intent_status: IntentStatus
    proposal_ok: bool

    # Candidate slots. May be UNKNOWN / None when the model cannot resolve them.
    user_intent: str | None = Field(default=None, max_length=64)
    journey_type: JourneyType | None = None
    product_domain: str | None = Field(default=None, max_length=64)
    # Non-authoritative. The gate derives the real platform from channel_hint.
    platform_hint: Platform | None = None

    entities: list[ProposedEntity] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguities: list[IntentAmbiguity] = Field(default_factory=list)
    # A hint only — the gate sets real priority from config.
    priority_hint: Priority | None = None
    rationale: str = Field(default="", max_length=MAX_RATIONALE_CHARS)

    error: IntentError | None = None

    @field_validator("user_intent")
    @classmethod
    def _no_whitespace_intent(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


# ---------------------------------------------------------------------------
# Gate output (deterministic code only)
# ---------------------------------------------------------------------------


class IntentOverride(BaseModel):
    """Record of the gate overriding or dropping a model-proposed value."""

    model_config = ConfigDict(extra="forbid")

    field: str
    reason: IntentOverrideReason
    model_value: str | None = None
    accepted_value: str | None = None


class IntentGateResult(BaseModel):
    """Verdict of the deterministic intent gate.

    ``accepted_intent`` is populated if and only if ``verdict == ACCEPTED``.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: IntentGateVerdict
    gate_id: Literal["intent_gate_deterministic_v1"] = "intent_gate_deterministic_v1"
    evaluated_at: datetime | None = None

    accepted_intent: AcceptedIntent | None = None

    # Machine-readable reasons; drive routing and HITL messaging.
    reason_codes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    overrides: list[IntentOverride] = Field(default_factory=list)
    dropped_entity_types: list[str] = Field(default_factory=list)
    unresolved_ambiguity_fields: list[str] = Field(default_factory=list)

    # Recorded for audit; explicitly NOT the primary acceptance criterion.
    confidence_floor_applied: float | None = None
    model_confidence: float | None = None

    def is_accepted(self) -> bool:
        return self.verdict == IntentGateVerdict.ACCEPTED
