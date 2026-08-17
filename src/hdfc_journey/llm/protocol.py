"""LLM client protocol — structured output only; no tools, no browsing."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredLLMClient(Protocol):
    """
    Minimal DI surface for agents.

    Implementations must:
    - Return an instance of `response_model` parsed from model output
    - Not expose tool calling
    - Not perform retrieval or HTTP calls unrelated to the LLM provider API
    """

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T: ...
