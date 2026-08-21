"""Workflow runner — executes the real operational agents and records traces.

Future pipeline stages are marked not_implemented. Metrics come only from
stored executions. Demo mode uses the same agents and is labelled DEMO.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agentops_api.db import db, dumps, loads
from agentops_api.health import llm_runtime
from agentops_api.knowledge import retrieve_pack
from agentops_api.registry import AGENT_CATALOG
from hdfc_journey.agents.intent.agent import IntentRecognitionAgent
from hdfc_journey.agents.intent.prompts import INTENT_PROMPT_VERSION
from hdfc_journey.agents.planner.agent import JourneyPlannerAgent
from hdfc_journey.agents.planner.prompts import PLANNER_PROMPT_VERSION
from hdfc_journey.config import IntentAgentSettings, PlannerAgentSettings, get_intent_settings
from hdfc_journey.contracts.enums import SkeletonStepType
from hdfc_journey.contracts.intent_registry import IntentRegistry
from hdfc_journey.contracts.skeleton import JourneySkeleton, SkeletonStep
from hdfc_journey.contracts.state import JourneyGenerationState, NormalizedInput, RawInput
from hdfc_journey.llm.deterministic_intent import deterministic_intent_llm_handler
from hdfc_journey.llm.deterministic_planner import deterministic_planner_llm_handler
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.capability_check import (
    CapabilityCheckError,
    run_capability_check,
)
from hdfc_journey.orchestrator.intent import run_intent_stage
from hdfc_journey.orchestrator.planning import run_planning_stage

_subscribers: dict[str, list[queue.Queue]] = {}
_sub_lock = threading.Lock()
_active: dict[str, str] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_ids(now: datetime | None = None) -> dict[str, str]:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    suffix = uuid4().hex[:5].upper()
    return {
        "flow_id": f"FLW-{stamp}-{suffix}",
        "execution_id": f"EXE-{uuid4().hex[:10].upper()}",
        "trace_id": f"TRC-{uuid4().hex[:8].upper()}",
    }


def subscribe(execution_id: str) -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with _sub_lock:
        _subscribers.setdefault(execution_id, []).append(q)
    return q


def unsubscribe(execution_id: str, q: queue.Queue) -> None:
    with _sub_lock:
        listeners = _subscribers.get(execution_id, [])
        if q in listeners:
            listeners.remove(q)


def _publish(execution_id: str, event: dict[str, Any]) -> None:
    with _sub_lock:
        listeners = list(_subscribers.get(execution_id, []))
    for q in listeners:
        q.put(event)


def _append_event(
    execution_id: str,
    *,
    agent_id: str | None,
    event_type: str,
    status: str | None,
    message: str,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "at": _utcnow(),
        "agent_id": agent_id,
        "event_type": event_type,
        "status": status,
        "message": message,
        "duration_ms": duration_ms,
        "payload": payload or {},
    }
    with db() as conn:
        conn.execute(
            """
            INSERT INTO execution_events
                (execution_id, at, agent_id, event_type, status, message, duration_ms, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                event["at"],
                agent_id,
                event_type,
                status,
                message,
                duration_ms,
                dumps(payload or {}),
            ),
        )
    _publish(execution_id, event)
    return event


def _update_execution(execution_id: str, **fields: Any) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [execution_id]
    with db() as conn:
        conn.execute(f"UPDATE executions SET {assignments} WHERE execution_id = ?", values)


def _load_execution(execution_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM executions WHERE execution_id = ?", (execution_id,)
        ).fetchone()
    if row is None:
        return None
    data = {k: row[k] for k in row.keys()}
    data["payload"] = loads(data.get("payload"), {})
    return data


def build_llm_client(kind: str) -> tuple[Any, str, str]:
    """Return (client, runtime_mode, model_name). Never silently pretends to be OpenAI."""
    settings = get_intent_settings()
    runtime = llm_runtime()
    if runtime["runtime_mode"] == "openai":
        from hdfc_journey.llm.openai_client import OpenAIStructuredClient

        client = OpenAIStructuredClient(settings.llm)
        return client, "openai", settings.llm.model
    handler = (
        deterministic_intent_llm_handler
        if kind == "intent"
        else deterministic_planner_llm_handler
    )
    client = StubStructuredClient(handler)
    return client, runtime["runtime_mode"], f"deterministic-{kind}-v1"


