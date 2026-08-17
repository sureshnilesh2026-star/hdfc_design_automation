"""Journey Planner Agent — formal input/output contracts.

The Planner produces a planning artifact only. It must never emit a JourneyBlueprint.
Outputs merge into JourneyGenerationState.business.planning via the orchestrator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hdfc_journey.contracts.enums import (
    AssumptionRisk,
    AttributionKind,
    DecisionKind,
    JourneyType,
    Platform,
    PlannerStatus,
    Priority,
    RequiredInfoSource,
    UnknownRequirementKind,
)
from hdfc_journey.contracts.knowledge_pack import KnowledgePack
from hdfc_journey.contracts.skeleton import JourneySkeleton

PLANNER_CONTRACT_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Accepted intent (maps from state.business.intent.accepted)
# ---------------------------------------------------------------------------


class AcceptedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    raw_span: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AcceptedIntent(BaseModel):
    """Immutable snapshot of intent.accepted for this Planner invocation."""

    model_config = ConfigDict(extra="forbid")

    user_intent: str = Field(..., min_length=1)
    journey_type: JourneyType
    platform: Platform
    product_domain: str | None = None
    entities: list[AcceptedEntity] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    ambiguities: list[dict[str, Any]] = Field(default_factory=list)
    priority: Priority = Priority.NORMAL
    accepted_by: str | None = "intent_gate"
    accepted_at: datetime | None = None


# ---------------------------------------------------------------------------
# Config + execution context
# ---------------------------------------------------------------------------


class PlannerConfig(BaseModel):
    """Orchestrator-supplied configuration. Immutable for the Planner call."""

    model_config = ConfigDict(extra="forbid")

    planner_prompt_version: str = Field(..., min_length=1)
    decision_kinds_allowlist: list[DecisionKind] = Field(
        default_factory=lambda: list(DecisionKind)
    )
    max_assumptions: int = Field(default=20, ge=0, le=100)
    max_unknown_requirements: int = Field(default=20, ge=0, le=100)
    require_citation_on_decisions: bool = True
    allow_skip_only_optional_steps: bool = True


class ReplanContext(BaseModel):
    """Optional soft-fail replan payload from Decision/Router — no new retrieval."""

    model_config = ConfigDict(extra="forbid")

    validation_errors: list[str] = Field(default_factory=list)
    prior_decision_ids: list[str] = Field(default_factory=list)


class PlannerExecutionContext(BaseModel):
    """Tracing metadata only — maps to JourneyGenerationState.execution."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    state_id: UUID | None = None
    current_stage: Literal["planning"] = "planning"
    orchestrator_version: str | None = None
    repair_pass: int = Field(default=0, ge=0)
    parent_trace_event_id: str | None = None


# ---------------------------------------------------------------------------
# Planner INPUT
# ---------------------------------------------------------------------------


class PlannerInput(BaseModel):
    """
    Strongly typed Planner input.

    Built by the orchestrator from JourneyGenerationState.
    All fields are immutable for the duration of the Planner call.
    Agent must not mutate this object or the underlying state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.0"] = PLANNER_CONTRACT_VERSION
    intent_accepted: AcceptedIntent
    knowledge_pack: KnowledgePack
    skeleton: JourneySkeleton
    config: PlannerConfig
    execution: PlannerExecutionContext
    replan_context: ReplanContext | None = None

    @model_validator(mode="after")
    def _cross_check_skeleton_intent(self) -> PlannerInput:
        sk = self.skeleton
        intent = self.intent_accepted
        if sk.intent and sk.intent != intent.user_intent:
            raise ValueError(
                f"skeleton.intent {sk.intent!r} != accepted intent {intent.user_intent!r}"
            )
        if sk.platform and sk.platform != intent.platform.value:
            raise ValueError(
                f"skeleton.platform {sk.platform!r} != accepted platform {intent.platform!r}"
            )
        if sk.journey_type and sk.journey_type != intent.journey_type.value:
            raise ValueError(
                f"skeleton.journey_type {sk.journey_type!r} != "
                f"accepted journey_type {intent.journey_type!r}"
            )
        return self


# ---------------------------------------------------------------------------
# Planner OUTPUT (planning artifact — NOT JourneyBlueprint)
# ---------------------------------------------------------------------------


class DecisionAttribution(BaseModel):
    """
    Every planning decision must cite at least one supplied fact.

    Knowledge document/chunk IDs must exist in KnowledgePack.attribution_index.
    """

    model_config = ConfigDict(extra="forbid")

    kind: AttributionKind
    ref: str = Field(
        ...,
        min_length=1,
        description="document_id, chunk_id, entity type:value, intent key, step id, or config key",
    )


class PlanningDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    kind: DecisionKind
    subject: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    related_step_ids: list[str] = Field(default_factory=list)
    knowledge_source_ids: list[str] = Field(
        default_factory=list,
        description="Document IDs from KnowledgePack only.",
    )
    attributions: list[DecisionAttribution] = Field(
        ...,
        min_length=1,
        description="At least one attribution to pack knowledge or explicit input fact.",
    )


class EntityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_value: str
    target_step_id: str
    target_field_hint: str | None = None
    knowledge_source_ids: list[str] = Field(default_factory=list)
    attributions: list[DecisionAttribution] = Field(..., min_length=1)


class RequiredInformation(BaseModel):
    """Information the planned journey must collect or resolve — not Blueprint fields."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    required: bool = True
    source: RequiredInfoSource = RequiredInfoSource.USER
    pii: bool = False
    target_step_id: str | None = None
    data_type_hint: str | None = None
    knowledge_source_ids: list[str] = Field(default_factory=list)
    attributions: list[DecisionAttribution] = Field(..., min_length=1)


class PlanningAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    statement: str = Field(..., min_length=1)
    risk: AssumptionRisk
    must_confirm: bool = True
    related_step_ids: list[str] = Field(default_factory=list)
    knowledge_source_ids: list[str] = Field(default_factory=list)
    # resolved/resolution are orchestrator/HITL/validator-owned — not agent-writable
    # Omitted from Planner output intentionally.


class UnknownRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: UnknownRequirementKind
    description: str = Field(..., min_length=1)
    blocking_hint: bool = True
    related_step_ids: list[str] = Field(default_factory=list)
    knowledge_source_ids: list[str] = Field(default_factory=list)


class PlanningConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: float = Field(..., ge=0.0, le=1.0)
    per_step: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None

    @field_validator("per_step")
    @classmethod
    def _scores_in_range(cls, value: dict[str, float]) -> dict[str, float]:
        for key, score in value.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"per_step[{key!r}] out of range")
        return value


class PlannerError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "schema_invalid",
        "uncitable_step",
        "empty_plan",
        "llm_failure",
        "skeleton_mismatch",
        "contract_violation",
    ]
    message: str
    retriable: bool = False


class PlannerOutput(BaseModel):
    """
    Planning artifact only.

    Forbidden: JourneyBlueprint fields (views, actions, api endpoint paths,
    validation_status=validated, platform_extensions as executable UI, etc.).
    Downstream Journey Generator transforms this + skeleton + pack into a draft Blueprint.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = PLANNER_CONTRACT_VERSION
    artifact_type: Literal["journey_plan"] = "journey_plan"
    planner_status: PlannerStatus
    planner_ok: bool
    skeleton_id: str

    ordered_step_ids: list[str] = Field(default_factory=list)
    skipped_optional_step_ids: list[str] = Field(default_factory=list)
    selected_step_ids: list[str] = Field(
        default_factory=list,
        description="Convenience: ordered_step_ids; validated equal if both set.",
    )

    decisions: list[PlanningDecision] = Field(default_factory=list)
    entity_bindings: list[EntityBinding] = Field(default_factory=list)
    required_information: list[RequiredInformation] = Field(default_factory=list)
    assumptions: list[PlanningAssumption] = Field(default_factory=list)
    unknown_requirements: list[UnknownRequirement] = Field(default_factory=list)

    knowledge_references: list[str] = Field(
        default_factory=list,
        description="Union of document IDs cited across the plan; must ⊆ pack.",
    )
    confidence: PlanningConfidence | None = None
    error: PlannerError | None = None

    @model_validator(mode="after")
    def _status_consistency(self) -> PlannerOutput:
        if self.planner_status == PlannerStatus.FAILED:
            if self.planner_ok:
                raise ValueError("FAILED status requires planner_ok=false")
            if self.error is None:
                raise ValueError("FAILED status requires error")
            return self

        if not self.planner_ok:
            raise ValueError("non-FAILED status requires planner_ok=true")
        if self.error is not None:
            raise ValueError("successful plan must not include error")
        if not self.ordered_step_ids:
            raise ValueError("successful plan requires non-empty ordered_step_ids")

        selected = self.selected_step_ids or self.ordered_step_ids
        if self.selected_step_ids and self.selected_step_ids != self.ordered_step_ids:
            raise ValueError("selected_step_ids must match ordered_step_ids when both provided")
        self.selected_step_ids = list(selected)

        if self.assumptions and self.planner_status == PlannerStatus.PLANNED:
            self.planner_status = PlannerStatus.PLANNED_WITH_ASSUMPTIONS
        if self.unknown_requirements and self.planner_status in {
            PlannerStatus.PLANNED,
            PlannerStatus.PLANNED_WITH_ASSUMPTIONS,
        }:
            self.planner_status = PlannerStatus.PLANNED_WITH_UNKNOWNS

        return self
