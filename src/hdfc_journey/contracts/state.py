"""JourneyGenerationState — canonical workflow state (architecture-aligned).

Planner never mutates this object directly. Orchestrator merges PlannerOutput
into business.planning and appends execution.trace / agents.planner metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from hdfc_journey.contracts.enums import JourneyType, Platform, PlannerStatus, Priority
from hdfc_journey.contracts.knowledge_pack import KnowledgePack
from hdfc_journey.contracts.planner import AcceptedEntity


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Business partition
# ---------------------------------------------------------------------------


class RawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modality: str = "text"
    text: str = ""
    channel_hint: str | None = None
    locale: str = "en-IN"
    received_at: datetime | None = None


class NormalizedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID | None = None
    modality: str = "text"
    raw_text: str = ""
    channel_hint: str | None = None
    locale: str = "en-IN"
    customer_context: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


class BusinessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw: RawInput = Field(default_factory=RawInput)
    normalized: NormalizedInput = Field(default_factory=NormalizedInput)


class IntentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_intent: str | None = None
    journey_type: str | None = None
    platform: str | None = None
    product_domain: str | None = None
    entities: list[AcceptedEntity] = Field(default_factory=list)
    confidence: float | None = None
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    priority_hint: str | None = None
    rationale: str | None = None


class IntentAccepted(BaseModel):
    """Maps to PlannerInput.intent_accepted (immutable after intent gate)."""

    model_config = ConfigDict(extra="forbid")

    user_intent: str
    journey_type: JourneyType
    platform: Platform
    product_domain: str | None = None
    entities: list[AcceptedEntity] = Field(default_factory=list)
    confidence: float = 0.0
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    priority: Priority = Priority.NORMAL
    accepted_by: str = "intent_gate"
    accepted_at: datetime | None = None


class IntentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: IntentProposal | None = None
    accepted: IntentAccepted | None = None


class PlanningAssumptionState(BaseModel):
    """Assumption on state — includes HITL/validator resolution fields."""

    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str
    risk: str
    must_confirm: bool = True
    related_step_ids: list[str] = Field(default_factory=list)
    knowledge_source_ids: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolution: str | None = None


class BusinessPlanning(BaseModel):
    """
    Planning partition.

    Additive vs early architecture sketch: holds full Planner artifact fields
    (entity_bindings, ordered_step_ids, unknown_requirements, …) so the
    PlannerOutput can merge without inventing a parallel state tree.
    """

    model_config = ConfigDict(extra="forbid")

    skeleton_id: str | None = None
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[PlanningAssumptionState] = Field(default_factory=list)
    unknown_requirements: list[dict[str, Any]] = Field(default_factory=list)
    entity_bindings: list[dict[str, Any]] = Field(default_factory=list)
    required_information: list[dict[str, Any]] = Field(default_factory=list)
    ordered_step_ids: list[str] = Field(default_factory=list)
    skipped_optional_step_ids: list[str] = Field(default_factory=list)
    selected_step_ids: list[str] = Field(default_factory=list)
    knowledge_references: list[str] = Field(default_factory=list)
    confidence: dict[str, Any] | None = None
    planner_status: PlannerStatus | None = None
    plan_artifact_type: str | None = None
    plan_schema_version: str | None = None
    error: dict[str, Any] | None = None
    # Deterministic planner-output contract report — NOT business.validation (blueprint).
    contract_validation_report: dict[str, Any] | None = None
    # Router-owned audit: original/repaired outputs, validations, routing decision.
    # Never written by the Planner agent.
    repair_audit: dict[str, Any] | None = None
    router_decision: dict[str, Any] | None = None


class BusinessGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blueprint_draft: dict[str, Any] | None = None
    blueprint_normalized: dict[str, Any] | None = None
    blueprint_final: dict[str, Any] | None = None


class BusinessValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: str = "pending"
    report: dict[str, Any] = Field(default_factory=dict)
    attempt: int = 0
    validated_at: datetime | None = None
    validator_id: str | None = None


class BusinessHitl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = False
    reasons: list[str] = Field(default_factory=list)
    pending_questions: list[dict[str, Any]] = Field(default_factory=list)
    ticket: dict[str, Any] | None = None


class BusinessOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "none"
    blueprint_id: str | None = None
    escalation_id: str | None = None
    completed_at: datetime | None = None


class BusinessError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    stage: str
    source: str
    retriable: bool = False
    at: datetime = Field(default_factory=_utcnow)


BusinessStatus = Literal[
    "received",
    "intent_resolved",
    "knowledge_loaded",
    "planned",
    "generated",
    "validated",
    "escalated",
    "failed",
]


class BusinessState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BusinessStatus = "received"
    input: BusinessInput = Field(default_factory=BusinessInput)
    intent: IntentState = Field(default_factory=IntentState)
    knowledge: KnowledgePack | None = None
    planning: BusinessPlanning = Field(default_factory=BusinessPlanning)
    generation: BusinessGeneration = Field(default_factory=BusinessGeneration)
    validation: BusinessValidation = Field(default_factory=BusinessValidation)
    hitl: BusinessHitl = Field(default_factory=BusinessHitl)
    errors: list[BusinessError] = Field(default_factory=list)
    output: BusinessOutput = Field(default_factory=BusinessOutput)


# ---------------------------------------------------------------------------
# Execution partition
# ---------------------------------------------------------------------------


class StageHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    entered_at: datetime
    exited_at: datetime | None = None
    outcome: str | None = None


class AgentRunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    prompt_version: str | None = None
    latency_ms: float | None = None
    token_usage: dict[str, int | None] = Field(
        default_factory=lambda: {"input": None, "output": None}
    )
    structured_output_ok: bool | None = None
    repair_pass: int = 0


class DecisionEvent(BaseModel):
    """Append-only execution trace event."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    at: datetime = Field(default_factory=_utcnow)
    stage: str
    actor: Literal["llm", "code", "human"]
    component: str
    decision: str
    evidence_refs: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class ExecutionGates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_gate: str = "not_run"
    knowledge_gate: str = "not_run"
    validation_gate: str = "not_run"


class ConfigSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent_allowlist: list[str] = Field(default_factory=list)
    platform_allowlist: list[str] = Field(default_factory=list)
    confidence_floor: float = 0.7
    max_planner_repairs: int = 1
    planner_prompt_version: str = "planner-system-v1"
    llm_model: str | None = None


class AgentsMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: AgentRunMetadata = Field(default_factory=AgentRunMetadata)
    planner: AgentRunMetadata = Field(default_factory=AgentRunMetadata)


class ExecutionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    orchestrator_version: str = "0.1.0"
    current_stage: str = "input"
    stage_history: list[StageHistoryEntry] = Field(default_factory=list)
    agents: AgentsMetadata = Field(default_factory=AgentsMetadata)
    tools_invoked: list[dict[str, Any]] = Field(default_factory=list)
    gates: ExecutionGates = Field(default_factory=ExecutionGates)
    config_snapshot: ConfigSnapshot = Field(default_factory=ConfigSnapshot)
    trace: list[DecisionEvent] = Field(default_factory=list)


class JourneyGenerationState(BaseModel):
    """Top-level workflow state document."""

    model_config = ConfigDict(extra="forbid")

    state_id: UUID = Field(default_factory=uuid4)
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    business: BusinessState = Field(default_factory=BusinessState)
    execution: ExecutionState = Field(default_factory=ExecutionState)

    def touch(self) -> None:
        self.updated_at = _utcnow()
