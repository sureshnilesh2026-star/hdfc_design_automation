"""Application settings for journey-generation components."""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    """Model client configuration (env-overridable)."""

    provider: str = Field(default="openai", description="openai | stub")
    model: str = Field(default="gpt-4o-mini")
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: float = 60.0
    max_retries: int = 1
    temperature: float = 0.0


class PlannerAgentSettings(BaseModel):
    """Settings for JourneyPlannerAgent only."""

    prompt_version: str = "planner-system-v1"
    enforce_contract_validation: bool = True
    llm: LLMSettings = Field(default_factory=LLMSettings)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


@lru_cache(maxsize=1)
def get_planner_settings() -> PlannerAgentSettings:
    """Load planner settings from environment (no .env file required)."""
    provider = _env("HDFC_LLM_PROVIDER", "openai") or "openai"
    return PlannerAgentSettings(
        prompt_version=_env("HDFC_PLANNER_PROMPT_VERSION", "planner-system-v1")
        or "planner-system-v1",
        enforce_contract_validation=_env("HDFC_PLANNER_ENFORCE_CONTRACT", "true")
        != "false",
        llm=LLMSettings(
            provider=provider,
            model=_env("HDFC_LLM_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
            api_key=_env("OPENAI_API_KEY") or _env("HDFC_LLM_API_KEY"),
            base_url=_env("OPENAI_BASE_URL") or _env("HDFC_LLM_BASE_URL"),
            timeout_seconds=float(_env("HDFC_LLM_TIMEOUT_SECONDS", "60") or "60"),
            max_retries=int(_env("HDFC_LLM_MAX_RETRIES", "1") or "1"),
            temperature=float(_env("HDFC_LLM_TEMPERATURE", "0") or "0"),
        ),
    )
