"""Application settings for journey-generation components."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_DOTENV_LOADED_PATHS: set[Path] = set()


def _apply_dotenv_file(path: Path) -> None:
    """Load KEY=VALUE pairs without overriding variables already in the environment."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


def load_dotenv() -> None:
    """Load the repo-root (or cwd) ``.env`` so agents can read OPENAI_API_KEY."""
    candidates = (
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in _DOTENV_LOADED_PATHS or not resolved.is_file():
            continue
        _apply_dotenv_file(resolved)
        _DOTENV_LOADED_PATHS.add(resolved)


load_dotenv()


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


class IntentAgentSettings(BaseModel):
    """Settings for IntentRecognitionAgent only."""

    prompt_version: str = "intent-system-v1"
    enforce_contract_validation: bool = True
    llm: LLMSettings = Field(default_factory=LLMSettings)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


@lru_cache(maxsize=1)
def get_planner_settings() -> PlannerAgentSettings:
    """Load planner settings from environment and optional repo-root ``.env``."""
    load_dotenv()
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


@lru_cache(maxsize=1)
def get_intent_settings() -> IntentAgentSettings:
    """Load intent-agent settings from environment and optional repo-root ``.env``."""
    load_dotenv()
    provider = _env("HDFC_LLM_PROVIDER", "openai") or "openai"
    return IntentAgentSettings(
        prompt_version=_env("HDFC_INTENT_PROMPT_VERSION", "intent-system-v1")
        or "intent-system-v1",
        enforce_contract_validation=_env("HDFC_INTENT_ENFORCE_CONTRACT", "true")
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
