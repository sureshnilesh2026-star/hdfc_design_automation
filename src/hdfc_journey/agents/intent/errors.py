"""Intent agent errors."""

from __future__ import annotations


class IntentAgentError(Exception):
    """Base error for Intent Recognition Agent (non-LLM transport issues)."""


class IntentBoundaryError(IntentAgentError):
    """Raised when code attempts an operation outside Intent agent boundaries."""
