"""Journey skeleton contract — structural source of truth for Planner."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hdfc_journey.contracts.enums import SkeletonStepType


class SkeletonStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    type: SkeletonStepType
    name: str = Field(..., min_length=1)
    ordinal: int = Field(..., ge=0)
    optional: bool = False
    description: str | None = None
    required_entity_types: list[str] = Field(default_factory=list)
    suggested_field_ids: list[str] = Field(default_factory=list)
    allowed_knowledge_source_ids: list[str] = Field(
        default_factory=list,
        description="If non-empty, step citations must be subset of this ∩ pack.",
    )


class JourneySkeleton(BaseModel):
    """Loaded by orchestrator; Planner may only select/order/skip known steps."""

    model_config = ConfigDict(extra="forbid")

    skeleton_id: str
    journey_id: str
    intent: str | None = None
    platform: str | None = None
    journey_type: str | None = None
    product_domain: str | None = None
    version: str = "1.0.0"
    steps: list[SkeletonStep] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _unique_step_ids(self) -> JourneySkeleton:
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("skeleton step ids must be unique")
        return self

    def step_ids(self) -> set[str]:
        return {s.id for s in self.steps}

    def step_by_id(self, step_id: str) -> SkeletonStep | None:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def required_step_ids(self) -> set[str]:
        return {s.id for s in self.steps if not s.optional}
