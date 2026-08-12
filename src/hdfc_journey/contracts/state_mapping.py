"""Map Planner contracts ↔ JourneyGenerationState.business.planning (documentation helpers)."""

from __future__ import annotations

from typing import Any

from hdfc_journey.contracts.planner import PlannerInput, PlannerOutput

# Fields on JourneyGenerationState that Planner may cause to be written
# (only via orchestrator merge — never by direct mutation).
AGENT_WRITABLE_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.planning.decisions",
        "business.planning.assumptions",  # statements only; resolved/resolution forbidden
        "business.planning.unknown_requirements",  # extension field mirrored from PlanResult
        "business.planning.entity_bindings",
        "business.planning.required_information",
        "business.planning.ordered_step_ids",
        "business.planning.skipped_optional_step_ids",
        "business.planning.knowledge_references",
        "business.planning.confidence",
        "business.planning.planner_status",
    }
)

# Set by orchestrator before/after Planner; Planner must not write.
ORCHESTRATOR_ONLY_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.planning.skeleton_id",
        "business.status",
        "business.intent.accepted",
        "business.knowledge",
        "business.generation",
        "business.validation",
        "business.hitl",
        "business.output",
        "execution.current_stage",
        "execution.stage_history",
        "execution.agents.planner",
        "execution.trace",
        "execution.gates",
    }
)

IMMUTABLE_INPUT_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.input.raw",
        "business.input.normalized",
        "business.intent.accepted",
        "business.knowledge",
        "execution.run_id",
        "execution.config_snapshot",
    }
)


def build_planner_input_from_state_slice(
    *,
    intent_accepted: dict[str, Any],
    knowledge: dict[str, Any],
    skeleton: dict[str, Any],
    config: dict[str, Any],
    execution: dict[str, Any],
    replan_context: dict[str, Any] | None = None,
) -> PlannerInput:
    """Construct PlannerInput from state slices (orchestrator helper)."""
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "intent_accepted": intent_accepted,
        "knowledge_pack": knowledge,
        "skeleton": skeleton,
        "config": config,
        "execution": execution,
    }
    if replan_context is not None:
        payload["replan_context"] = replan_context
    return PlannerInput.model_validate(payload)


def planning_state_patch_from_output(output: PlannerOutput) -> dict[str, Any]:
    """
    Deterministic merge patch for business.planning.

    Does NOT set skeleton_id, status, generation.blueprint_*, or validation.
    Orchestrator applies this patch after validate_planner_output succeeds.
    """
    if not output.planner_ok:
        return {
            "planner_status": output.planner_status.value,
            "error": output.error.model_dump() if output.error else None,
        }

    return {
        "decisions": [d.model_dump(mode="json") for d in output.decisions],
        "assumptions": [
            {
                **a.model_dump(mode="json"),
                "resolved": False,
                "resolution": None,
            }
            for a in output.assumptions
        ],
        "unknown_requirements": [
            u.model_dump(mode="json") for u in output.unknown_requirements
        ],
        "entity_bindings": [b.model_dump(mode="json") for b in output.entity_bindings],
        "required_information": [
            r.model_dump(mode="json") for r in output.required_information
        ],
        "ordered_step_ids": list(output.ordered_step_ids),
        "skipped_optional_step_ids": list(output.skipped_optional_step_ids),
        "selected_step_ids": list(output.selected_step_ids),
        "knowledge_references": list(output.knowledge_references),
        "confidence": output.confidence.model_dump(mode="json")
        if output.confidence
        else None,
        "planner_status": output.planner_status.value,
        "plan_artifact_type": output.artifact_type,
        "plan_schema_version": output.schema_version,
    }
