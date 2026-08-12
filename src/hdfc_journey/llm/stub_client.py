"""Test/dev stub LLM — returns a caller-provided structured object; no network."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StubStructuredClient:
    """
    Deterministic StructuredLLMClient for tests.

    `handler` receives (system_prompt, user_prompt, response_model) and must
    return an instance of response_model. No I/O.
    """

    def __init__(
        self,
        handler: Callable[[str, str, type[BaseModel]], BaseModel],
    ) -> None:
        self._handler = handler
        self.calls: list[dict[str, str]] = []

    def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ) -> T:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_model": response_model.__name__,
            }
        )
        result = self._handler(system_prompt, user_prompt, response_model)
        if not isinstance(result, response_model):
            raise TypeError(
                f"Stub handler must return {response_model.__name__}, got {type(result)}"
            )
        return result
