"""OpenAI structured-output client (LLM provider API only — no tools, no web)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from hdfc_journey.config import LLMSettings
from hdfc_journey.logging_config import get_logger

T = TypeVar("T", bound=BaseModel)
logger = get_logger(__name__)


class LLMInvocationError(RuntimeError):
    """Raised when the provider call or structured parse fails."""


class OpenAIStructuredClient:
    """
    Structured LLM client using the OpenAI SDK chat.completions.parse API.

    Boundary:
    - Calls the configured OpenAI-compatible endpoint only
    - Does not register tools
    - Does not browse the internet or access enterprise knowledge stores
    """

    def __init__(self, settings: LLMSettings) -> None:
        if not settings.api_key:
            raise LLMInvocationError(
                "OPENAI_API_KEY / HDFC_LLM_API_KEY is required for OpenAIStructuredClient"
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMInvocationError(
                "openai package is required; install with pip install 'hdfc-design-automation[llm]'"
            ) from exc

        self._settings = settings
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        logger.info(
            "openai_structured_completion model=%s response_model=%s",
            self._settings.model,
            response_model.__name__,
        )
        try:
            completion = self._client.beta.chat.completions.parse(
                model=self._settings.model,
                temperature=self._settings.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=response_model,
            )
        except Exception as exc:  # noqa: BLE001 — normalized for agent boundary
            raise LLMInvocationError(f"OpenAI structured completion failed: {exc}") from exc

        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise LLMInvocationError(f"Model refused: {message.refusal}")

        parsed = message.parsed
        if parsed is None:
            # Fallback: parse content JSON manually
            content = message.content or ""
            try:
                return response_model.model_validate_json(content)
            except ValidationError as exc:
                raise LLMInvocationError(
                    f"Failed to parse model content as {response_model.__name__}: {exc}"
                ) from exc
        return parsed