def _make_state(*, raw_text: str, channel_hint: str) -> JourneyGenerationState:
    state = JourneyGenerationState()
    state.business.input.raw = RawInput(
        modality="text", text=raw_text, channel_hint=channel_hint
    )
    state.business.input.normalized = NormalizedInput(
        request_id=uuid4(),
        modality="text",
        raw_text=raw_text,
        channel_hint=channel_hint,
        locale="en-IN",
    )
    state.execution.config_snapshot.intent_allowlist = [
        "APPLY_CREDIT_CARD",
        "UPDATE_ADDRESS",
        "BLOCK_CARD",
        "CHECK_BALANCE",
    ]
    state.execution.config_snapshot.platform_allowlist = [
        "asknow",
        "eva_dbu",
        "web",
        "mobile_native",
    ]
    state.execution.config_snapshot.confidence_floor = 0.7
    return state


def generic_skeleton(accepted: Any) -> JourneySkeleton:
    intent = accepted.user_intent
    platform = accepted.platform.value
    journey_type = accepted.journey_type.value
    return JourneySkeleton(
        skeleton_id=f"JOURNEY-{intent}-GENERIC",
        journey_id=f"JN-{intent}",
        intent=intent,
        platform=platform,
        journey_type=journey_type,
        product_domain=accepted.product_domain,
        version="0.1.0-generic",
        steps=[
            SkeletonStep(
                id="auth_gate",
                type=SkeletonStepType.AUTH_GATE,
                name="Authenticate customer",
                ordinal=0,
                optional=False,
                description="Verify the customer before a protected action.",
            ),
            SkeletonStep(
                id="capture_information",
                type=SkeletonStepType.INTERACTION,
                name="Capture required information",
                ordinal=1,
                optional=False,
                description="Collect fields required to complete the journey.",
            ),
            SkeletonStep(
                id="review",
                type=SkeletonStepType.CONFIRMATION,
                name="Review details",
                ordinal=2,
                optional=False,
            ),
            SkeletonStep(
                id="submit",
                type=SkeletonStepType.TERMINAL,
                name="Submit",
                ordinal=3,
                optional=False,
            ),
        ],
    )


def _init_stages() -> list[dict[str, Any]]:
    stages = [
        {
            "agent_id": "request",
            "name": "Request",
            "kind": "anchor",
            "status": "completed",
            "duration_ms": None,
            "note": None,
        }
    ]
    for agent in AGENT_CATALOG:
        if agent.lifecycle == "in_development":
            status = "not_implemented"
            note = "In development"
        else:
            status = "not_started"
            note = None
        stages.append(
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "kind": "agent",
                "status": status,
                "duration_ms": None,
                "note": note,
                "input": None,
                "output": None,
                "error": None,
                "events": [],
            }
        )
    stages.append(
        {
            "agent_id": "output-delivery",
            "name": "Output",
            "kind": "anchor",
            "status": "not_implemented",
            "duration_ms": None,
            "note": "Downstream output packaging is in development.",
        }
    )
    return stages


def create_execution(
    *,
    request_text: str,
    channel: str,
    username: str,
    user_id: int | None,
    mode: str = "live",
    replay_of: str | None = None,
    parent_trace_id: str | None = None,
    environment: str = "local",
) -> dict[str, Any]:
    ids = _new_ids()
    now = _utcnow()
    payload = {
        "stages": _init_stages(),
        "business_summary": "Request received. Waiting to start.",
        "request": {"text": request_text, "channel": channel},
        "mode": mode,
        "replay_of": replay_of,
    }
    with db() as conn:
        conn.execute(
            """
            INSERT INTO executions (
                flow_id, execution_id, trace_id, parent_trace_id, user_id, username,
                request_text, channel, environment, mode, runtime_mode, status,
                current_stage, started_at, replay_of, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 'request', ?, ?, ?)
            """,
            (
                ids["flow_id"],
                ids["execution_id"],
                ids["trace_id"],
                parent_trace_id,
                user_id,
                username,
                request_text,
                channel,
                environment,
                mode,
                None,
                now,
                replay_of,
                dumps(payload),
            ),
        )
    return get_execution(ids["execution_id"]) or {}


