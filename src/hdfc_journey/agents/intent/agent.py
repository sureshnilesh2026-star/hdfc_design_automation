"""Intent Recognition Agent — bounded structured interpretation component.

The agent proposes; it never decides. Acceptance belongs to the deterministic
intent gate, routing belongs to the Router, and state belongs to the
orchestrator. Those capabilities are not merely unused here — they are
explicitly refused (see the boundary methods below), so a future caller cannot
accidentally hand this agent authority it must not have.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from hdfc_journey.agents.intent.errors import IntentBoundaryError
from hdfc_journey.agents.intent.prompts import (
    INTENT_PROMPT_VERSION,
    build_intent_system_prompt,
    build_intent_user_message,
)
from hdfc_journey.config import IntentAgentSettings, get_intent_settings
from hdfc_journey.contracts.intent import (
    IntentError,
    IntentInput,
    IntentProposalOutput,
)
from hdfc_journey.contracts.intent_enums import IntentStatus
from hdfc_journey.contracts.intent_validation import (
    IntentProposalValidationReport,
    validate_intent_proposal_report,
)
from hdfc_journey.llm.openai_client import LLMInvocationError
from hdfc_journey.llm.protocol import StructuredLLMClient
from hdfc_journey.logging_config import get_logger

logger = get_logger(__name__)


class IntentRecognitionAgent:
    """
    Constrained enterprise intent interpreter.

    Receives IntentInput, returns IntentProposalOutput.
    Does not accept intent, retrieve knowledge, mutate JourneyGenerationState,
    route, escalate, or answer the customer.
    """

    def __init__(
        self,
        llm_client: StructuredLLMClient,
        settings: IntentAgentSettings | None = None,
    ) -> None:
        self._llm = llm_client
        self._settings = settings or get_intent_settings()
        self.last_validation_report: IntentProposalValidationReport | None = None
        if self._settings.prompt_version != INTENT_PROMPT_VERSION:
            logger.warning(
                "prompt_version mismatch settings=%s module=%s",
                self._settings.prompt_version,
                INTENT_PROMPT_VERSION,
            )

    @property
    def prompt_version(self) -> str:
        return INTENT_PROMPT_VERSION

    def propose(self, intent_input: IntentInput) -> IntentProposalOutput:
        """
        One interpretation proposal for the orchestrator/gate.

        Returns a structured artifact even when the LLM or contract validation
        fails, so the deterministic gate and Router can decide clarify vs
        escalate. Does not self-retry. Never mutates JourneyGenerationState.
        """
        if not isinstance(intent_input, IntentInput):
            raise TypeError("IntentRecognitionAgent.propose requires IntentInput")

        logger.info(
            "intent_propose run_id=%s modality=%s locale=%s channel_hint=%s "
            "repair_pass=%s chars=%s",
            intent_input.execution.run_id,
            intent_input.utterance.modality,
            intent_input.utterance.locale,
            intent_input.utterance.channel_hint,
            intent_input.execution.repair_pass,
            len(intent_input.utterance.raw_text),
        )

        vocabulary = (
            intent_input.config.registry.vocabulary_for_prompt()
            if intent_input.config.expose_vocabulary_to_model
            else "(vocabulary withheld)"
        )
        system_prompt = build_intent_system_prompt(vocabulary)
        user_prompt = build_intent_user_message(
            intent_input.model_dump_json(by_alias=True)
        )

        try:
            raw_output = self._llm.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=IntentProposalOutput,
            )
        except LLMInvocationError as exc:
            logger.error(
                "intent_llm_failure run_id=%s err=%s",
                intent_input.execution.run_id,
                exc,
            )
            failed = self._failed("llm_failure", str(exc), retriable=True)
            self.last_validation_report = validate_intent_proposal_report(
                failed, intent_input
            )
            return failed
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "intent_unexpected_failure run_id=%s", intent_input.execution.run_id
            )
            failed = self._failed(
                "llm_failure",
                f"Unexpected intent agent failure: {exc}",
                retriable=False,
            )
            self.last_validation_report = validate_intent_proposal_report(
                failed, intent_input
            )
            return failed

        try:
            output = (
                raw_output
                if isinstance(raw_output, IntentProposalOutput)
                else IntentProposalOutput.model_validate(raw_output)
            )
        except ValidationError as exc:
            logger.error(
                "intent_schema_invalid run_id=%s err=%s",
                intent_input.execution.run_id,
                exc,
            )
            failed = self._failed("schema_invalid", str(exc), retriable=True)
            self.last_validation_report = validate_intent_proposal_report(
                failed, intent_input
            )
            return failed

        # Force artifact identity — the agent must never claim to be anything
        # other than a proposal (e.g. an accepted intent or a plan).
        output = output.model_copy(
            update={
                "artifact_type": "intent_proposal",
                "schema_version": "1.0.0",
            }
        )

        if not self._settings.enforce_contract_validation:
            self.last_validation_report = None
            logger.info(
                "intent_propose_done run_id=%s status=%s contract_check=skipped",
                intent_input.execution.run_id,
                output.intent_status,
            )
            return output

        report = validate_intent_proposal_report(output, intent_input)
        self.last_validation_report = report
        assert report.grants_acceptance is False

        logger.info(
            "intent_propose_done run_id=%s status=%s proposal_ok=%s "
            "validation_passed=%s intent=%s confidence=%s ambiguities=%s",
            intent_input.execution.run_id,
            output.intent_status,
            output.proposal_ok,
            report.overall_passed,
            output.user_intent,
            output.confidence,
            len(output.ambiguities),
        )
        return output

    # -- Explicit boundary refusals -----------------------------------------
    # These exist so the boundary is enforced by the type system and the test
    # suite, not merely by documentation.

    def accept_intent(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not accept intent; "
            "acceptance belongs to the deterministic intent gate"
        )

    def merge_into_state(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not mutate JourneyGenerationState; "
            "use intent_state_patch_from_output in the orchestrator"
        )

    def retrieve(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not perform retrieval"
        )

    def search_knowledge(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not access the knowledge database"
        )

    def route(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not perform routing"
        )

    def escalate(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not decide escalation"
        )

    def answer_customer(self, *_args: Any, **_kwargs: Any) -> None:
        raise IntentBoundaryError(
            "IntentRecognitionAgent must not answer the customer; "
            "this platform generates journeys, it does not reply to users"
        )

    @staticmethod
    def _failed(code: str, message: str, *, retriable: bool) -> IntentProposalOutput:
        return IntentProposalOutput(
            intent_status=IntentStatus.FAILED,
            proposal_ok=False,
            user_intent=None,
            journey_type=None,
            product_domain=None,
            platform_hint=None,
            entities=[],
            confidence=0.0,
            ambiguities=[],
            priority_hint=None,
            rationale="",
            error=IntentError(code=code, message=message, retriable=retriable),  # type: ignore[arg-type]
        )


def create_intent_agent(
    llm_client: StructuredLLMClient | None = None,
    settings: IntentAgentSettings | None = None,
) -> IntentRecognitionAgent:
    """
    Factory with dependency injection.

    If llm_client is omitted, builds OpenAI or requires explicit stub in tests.
    """
    resolved = settings or get_intent_settings()
    if llm_client is not None:
        return IntentRecognitionAgent(llm_client=llm_client, settings=resolved)

    if resolved.llm.provider == "stub":
        raise IntentBoundaryError(
            "llm_client is required when HDFC_LLM_PROVIDER=stub "
            "(inject StubStructuredClient in tests/dev)"
        )

    from hdfc_journey.llm.openai_client import OpenAIStructuredClient

    return IntentRecognitionAgent(
        llm_client=OpenAIStructuredClient(resolved.llm),
        settings=resolved,
    )


def intent_input_to_loggable_dict(intent_input: IntentInput) -> dict[str, Any]:
    """Safe summary for logs — never dumps the raw utterance (may contain PII)."""
    return {
        "run_id": str(intent_input.execution.run_id),
        "modality": intent_input.utterance.modality,
        "locale": intent_input.utterance.locale,
        "channel_hint": intent_input.utterance.channel_hint,
        "utterance_chars": len(intent_input.utterance.raw_text),
        "repair_pass": intent_input.execution.repair_pass,
        "vocabulary_size": len(intent_input.config.registry.intent_ids()),
    }


def dumps_intent_io(model: IntentInput | IntentProposalOutput) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2)
