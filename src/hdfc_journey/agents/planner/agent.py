"""Journey Planner Agent — bounded structured planning component."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from hdfc_journey.agents.planner.errors import PlannerBoundaryError
from hdfc_journey.agents.planner.prompts import (
    JOURNEY_PLANNER_SYSTEM_PROMPT,
    PLANNER_PROMPT_VERSION,
    build_planner_user_message,
)
from hdfc_journey.config import PlannerAgentSettings, get_planner_settings
from hdfc_journey.contracts.enums import PlannerStatus
from hdfc_journey.contracts.planner import PlannerError, PlannerInput, PlannerOutput
from hdfc_journey.contracts.validation import (
    PlannerOutputValidationReport,
    validate_planner_output_report,
)
from hdfc_journey.llm.openai_client import LLMInvocationError
from hdfc_journey.llm.protocol import StructuredLLMClient
from hdfc_journey.logging_config import get_logger

logger = get_logger(__name__)


class JourneyPlannerAgent:
    """
    Constrained enterprise journey planner.

    Receives PlannerInput, returns PlannerOutput.
    Does not access knowledge DB, retrieve, mutate JourneyGenerationState,
    route, escalate, validate journeys officially, or call enterprise APIs.
    """

    def __init__(
        self,
        llm_client: StructuredLLMClient,
        settings: PlannerAgentSettings | None = None,
    ) -> None:
        self._llm = llm_client
        self._settings = settings or get_planner_settings()
        self.last_validation_report: PlannerOutputValidationReport | None = None
        if self._settings.prompt_version != PLANNER_PROMPT_VERSION:
            logger.warning(
                "prompt_version mismatch settings=%s module=%s",
                self._settings.prompt_version,
                PLANNER_PROMPT_VERSION,
            )

    @property
    def prompt_version(self) -> str:
        return PLANNER_PROMPT_VERSION

    def propose(self, planner_input: PlannerInput) -> PlannerOutput:
        """
        One planning proposal for the orchestrator/Router.

        Returns structured output even when contract validation fails so the
        deterministic Router can decide repair vs escalate. Does not self-retry.
        Never mutates JourneyGenerationState.
        """
        if not isinstance(planner_input, PlannerInput):
            raise TypeError("JourneyPlannerAgent.propose requires PlannerInput")

        logger.info(
            "planner_propose run_id=%s skeleton_id=%s intent=%s platform=%s repair_pass=%s",
            planner_input.execution.run_id,
            planner_input.skeleton.skeleton_id,
            planner_input.intent_accepted.user_intent,
            planner_input.intent_accepted.platform,
            planner_input.execution.repair_pass,
        )

        user_prompt = build_planner_user_message(
            planner_input.model_dump_json(by_alias=True)
        )

        try:
            raw_output = self._llm.complete_structured(
                system_prompt=JOURNEY_PLANNER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=PlannerOutput,
            )
        except LLMInvocationError as exc:
            logger.error("planner_llm_failure run_id=%s err=%s", planner_input.execution.run_id, exc)
            failed = self._failed(
                skeleton_id=planner_input.skeleton.skeleton_id,
                code="llm_failure",
                message=str(exc),
                retriable=True,
            )
            self.last_validation_report = validate_planner_output_report(
                failed, planner_input
            )
            return failed
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "planner_unexpected_failure run_id=%s", planner_input.execution.run_id
            )
            failed = self._failed(
                skeleton_id=planner_input.skeleton.skeleton_id,
                code="llm_failure",
                message=f"Unexpected planner failure: {exc}",
                retriable=False,
            )
            self.last_validation_report = validate_planner_output_report(
                failed, planner_input
            )
            return failed

        try:
            output = (
                raw_output
                if isinstance(raw_output, PlannerOutput)
                else PlannerOutput.model_validate(raw_output)
            )
        except ValidationError as exc:
            logger.error(
                "planner_schema_invalid run_id=%s err=%s",
                planner_input.execution.run_id,
                exc,
            )
            failed = self._failed(
                skeleton_id=planner_input.skeleton.skeleton_id,
                code="schema_invalid",
                message=str(exc),
                retriable=True,
            )
            self.last_validation_report = validate_planner_output_report(
                failed, planner_input
            )
            return failed

        # Force artifact identity — Planner must never claim Blueprint validation.
        output = output.model_copy(
            update={
                "artifact_type": "journey_plan",
                "schema_version": "1.0.0",
            }
        )

        if not self._settings.enforce_contract_validation:
            self.last_validation_report = None
            logger.info(
                "planner_propose_done run_id=%s status=%s contract_check=skipped",
                planner_input.execution.run_id,
                output.planner_status,
            )
            return output

        report = validate_planner_output_report(output, planner_input)
        self.last_validation_report = report
        assert report.official_journey_validation is False

        logger.info(
            "planner_propose_done run_id=%s status=%s planner_ok=%s "
            "validation_passed=%s steps=%s",
            planner_input.execution.run_id,
            output.planner_status,
            output.planner_ok,
            report.overall_passed,
            len(output.ordered_step_ids),
        )
        return output

    def plan(self, planner_input: PlannerInput) -> PlannerOutput:
        """
        Standalone planning pass with fail-closed contract handling.

        Prefer orchestrator ``run_planning_stage`` (uses ``propose`` + Router).
        This method never self-repairs and never mutates workflow state.
        """
        output = self.propose(planner_input)
        report = self.last_validation_report

        if output.planner_status == PlannerStatus.FAILED or not output.planner_ok:
            return output

        if (
            self._settings.enforce_contract_validation
            and report is not None
            and not report.overall_passed
        ):
            detail = report.error_summary()
            logger.warning(
                "planner_contract_violation run_id=%s detail=%s",
                planner_input.execution.run_id,
                detail,
            )
            failed = self._failed(
                skeleton_id=planner_input.skeleton.skeleton_id,
                code="contract_violation",
                message=detail,
                retriable=True,
            )
            # Keep the failing report (not the failed-output revalidation).
            self.last_validation_report = report
            return failed

        return output

    def merge_into_state(self, *_args: Any, **_kwargs: Any) -> None:
        """Explicitly forbidden — orchestrator owns state mutation."""
        raise PlannerBoundaryError(
            "JourneyPlannerAgent must not mutate JourneyGenerationState; "
            "use planning_state_patch_from_output in the orchestrator"
        )

    def retrieve(self, *_args: Any, **_kwargs: Any) -> None:
        raise PlannerBoundaryError("JourneyPlannerAgent must not perform retrieval")

    def search_knowledge(self, *_args: Any, **_kwargs: Any) -> None:
        raise PlannerBoundaryError(
            "JourneyPlannerAgent must not access the knowledge database"
        )

    def validate_journey(self, *_args: Any, **_kwargs: Any) -> None:
        raise PlannerBoundaryError(
            "JourneyPlannerAgent must not perform journey validation pass/fail"
        )

    def route(self, *_args: Any, **_kwargs: Any) -> None:
        raise PlannerBoundaryError("JourneyPlannerAgent must not perform routing")

    @staticmethod
    def _failed(
        *,
        skeleton_id: str,
        code: str,
        message: str,
        retriable: bool,
    ) -> PlannerOutput:
        return PlannerOutput(
            planner_status=PlannerStatus.FAILED,
            planner_ok=False,
            skeleton_id=skeleton_id,
            ordered_step_ids=[],
            skipped_optional_step_ids=[],
            selected_step_ids=[],
            decisions=[],
            entity_bindings=[],
            required_information=[],
            assumptions=[],
            unknown_requirements=[],
            knowledge_references=[],
            confidence=None,
            error=PlannerError(code=code, message=message, retriable=retriable),  # type: ignore[arg-type]
        )


def create_planner_agent(
    llm_client: StructuredLLMClient | None = None,
    settings: PlannerAgentSettings | None = None,
) -> JourneyPlannerAgent:
    """
    Factory with dependency injection.

    If llm_client is omitted, builds OpenAI or requires explicit stub in tests.
    """
    resolved = settings or get_planner_settings()
    if llm_client is not None:
        return JourneyPlannerAgent(llm_client=llm_client, settings=resolved)

    if resolved.llm.provider == "stub":
        raise PlannerBoundaryError(
            "llm_client is required when HDFC_LLM_PROVIDER=stub "
            "(inject StubStructuredClient in tests/dev)"
        )

    from hdfc_journey.llm.openai_client import OpenAIStructuredClient

    return JourneyPlannerAgent(
        llm_client=OpenAIStructuredClient(resolved.llm),
        settings=resolved,
    )


def planner_input_to_loggable_dict(planner_input: PlannerInput) -> dict[str, Any]:
    """Safe summary for logs (no full excerpts dump)."""
    return {
        "run_id": str(planner_input.execution.run_id),
        "intent": planner_input.intent_accepted.user_intent,
        "platform": planner_input.intent_accepted.platform,
        "skeleton_id": planner_input.skeleton.skeleton_id,
        "pack_id": planner_input.knowledge_pack.pack_id,
        "doc_ids": list(planner_input.knowledge_pack.attribution_index.by_document),
    }


def dumps_planner_io(model: PlannerInput | PlannerOutput) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2)