def get_execution(execution_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM executions WHERE execution_id = ? OR flow_id = ? OR trace_id = ?",
            (execution_id, execution_id, execution_id),
        ).fetchone()
        if row is None:
            return None
        events = conn.execute(
            "SELECT * FROM execution_events WHERE execution_id = ? ORDER BY id ASC",
            (row["execution_id"],),
        ).fetchall()
    data = {k: row[k] for k in row.keys()}
    data["payload"] = loads(data.get("payload"), {})
    data["events"] = [
        {
            **{k: ev[k] for k in ev.keys()},
            "payload": loads(ev["payload"], {}),
        }
        for ev in events
    ]
    data["is_demo"] = data.get("mode") == "demo"
    return data


def list_executions(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    sql = "SELECT * FROM executions WHERE 1=1"
    params: list[Any] = []
    if filters.get("status"):
        sql += " AND status = ?"
        params.append(filters["status"])
    if filters.get("agent"):
        sql += " AND current_stage = ?"
        params.append(filters["agent"])
    if filters.get("user"):
        sql += " AND username = ?"
        params.append(filters["user"])
    if filters.get("environment"):
        sql += " AND environment = ?"
        params.append(filters["environment"])
    if filters.get("mode"):
        sql += " AND mode = ?"
        params.append(filters["mode"])
    sql += " ORDER BY id DESC LIMIT 200"
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for row in rows:
        item = {k: row[k] for k in row.keys()}
        item["payload"] = loads(item.get("payload"), {})
        item["is_demo"] = item.get("mode") == "demo"
        result.append(item)
    return result


def _set_stage(payload: dict[str, Any], agent_id: str, **fields: Any) -> None:
    for stage in payload["stages"]:
        if stage["agent_id"] == agent_id:
            stage.update(fields)
            return


def _business_progress(payload: dict[str, Any]) -> str:
    operational = [
        s
        for s in payload["stages"]
        if s.get("kind") == "agent"
        and next((a for a in AGENT_CATALOG if a.agent_id == s["agent_id"]), None)
        and next(a for a in AGENT_CATALOG if a.agent_id == s["agent_id"]).lifecycle
        == "operational"
    ]
    completed = [s for s in operational if s["status"] == "completed"]
    running = next((s for s in operational if s["status"] == "running"), None)
    failed = next((s for s in operational if s["status"] == "failed"), None)
    if failed:
        return f"Stopped at {failed['name']}. {failed.get('error', {}).get('message') or 'See details.'}"
    if running:
        return (
            f"Journey is progressing. {len(completed)} of {len(operational)} active agents completed. "
            f"Currently: {running['name']}."
        )
    if len(completed) == len(operational) and operational:
        return (
            f"{len(completed)} of {len(operational)} active agents completed. "
            "Remaining pipeline stages are in development."
        )
    return "Journey is queued."


def start_execution_async(execution_id: str) -> None:
    thread = threading.Thread(target=run_execution, args=(execution_id,), daemon=True)
    thread.start()


def run_execution(execution_id: str) -> None:
    record = _load_execution(execution_id)
    if record is None:
        return
    payload = record["payload"]
    _active[execution_id] = "running"
    _update_execution(execution_id, status="running", current_stage="intent-recognition")
    _append_event(
        execution_id,
        agent_id="request",
        event_type="flow_started",
        status="running",
        message="Flow started",
        payload={"request": record["request_text"], "channel": record["channel"]},
    )
    started = time.perf_counter()
    runtime_mode = None
    try:
        state = _make_state(
            raw_text=record["request_text"],
            channel_hint=record["channel"] or "asknow",
        )
        state.execution.run_id = uuid4()
        llm_client, runtime_mode, model_name = build_llm_client("intent")
        _update_execution(execution_id, runtime_mode=runtime_mode)
        payload["runtime_mode"] = runtime_mode
        payload["llm_model"] = model_name

        # --- Intent ---
        _set_stage(payload, "intent-recognition", status="running")
        _persist_payload(execution_id, payload, current_stage="intent-recognition")
        _append_event(
            execution_id,
            agent_id="intent-recognition",
            event_type="stage_started",
            status="running",
            message="Request received",
        )
        intent_input = {
            "utterance": record["request_text"],
            "channel": record["channel"],
        }
        t0 = time.perf_counter()
        intent_agent = IntentRecognitionAgent(
            llm_client=llm_client,
            settings=IntentAgentSettings(prompt_version=INTENT_PROMPT_VERSION),
        )
        _append_event(
            execution_id,
            agent_id="intent-recognition",
            event_type="processing",
            status="running",
            message="Intent classification started",
        )
        state, proposal, gate = run_intent_stage(
            state, agent=intent_agent, registry=IntentRegistry(), model_name=model_name
        )
        intent_ms = int((time.perf_counter() - t0) * 1000)
        intent_output = proposal.model_dump(mode="json")
        gate_dump = gate.model_dump(mode="json")
        _append_event(
            execution_id,
            agent_id="intent-recognition",
            event_type="processing",
            status="running",
            message="Entity extraction completed",
        )
        _append_event(
            execution_id,
            agent_id="intent-recognition",
            event_type="processing",
            status="running",
            message="Confidence calculated",
        )
        accepted = gate.is_accepted()
        _set_stage(
            payload,
            "intent-recognition",
            status="completed" if accepted else "failed",
            duration_ms=intent_ms,
            input=intent_input,
            output={
                "proposal": intent_output,
                "gate": gate_dump,
                "human": {
                    "intent": proposal.user_intent,
                    "confidence": proposal.confidence,
                    "entities": [e.model_dump(mode="json") for e in proposal.entities],
                    "gate": gate.verdict.value,
                },
            },
            error=None
            if accepted
            else {
                "type": "intent_gate_rejection",
                "message": "; ".join(gate.reasons) or "Intent was not accepted.",
                "severity": "high",
                "recovery": "Clarify the request or choose a supported journey.",
            },
        )
        _append_event(
            execution_id,
            agent_id="intent-recognition",
            event_type="stage_completed" if accepted else "stage_failed",
            status="completed" if accepted else "failed",
            message="Intent validated" if accepted else "Intent was not accepted",
            duration_ms=intent_ms,
            payload={"intent": proposal.user_intent, "confidence": proposal.confidence},
        )
        if not accepted:
            payload["business_summary"] = _business_progress(payload)
            _fail_flow(execution_id, payload, "intent-recognition", started)
            return

        # --- Platform capability ---
        _set_stage(payload, "platform-capability", status="running")
        _persist_payload(execution_id, payload, current_stage="platform-capability")
        _append_event(
            execution_id,
            agent_id="platform-capability",
            event_type="stage_started",
            status="running",
            message="Checking whether this platform can support the journey",
        )
        t0 = time.perf_counter()
        try:
            cap = run_capability_check(gate.accepted_intent)
            cap_ms = int((time.perf_counter() - t0) * 1000)
            cap_failed = cap.status in {"not_supported", "unknown_platform"}
            _set_stage(
                payload,
                "platform-capability",
                status="failed" if cap_failed else ("warning" if cap.status != "fully_supported" else "completed"),
                duration_ms=cap_ms,
                input={
                    "platform": cap.platform,
                    "required_capabilities": cap.requested_capabilities,
                    "intent": cap.user_intent,
                },
                output={
                    "raw": cap.raw,
                    "human": {
                        "platform": cap.platform,
                        "status": cap.status,
                        "supported": cap.supported,
                        "supported_capabilities": cap.supported_capabilities,
                        "unsupported_capabilities": cap.unsupported_capabilities,
                        "confidence": cap.confidence,
                    },
                },
                error={
                    "type": "unsupported_capability",
                    "message": f"Platform verdict: {cap.status}",
                    "severity": "high" if cap_failed else "medium",
                    "recovery": "Choose a supported platform or reduce required capabilities.",
                }
                if cap_failed or cap.unsupported_capabilities
                else None,
            )
            _append_event(
                execution_id,
                agent_id="platform-capability",
                event_type="stage_completed" if not cap_failed else "stage_failed",
                status="completed" if not cap_failed else "failed",
                message=f"Platform {cap.platform}: {cap.status}",
                duration_ms=cap_ms,
                payload=cap.raw,
            )
            if cap_failed:
                payload["business_summary"] = _business_progress(payload)
                _fail_flow(execution_id, payload, "platform-capability", started)
                return
        except (CapabilityCheckError, KeyError) as exc:
            cap_ms = int((time.perf_counter() - t0) * 1000)
            _set_stage(
                payload,
                "platform-capability",
                status="failed",
                duration_ms=cap_ms,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "severity": "high",
                    "recovery": "Verify the intent has a capability mapping and knowledge files are present.",
                },
            )
            payload["business_summary"] = _business_progress(payload)
            _fail_flow(execution_id, payload, "platform-capability", started)
            return

        # --- Knowledge ---
        _set_stage(payload, "knowledge-repository", status="running")
        _persist_payload(execution_id, payload, current_stage="knowledge-repository")
        _append_event(
            execution_id,
            agent_id="knowledge-repository",
            event_type="stage_started",
            status="running",
            message="Searching the knowledge repository",
        )
        t0 = time.perf_counter()
        retrieval = retrieve_pack(
            utterance=record["request_text"],
            platform=gate.accepted_intent.platform.value,
            intent=gate.accepted_intent.user_intent,
        )
        know_ms = int((time.perf_counter() - t0) * 1000)
        pack = retrieval["pack"]
        state.business.knowledge = pack
        state.execution.gates.knowledge_gate = "passed"
        _set_stage(
            payload,
            "knowledge-repository",
            status="completed",
            duration_ms=know_ms,
            input={
                "query": record["request_text"],
                "intent": gate.accepted_intent.user_intent,
                "platform": gate.accepted_intent.platform.value,
                "method": retrieval["retrieval_method"],
            },
            output={
                "pack": pack.model_dump(mode="json"),
                "human": {
                    "documents_retrieved": retrieval["documents_retrieved"],
                    "documents_considered": retrieval["documents_considered"],
                    "embedding_used": retrieval["embedding_used"],
                    "missing": [m.model_dump(mode="json") for m in pack.missing_knowledge],
                },
            },
        )
        _append_event(
            execution_id,
            agent_id="knowledge-repository",
            event_type="stage_completed",
            status="completed",
            message=f"Retrieved {retrieval['documents_retrieved']} documents (keyword search)",
            duration_ms=know_ms,
            payload={
                "documents_retrieved": retrieval["documents_retrieved"],
                "embedding_used": False,
            },
        )

        # --- Planner ---
        _set_stage(payload, "journey-planner", status="running")
        _persist_payload(execution_id, payload, current_stage="journey-planner")
        _append_event(
            execution_id,
            agent_id="journey-planner",
            event_type="stage_started",
            status="running",
            message="Planning the journey from intent and knowledge",
        )
        skeleton = generic_skeleton(gate.accepted_intent)
        state.business.planning.skeleton_id = skeleton.skeleton_id
        state.execution.config_snapshot.planner_prompt_version = PLANNER_PROMPT_VERSION
        planner_client, planner_runtime, planner_model = build_llm_client("planner")
        runtime_mode = planner_runtime
        t0 = time.perf_counter()
        planner_agent = JourneyPlannerAgent(
            llm_client=planner_client,
            settings=PlannerAgentSettings(prompt_version=PLANNER_PROMPT_VERSION),
        )
        state, planner_output = run_planning_stage(
            state, agent=planner_agent, skeleton=skeleton, model_name=planner_model
        )
        plan_ms = int((time.perf_counter() - t0) * 1000)
        planner_failed = planner_output.planner_status.value == "failed" if hasattr(planner_output.planner_status, "value") else planner_output.planner_status == "failed"
        plan_dump = planner_output.model_dump(mode="json")
        _set_stage(
            payload,
            "journey-planner",
            status="failed" if planner_failed else "completed",
            duration_ms=plan_ms,
            input={
                "intent": gate.accepted_intent.user_intent,
                "journey_version": skeleton.version,
                "skeleton_id": skeleton.skeleton_id,
                "knowledge_pack_id": pack.pack_id,
            },
            output={
                "plan": plan_dump,
                "human": {
                    "planner_status": plan_dump.get("planner_status"),
                    "ordered_step_ids": plan_dump.get("ordered_step_ids"),
                    "assumptions": plan_dump.get("assumptions"),
                    "unknown_requirements": plan_dump.get("unknown_requirements"),
                    "screens": plan_dump.get("ordered_step_ids"),
                },
            },
            error=(
                {
                    "type": "planner_failed",
                    "message": (plan_dump.get("error") or {}).get("message")
                    or "Planner returned failed status.",
                    "severity": "high",
                    "recovery": "Review knowledge gaps and retry.",
                }
                if planner_failed
                else None
            ),
        )
        _append_event(
            execution_id,
            agent_id="journey-planner",
            event_type="stage_completed" if not planner_failed else "stage_failed",
            status="completed" if not planner_failed else "failed",
            message=f"Planner status: {plan_dump.get('planner_status')}",
            duration_ms=plan_ms,
            payload={"planner_status": plan_dump.get("planner_status")},
        )
        if planner_failed:
            payload["business_summary"] = _business_progress(payload)
            _fail_flow(execution_id, payload, "journey-planner", started)
            return

        for agent in AGENT_CATALOG:
            if agent.lifecycle == "in_development":
                _set_stage(
                    payload,
                    agent.agent_id,
                    status="not_implemented",
                    note="In development — runtime not available.",
                )
                _append_event(
                    execution_id,
                    agent_id=agent.agent_id,
                    event_type="stage_skipped",
                    status="not_implemented",
                    message=f"{agent.name} is in development",
                )

        payload["business_summary"] = _business_progress(payload)
        payload["state"] = json.loads(state.model_dump_json())
        duration_ms = int((time.perf_counter() - started) * 1000)
        _persist_payload(
            execution_id,
            payload,
            current_stage="journey-planner",
            status="completed",
            ended_at=_utcnow(),
            duration_ms=duration_ms,
            runtime_mode=runtime_mode,
        )
        _append_event(
            execution_id,
            agent_id=None,
            event_type="flow_completed",
            status="completed",
            message="Active agents completed. Later stages are in development.",
            duration_ms=duration_ms,
        )
        _publish(execution_id, {"event_type": "done", "status": "completed"})
    except Exception as exc:  # noqa: BLE001
        payload.setdefault("stages", _init_stages())
        err = {
            "type": type(exc).__name__,
            "message": str(exc),
            "severity": "critical",
            "recovery": "Retry the flow or inspect the trace.",
            "stack": traceback.format_exc(),
        }
        current = record.get("current_stage") or "intent-recognition"
        _set_stage(payload, current, status="failed", error=err)
        payload["business_summary"] = f"The flow stopped unexpectedly: {exc}"
        duration_ms = int((time.perf_counter() - started) * 1000)
        _update_execution(
            execution_id,
            status="failed",
            failed_agent_id=current,
            ended_at=_utcnow(),
            duration_ms=duration_ms,
            error_summary=str(exc),
            payload=dumps(payload),
            runtime_mode=runtime_mode,
        )
        _append_event(
            execution_id,
            agent_id=current,
            event_type="flow_failed",
            status="failed",
            message=str(exc),
            payload=err,
        )
        _publish(execution_id, {"event_type": "done", "status": "failed"})
    finally:
        _active.pop(execution_id, None)


