"""Planner agent errors."""

from __future__ import annotations


class PlannerAgentError(Exception):
    """Base error for Journey Planner Agent (non-LLM transport issues)."""


class PlannerBoundaryError(PlannerAgentError):
    """Raised when code attempts an operation outside Planner boundaries."""
