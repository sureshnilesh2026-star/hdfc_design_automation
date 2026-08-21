"""Live health probes — never treat missing telemetry as healthy."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from agentops_api.config import BOOT_ID, DATA_DIR, DB_PATH, KNOWLEDGE_ROOT
from agentops_api.db import db
from agentops_api.registry import AGENT_CATALOG, empty_metrics

PROCESS_STARTED_AT = datetime.now(timezone.utc)
PROCESS_STARTED_MONO = time.monotonic()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def process_uptime_seconds() -> float:
    return time.monotonic() - PROCESS_STARTED_MONO


def llm_runtime() -> dict[str, Any]:
    from hdfc_journey.config import get_intent_settings

    settings = get_intent_settings()
    has_key = bool(settings.llm.api_key)
    provider = settings.llm.provider
    if provider == "openai" and has_key:
        status = "healthy"
        note = "OpenAI-compatible client is configured."
        runtime_mode = "openai"
    elif provider == "stub":
        status = "degraded"
        note = "LLM provider is stub. Deterministic runtime is active."
        runtime_mode = "deterministic"
    elif not has_key:
        status = "degraded"
        note = "No LLM API key configured. Deterministic runtime is available as fallback."
        runtime_mode = "deterministic-fallback"
    else:
        status = "unknown"
        note = "LLM configuration could not be classified."
        runtime_mode = "unknown"
    return {
        "component": "llm",
        "status": status,
        "provider": provider,
        "model": settings.llm.model,
        "has_api_key": has_key,
        "runtime_mode": runtime_mode,
        "note": note,
        "last_checked": _iso(datetime.now(timezone.utc)),
    }


def probe_component(name: str) -> dict[str, Any]:
    now = _iso(datetime.now(timezone.utc))
    if name == "api":
        return {"component": "api", "status": "healthy", "note": "AgentOps API is serving.", "last_checked": now}
    if name == "database":
        try:
            with db() as conn:
                conn.execute("SELECT 1").fetchone()
            return {
                "component": "database",
                "status": "healthy",
                "note": f"SQLite at {DB_PATH.name}",
                "last_checked": now,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "component": "database",
                "status": "unavailable",
                "note": str(exc),
                "last_checked": now,
            }
    if name == "knowledge_repository":
        if KNOWLEDGE_ROOT.is_dir():
            count = sum(1 for p in KNOWLEDGE_ROOT.rglob("*.md") if p.is_file())
            return {
                "component": "knowledge_repository",
                "status": "healthy",
                "note": f"{count} markdown documents on disk.",
                "last_checked": now,
            }
        return {
            "component": "knowledge_repository",
            "status": "unavailable",
            "note": "Knowledge_Base directory is missing.",
            "last_checked": now,
        }
    if name == "vector_search":
        return {
            "component": "vector_search",
            "status": "unknown",
            "note": "Vector / embedding service is not instrumented.",
            "last_checked": now,
        }
    if name == "llm":
        runtime = llm_runtime()
        return {
            "component": "llm",
            "status": runtime["status"],
            "note": runtime["note"],
            "last_checked": now,
            "detail": runtime,
        }
    if name == "authentication":
        return {
            "component": "authentication",
            "status": "healthy",
            "note": "Local session authentication is active.",
            "last_checked": now,
        }
    if name == "storage":
        writable = os.access(DATA_DIR, os.W_OK) if DATA_DIR.exists() else False
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        writable = os.access(DATA_DIR, os.W_OK)
        return {
            "component": "storage",
            "status": "healthy" if writable else "unavailable",
            "note": f"Data directory {DATA_DIR}",
            "last_checked": now,
        }
    return {"component": name, "status": "unknown", "note": "No probe registered.", "last_checked": now}


def system_health() -> dict[str, Any]:
    components = [
        probe_component("api"),
        probe_component("database"),
        probe_component("knowledge_repository"),
        probe_component("vector_search"),
        probe_component("llm"),
        probe_component("authentication"),
        probe_component("storage"),
    ]
    statuses = {c["status"] for c in components}
    if "unavailable" in statuses:
        overall = "unavailable"
    elif "degraded" in statuses or "unknown" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"
    return {
        "overall": overall,
        "boot_id": BOOT_ID,
        "started_at": _iso(PROCESS_STARTED_AT),
        "uptime_seconds": round(process_uptime_seconds(), 1),
        "components": components,
        "note": "Unknown means no telemetry — it is not treated as healthy.",
    }


def agent_runtime_health(agent_id: str) -> dict[str, Any]:
    agent = next((a for a in AGENT_CATALOG if a.agent_id == agent_id), None)
    now = datetime.now(timezone.utc)
    heartbeat = _iso(now)
    if agent is None:
        return {
            "status": "UNKNOWN",
            "health_score": None,
            "last_heartbeat": heartbeat,
            "note": "Agent is not registered.",
            "metrics": empty_metrics(),
        }
    if agent.lifecycle == "in_development":
        return {
            "status": "IN_DEVELOPMENT",
            "health_score": None,
            "last_heartbeat": None,
            "uptime_seconds": None,
            "note": "This agent is not implemented yet.",
            "runtime": "not_available",
            "metrics": empty_metrics(),
        }

    if agent_id == "intent-recognition":
        try:
            from hdfc_journey.agents.intent.agent import IntentRecognitionAgent  # noqa: F401

            llm = llm_runtime()
            status = "HEALTHY" if llm["status"] == "healthy" else "DEGRADED"
            return {
                "status": status,
                "health_score": None,
                "last_heartbeat": heartbeat,
                "uptime_seconds": round(process_uptime_seconds(), 1),
                "note": llm["note"],
                "runtime": llm["runtime_mode"],
                "version": agent.version,
                "importable": True,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "OFFLINE",
                "health_score": None,
                "last_heartbeat": heartbeat,
                "note": f"Intent agent could not be loaded: {exc}",
                "runtime": "unavailable",
                "importable": False,
            }

    if agent_id == "platform-capability":
        try:
            from hdfc_journey.orchestrator.capability_check import (  # noqa: WPS433
                _ensure_capability_agent_on_path,
                default_shared_knowledge_dir,
            )

            _ensure_capability_agent_on_path()
            kb = default_shared_knowledge_dir()
            if not kb.is_dir():
                return {
                    "status": "DEGRADED",
                    "last_heartbeat": heartbeat,
                    "uptime_seconds": round(process_uptime_seconds(), 1),
                    "note": "Platform capability knowledge directory is missing.",
                    "runtime": "deterministic",
                    "importable": True,
                }
            from agent import PlatformCapabilityAgent  # noqa: WPS433

            PlatformCapabilityAgent(knowledge_dir=str(kb))
            return {
                "status": "HEALTHY",
                "health_score": None,
                "last_heartbeat": heartbeat,
                "uptime_seconds": round(process_uptime_seconds(), 1),
                "note": "Deterministic capability agent loaded its knowledge files.",
                "runtime": "deterministic",
                "importable": True,
                "version": agent.version,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "OFFLINE",
                "last_heartbeat": heartbeat,
                "note": f"Platform capability agent could not be reached: {exc}",
                "runtime": "unavailable",
                "importable": False,
            }

    if agent_id == "knowledge-repository":
        if KNOWLEDGE_ROOT.is_dir():
            return {
                "status": "HEALTHY",
                "health_score": None,
                "last_heartbeat": heartbeat,
                "uptime_seconds": round(process_uptime_seconds(), 1),
                "note": "Filesystem knowledge index is available. Embedding is not instrumented.",
                "runtime": "filesystem",
                "importable": True,
                "version": agent.version,
            }
        return {
            "status": "OFFLINE",
            "last_heartbeat": heartbeat,
            "note": "Knowledge_Base is not available.",
            "runtime": "unavailable",
        }

    if agent_id == "journey-planner":
        try:
            from hdfc_journey.agents.planner.agent import JourneyPlannerAgent  # noqa: F401

            llm = llm_runtime()
            status = "HEALTHY" if llm["status"] == "healthy" else "DEGRADED"
            return {
                "status": status,
                "health_score": None,
                "last_heartbeat": heartbeat,
                "uptime_seconds": round(process_uptime_seconds(), 1),
                "note": llm["note"],
                "runtime": llm["runtime_mode"],
                "importable": True,
                "version": agent.version,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "OFFLINE",
                "last_heartbeat": heartbeat,
                "note": f"Journey planner could not be loaded: {exc}",
                "runtime": "unavailable",
                "importable": False,
            }

    return {
        "status": "UNKNOWN",
        "last_heartbeat": heartbeat,
        "note": "No health probe for this agent.",
        "runtime": "unknown",
    }