def _persist_payload(execution_id: str, payload: dict[str, Any], **fields: Any) -> None:
    payload["business_summary"] = _business_progress(payload)
    extras = {k: v for k, v in fields.items()}
    extras["payload"] = dumps(payload)
    _update_execution(execution_id, **extras)


def _fail_flow(execution_id: str, payload: dict[str, Any], agent_id: str, started: float) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    stage = next((s for s in payload["stages"] if s["agent_id"] == agent_id), {})
    error = stage.get("error") or {}
    _update_execution(
        execution_id,
        status="failed",
        current_stage=agent_id,
        failed_agent_id=agent_id,
        ended_at=_utcnow(),
        duration_ms=duration_ms,
        error_summary=error.get("message"),
        payload=dumps(payload),
    )
    _append_event(
        execution_id,
        agent_id=agent_id,
        event_type="flow_failed",
        status="failed",
        message=error.get("message") or "Flow failed",
        payload=error,
    )
    _publish(execution_id, {"event_type": "done", "status": "failed"})


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def metrics_for_agent(agent_id: str) -> dict[str, Any]:
    """Compute metrics strictly from stored live/demo executions. Empty → unavailable."""
    with db() as conn:
        rows = conn.execute("SELECT payload, status, mode FROM executions").fetchall()
        active = conn.execute(
            """
            SELECT COUNT(*) AS n FROM executions
            WHERE status IN ('queued', 'running') AND current_stage = ?
            """,
            (agent_id,),
        ).fetchone()["n"]
    latencies: list[float] = []
    success = 0
    failure = 0
    total = 0
    for row in rows:
        payload = loads(row["payload"], {})
        for stage in payload.get("stages", []):
            if stage.get("agent_id") != agent_id:
                continue
            if stage.get("status") in {"not_started", "not_implemented", None}:
                continue
            total += 1
            if stage.get("duration_ms") is not None:
                latencies.append(float(stage["duration_ms"]))
            if stage.get("status") in {"completed", "warning"}:
                success += 1
            elif stage.get("status") == "failed":
                failure += 1
    with db() as conn:
        last = conn.execute(
            "SELECT started_at FROM executions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_at = last["started_at"] if last else None
    if total == 0:
        return {
            "active_executions": active,
            "total_executions": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": None,
            "failure_rate": None,
            "average_latency_ms": None,
            "p50_latency_ms": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "last_execution_at": None,
            "availability": "unavailable",
            "note": "No executions recorded yet. Telemetry unavailable.",
            "includes_demo": False,
        }
    return {
        "active_executions": active,
        "total_executions": total,
        "success_count": success,
        "failure_count": failure,
        "success_rate": round(100.0 * success / total, 1) if total else None,
        "failure_rate": round(100.0 * failure / total, 1) if total else None,
        "average_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p50_latency_ms": round(percentile(latencies, 50), 1) if latencies else None,
        "p95_latency_ms": round(percentile(latencies, 95), 1) if latencies else None,
        "p99_latency_ms": round(percentile(latencies, 99), 1) if latencies else None,
        "last_execution_at": last_at,
        "availability": "live",
        "note": "Figures include DEMO MODE runs." if any(row["mode"] == "demo" for row in rows) else None,
            "includes_demo": any(row["mode"] == "demo" for row in rows),
    }


def overview_stats() -> dict[str, Any]:
    with db() as conn:
        exec_rows = conn.execute("SELECT status, duration_ms, mode FROM executions").fetchall()
        error_rows = conn.execute(
            """
            SELECT execution_id, failed_agent_id, error_summary, ended_at, flow_id, status
            FROM executions WHERE status = 'failed' ORDER BY id DESC LIMIT 8
            """
        ).fetchall()
        active = conn.execute(
            "SELECT COUNT(*) AS n FROM executions WHERE status IN ('queued','running')"
        ).fetchone()["n"]
    total = len(exec_rows)
    success = sum(1 for r in exec_rows if r["status"] == "completed")
    failed = sum(1 for r in exec_rows if r["status"] == "failed")
    durations = [r["duration_ms"] for r in exec_rows if r["duration_ms"] is not None]
    return {
        "active_executions": active,
        "successful_executions": success,
        "failed_executions": failed,
        "total_executions": total,
        "average_execution_time_ms": round(sum(durations) / len(durations), 1) if durations else None,
        "telemetry_available": total > 0,
        "recent_errors": [
            {
                "execution_id": r["execution_id"],
                "flow_id": r["flow_id"],
                "agent_id": r["failed_agent_id"],
                "message": r["error_summary"],
                "at": r["ended_at"],
            }
            for r in error_rows
        ],
    }
