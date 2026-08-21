"""HTTP routes for the AgentOps Control Center."""

from __future__ import annotations

import json
import queue
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agentops_api.db import db, dumps, loads, row_to_dict
from agentops_api.health import agent_runtime_health, process_uptime_seconds, system_health
from agentops_api.knowledge import (
    document_preview,
    repository_stats,
    save_upload,
    scan_bundled_documents,
)
from agentops_api.registry import (
    AGENT_CATALOG,
    STATUS_LABELS,
    WORKFLOW_ANCHORS,
    catalog_by_id,
    empty_metrics,
)
from agentops_api.security import (
    decode_session_token,
    has_permission,
    hash_password,
    issue_session_token,
    verify_password,
)
from agentops_api.workflow import (
    create_execution,
    get_execution,
    list_executions,
    metrics_for_agent,
    overview_stats,
    start_execution_async,
    subscribe,
    unsubscribe,
)

router = APIRouter()


class LoginBody(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserCreateBody(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=10)
    display_name: str = Field(min_length=1)
    role: str


class UserUpdateBody(BaseModel):
    role: str | None = None
    status: str | None = None
    display_name: str | None = None
    password: str | None = None


class ExecutionCreateBody(BaseModel):
    request_text: str = Field(min_length=1, max_length=4000)
    channel: str = Field(default="asknow")
    mode: str = Field(default="live")
    environment: str = Field(default="local")


class ApprovalBody(BaseModel):
    decision: str
    comment: str | None = None


class ReplayBody(BaseModel):
    mode: str = Field(default="live")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def audit(
    *,
    user: dict[str, Any] | None,
    action: str,
    resource: str | None,
    result: str,
    request: Request | None = None,
    trace_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs (at, user_id, username, action, resource, result, ip, session_jti, trace_id, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utcnow(),
                user.get("id") if user else None,
                user.get("username") if user else None,
                action,
                resource,
                result,
                _client_ip(request) if request else None,
                user.get("jti") if user else None,
                trace_id,
                dumps(detail or {}),
            ),
        )


def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("agentops_session")
    payload = decode_session_token(token or "")
    if not payload:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ? AND status = 'active'",
            (payload["sub"],),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="This account is no longer active.")
    user = row_to_dict(row) or {}
    user["jti"] = payload.get("jti")
    user.pop("password_hash", None)
    return user


def require(permission: str):
    def dependency(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not has_permission(user["role"], permission):
            raise HTTPException(status_code=403, detail="You do not have permission for this action.")
        return user

    return dependency


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
        "status": user.get("status", "active"),
        "last_login_at": user.get("last_login_at"),
        "created_at": user.get("created_at"),
    }


@router.post("/auth/login")
def login(body: LoginBody, request: Request) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (body.username.strip(),)
        ).fetchone()
    user = row_to_dict(row)
    if not user or not verify_password(body.password, user["password_hash"]):
        audit(user=None, action="login", resource=body.username, result="failure", request=request)
        raise HTTPException(status_code=401, detail="User ID or password is incorrect.")
    if user["status"] != "active":
        audit(user=user, action="login", resource=user["username"], result="denied", request=request)
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    token = issue_session_token(user_id=user["id"], username=user["username"], role=user["role"])
    payload = decode_session_token(token) or {}
    user["jti"] = payload.get("jti")
    with db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (_utcnow(), user["id"]),
        )
    audit(user=user, action="login", resource=user["username"], result="success", request=request)
    return {"token": token, "user": public_user(user)}


@router.post("/auth/logout")
def logout(
    request: Request, user: dict[str, Any] = Depends(get_current_user)
) -> dict[str, str]:
    audit(user=user, action="logout", resource=user["username"], result="success", request=request)
    return {"status": "signed_out"}


@router.get("/auth/me")
def me(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": public_user(user)}


def _serialize_agent(agent: Any) -> dict[str, Any]:
    runtime = agent_runtime_health(agent.agent_id)
    if agent.lifecycle == "in_development":
        metrics = empty_metrics()
    else:
        metrics = metrics_for_agent(agent.agent_id)
    status = runtime.get("status", "UNKNOWN")
    return {
        **agent.model_dump(),
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "health": runtime,
        "metrics": metrics,
        "last_heartbeat": runtime.get("last_heartbeat"),
        "uptime_seconds": runtime.get("uptime_seconds"),
        "environment": agent.environment,
    }


@router.get("/overview")
def overview(user: dict[str, Any] = Depends(require("dashboard.read"))) -> dict[str, Any]:
    agents = [_serialize_agent(a) for a in AGENT_CATALOG]
    operational = [a for a in agents if a["lifecycle"] == "operational"]
    health_counts = {
        "healthy": sum(1 for a in operational if a["status"] == "HEALTHY"),
        "degraded": sum(1 for a in operational if a["status"] == "DEGRADED"),
        "offline": sum(1 for a in operational if a["status"] in {"OFFLINE", "FAILED"}),
        "unknown": sum(1 for a in operational if a["status"] == "UNKNOWN"),
        "in_development": sum(1 for a in agents if a["lifecycle"] == "in_development"),
        "online": sum(1 for a in operational if a["status"] in {"HEALTHY", "IDLE", "RUNNING", "DEGRADED"}),
    }
    sys_health = system_health()
    stats = overview_stats()
    overall = sys_health["overall"]
    if health_counts["offline"]:
        overall = "unavailable"
    elif health_counts["degraded"] or sys_health["overall"] == "degraded":
        overall = "degraded"
    elif health_counts["healthy"] == len(operational) and operational:
        overall = "healthy"
    return {
        "title": "AgentOps Control Center",
        "overall_health": overall,
        "overall_health_label": {
            "healthy": "Healthy",
            "degraded": "Needs attention",
            "unavailable": "Unavailable",
        }.get(overall, overall),
        "agent_counts": {
            "total": len(agents),
            "operational": len(operational),
            **health_counts,
        },
        "executions": stats,
        "uptime_seconds": process_uptime_seconds(),
        "workflow": _workflow_stages(),
        "recent_errors": stats["recent_errors"],
        "system": sys_health,
    }


@router.get("/workflow")
def workflow_graph(user: dict[str, Any] = Depends(require("dashboard.read"))) -> dict[str, Any]:
    return {"stages": _workflow_stages()}


def _workflow_stages() -> list[dict[str, Any]]:
    stages = []
    for anchor in WORKFLOW_ANCHORS:
        if anchor["pipeline_order"] == 0:
            stages.append({**anchor, "status": "HEALTHY", "status_label": "Start"})
    for agent in AGENT_CATALOG:
        runtime = agent_runtime_health(agent.agent_id)
        stages.append(
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "pipeline_order": agent.pipeline_order,
                "kind": "agent",
                "lifecycle": agent.lifecycle,
                "status": runtime.get("status"),
                "status_label": STATUS_LABELS.get(runtime.get("status", ""), runtime.get("status")),
                "note": runtime.get("note"),
            }
        )
    for anchor in WORKFLOW_ANCHORS:
        if anchor["pipeline_order"] != 0:
            stages.append(
                {
                    **anchor,
                    "status": "IN_DEVELOPMENT",
                    "status_label": "In development",
                }
            )
    stages.sort(key=lambda s: s["pipeline_order"])
    return stages


@router.get("/agents")
def list_agents(user: dict[str, Any] = Depends(require("agents.read"))) -> dict[str, Any]:
    return {"agents": [_serialize_agent(a) for a in AGENT_CATALOG]}


@router.get("/agents/{agent_id}")
def agent_detail(agent_id: str, user: dict[str, Any] = Depends(require("agents.read"))) -> dict[str, Any]:
    agent = catalog_by_id().get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="That agent is not registered.")
    serialized = _serialize_agent(agent)
    latest = None
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM executions ORDER BY id DESC LIMIT 40"
        ).fetchall()
    for row in rows:
        payload = loads(row["payload"], {})
        for stage in payload.get("stages", []):
            if stage.get("agent_id") == agent_id and stage.get("status") not in {
                "not_started",
                "not_implemented",
                None,
            }:
                latest = {
                    "flow_id": row["flow_id"],
                    "execution_id": row["execution_id"],
                    "trace_id": row["trace_id"],
                    "status": stage.get("status"),
                    "started_at": row["started_at"],
                    "duration_ms": stage.get("duration_ms"),
                    "input": stage.get("input"),
                    "output": stage.get("output"),
                    "error": stage.get("error"),
                    "mode": row["mode"],
                }
                break
        if latest:
            break
    serialized["latest_execution"] = latest
    serialized["recent_errors"] = _agent_errors(agent_id)
    return serialized


def _agent_errors(agent_id: str) -> list[dict[str, Any]]:
    items = []
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM executions WHERE failed_agent_id = ? ORDER BY id DESC LIMIT 20",
            (agent_id,),
        ).fetchall()
    for row in rows:
        payload = loads(row["payload"], {})
        stage = next((s for s in payload.get("stages", []) if s.get("agent_id") == agent_id), {})
        error = stage.get("error") or {}
        items.append(
            {
                "flow_id": row["flow_id"],
                "execution_id": row["execution_id"],
                "trace_id": row["trace_id"],
                "at": row["ended_at"] or row["started_at"],
                "type": error.get("type"),
                "message": error.get("message") or row["error_summary"],
                "severity": error.get("severity"),
                "recovery": error.get("recovery"),
                "mode": row["mode"],
            }
        )
    return items


@router.get("/executions")
def executions(
    status: str | None = None,
    agent: str | None = None,
    user_filter: str | None = Query(default=None, alias="user"),
    environment: str | None = None,
    user: dict[str, Any] = Depends(require("executions.read")),
) -> dict[str, Any]:
    items = list_executions(
        {
            "status": status,
            "agent": agent,
            "user": user_filter,
            "environment": environment,
        }
    )
    return {"executions": items}


@router.post("/executions")
def create_flow(
    body: ExecutionCreateBody,
    request: Request,
    user: dict[str, Any] = Depends(require("executions.create")),
) -> dict[str, Any]:
    if body.mode not in {"live", "demo"}:
        raise HTTPException(status_code=400, detail="Mode must be live or demo.")
    record = create_execution(
        request_text=body.request_text.strip(),
        channel=body.channel.strip() or "asknow",
        username=user["username"],
        user_id=user["id"],
        mode=body.mode,
        environment=body.environment,
    )
    start_execution_async(record["execution_id"])
    audit(
        user=user,
        action="workflow.start",
        resource=record["flow_id"],
        result="success",
        request=request,
        trace_id=record["trace_id"],
        detail={"mode": body.mode, "channel": body.channel},
    )
    return record


@router.get("/executions/{execution_id}")
def execution_detail(
    execution_id: str, user: dict[str, Any] = Depends(require("executions.read"))
) -> dict[str, Any]:
    record = get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="That execution was not found.")
    return record


@router.get("/executions/{execution_id}/events")
def execution_events(
    execution_id: str, user: dict[str, Any] = Depends(require("executions.read"))
) -> StreamingResponse:
    record = get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="That execution was not found.")

    def generate():
        q = subscribe(record["execution_id"])
        try:
            snapshot = get_execution(record["execution_id"])
            yield f"data: {json.dumps({'event_type': 'snapshot', 'execution': snapshot})}\n\n"
            if snapshot and snapshot.get("status") in {"completed", "failed"}:
                yield f"data: {json.dumps({'event_type': 'done', 'status': snapshot['status']})}\n\n"
                return
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    yield "data: {\"event_type\": \"heartbeat\"}\n\n"
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("event_type") == "done":
                    break
        finally:
            unsubscribe(record["execution_id"], q)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/executions/{execution_id}/retry")
def retry_execution(
    execution_id: str,
    request: Request,
    user: dict[str, Any] = Depends(require("executions.retry")),
) -> dict[str, Any]:
    original = get_execution(execution_id)
    if original is None:
        raise HTTPException(status_code=404, detail="That execution was not found.")
    if original["status"] != "failed":
        raise HTTPException(status_code=400, detail="Only failed executions can be retried.")
    record = create_execution(
        request_text=original["request_text"],
        channel=original["channel"] or "asknow",
        username=user["username"],
        user_id=user["id"],
        mode=original["mode"],
        parent_trace_id=original["trace_id"],
        environment=original["environment"],
    )
    start_execution_async(record["execution_id"])
    audit(
        user=user,
        action="workflow.retry",
        resource=record["flow_id"],
        result="success",
        request=request,
        trace_id=record["trace_id"],
        detail={"original_trace_id": original["trace_id"]},
    )
    return record


@router.post("/executions/{execution_id}/replay")
def replay_execution(
    execution_id: str,
    body: ReplayBody,
    request: Request,
    user: dict[str, Any] = Depends(require("executions.retry")),
) -> dict[str, Any]:
    original = get_execution(execution_id)
    if original is None:
        raise HTTPException(status_code=404, detail="That execution was not found.")
    record = create_execution(
        request_text=original["request_text"],
        channel=original["channel"] or "asknow",
        username=user["username"],
        user_id=user["id"],
        mode=body.mode,
        replay_of=original["execution_id"],
        parent_trace_id=original["trace_id"],
        environment=original["environment"],
    )
    start_execution_async(record["execution_id"])
    audit(
        user=user,
        action="workflow.replay",
        resource=record["flow_id"],
        result="success",
        request=request,
        trace_id=record["trace_id"],
        detail={
            "original_trace_id": original["trace_id"],
            "note": "This is a new execution based on a previous input.",
        },
    )
    return record


@router.post("/executions/{execution_id}/approval")
def approve_execution(
    execution_id: str,
    body: ApprovalBody,
    request: Request,
    user: dict[str, Any] = Depends(require("executions.approve")),
) -> dict[str, Any]:
    if body.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected.")
    record = get_execution(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="That execution was not found.")
    with db() as conn:
        conn.execute(
            "UPDATE executions SET approval_status = ?, approval_comment = ? WHERE execution_id = ?",
            (body.decision, body.comment, record["execution_id"]),
        )
    audit(
        user=user,
        action="workflow.approve" if body.decision == "approved" else "workflow.reject",
        resource=record["flow_id"],
        result="success",
        request=request,
        trace_id=record["trace_id"],
        detail={"comment": body.comment},
    )
    return get_execution(execution_id) or {}


@router.get("/health")
def health(user: dict[str, Any] = Depends(require("health.read"))) -> dict[str, Any]:
    data = system_health()
    data["agents"] = [
        {
            "agent_id": a.agent_id,
            "name": a.name,
            **agent_runtime_health(a.agent_id),
        }
        for a in AGENT_CATALOG
    ]
    return data


@router.get("/incidents")
def incidents(user: dict[str, Any] = Depends(require("executions.read"))) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT failed_agent_id AS agent_id, COUNT(*) AS failure_count,
                   MIN(started_at) AS first_seen, MAX(ended_at) AS last_seen,
                   MAX(error_summary) AS sample_message,
                   MAX(execution_id) AS sample_execution_id
            FROM executions
            WHERE status = 'failed' AND failed_agent_id IS NOT NULL
            GROUP BY failed_agent_id
            ORDER BY failure_count DESC
            """
        ).fetchall()
        recent = conn.execute(
            """
            SELECT flow_id, execution_id, failed_agent_id, error_summary, ended_at, status, mode
            FROM executions WHERE status = 'failed' ORDER BY id DESC LIMIT 25
            """
        ).fetchall()
    grouped = []
    for row in rows:
        grouped.append(
            {
                "incident_id": f"INC-{(row['agent_id'] or 'unknown').upper()}",
                "agent_id": row["agent_id"],
                "title": f"{catalog_by_id().get(row['agent_id']).name if catalog_by_id().get(row['agent_id']) else row['agent_id']} — repeated failures",
                "severity": "high" if row["failure_count"] >= 3 else "medium",
                "status": "open",
                "failure_count": row["failure_count"],
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
                "sample_message": row["sample_message"],
                "sample_execution_id": row["sample_execution_id"],
            }
        )
    return {
        "incidents": grouped,
        "recent_failures": [dict(r) for r in recent],
        "note": None if grouped else "No failures have been recorded yet.",
    }


@router.get("/knowledge/stats")
def knowledge_stats(user: dict[str, Any] = Depends(require("knowledge.read"))) -> dict[str, Any]:
    with db() as conn:
        uploaded = [row_to_dict(r) for r in conn.execute("SELECT * FROM documents").fetchall()]
    return repository_stats(uploaded_rows=[u for u in uploaded if u])


@router.get("/knowledge/documents")
def knowledge_documents(
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
    user: dict[str, Any] = Depends(require("knowledge.read")),
) -> dict[str, Any]:
    bundled = scan_bundled_documents()
    with db() as conn:
        uploaded = [row_to_dict(r) or {} for r in conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()]
    docs = bundled + uploaded
    if q:
        needle = q.lower()
        docs = [d for d in docs if needle in (d.get("file_name") or "").lower() or needle in (d.get("category") or "").lower()]
    if status:
        docs = [d for d in docs if d.get("status") == status]
    if category:
        docs = [d for d in docs if d.get("category") == category]
    return {"documents": docs, "count": len(docs)}


@router.get("/knowledge/documents/{document_id}")
def knowledge_document(
    document_id: str, user: dict[str, Any] = Depends(require("knowledge.read"))
) -> dict[str, Any]:
    bundled = scan_bundled_documents()
    match = next((d for d in bundled if d["document_id"] == document_id), None)
    if match:
        preview = document_preview(match["source_path"])
        return {**match, "preview": preview, "history": [{"at": match["uploaded_at"], "event": "indexed", "actor": "knowledge-base"}]}
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="That document was not found.")
    data = row_to_dict(row) or {}
    data["history"] = loads(data.get("history"), [])
    if data.get("source_path") and data.get("file_type") in {"md", "txt"}:
        try:
            data["preview"] = document_preview(data["source_path"])
        except (OSError, PermissionError, FileNotFoundError):
            data["preview"] = {"preview_available": False, "reason": "Preview is not available."}
    return data


@router.post("/knowledge/documents")
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require("knowledge.write")),
) -> dict[str, Any]:
    content = file.file.read()
    dest = save_upload(file.filename or "document", content, user["username"])
    document_id = f"UPL-{uuid4().hex[:10].upper()}"
    now = _utcnow()
    suffix = dest.suffix.lower().lstrip(".")
    history = [
        {"at": now, "event": "upload", "actor": user["username"]},
        {"at": now, "event": "parse", "actor": "system"},
        {"at": now, "event": "chunk", "actor": "system"},
        {"at": now, "event": "tag", "actor": "system"},
        {"at": now, "event": "version", "actor": "system", "version": "1.0"},
        {"at": now, "event": "embed", "actor": "system", "status": "skipped", "note": "Embedding is not instrumented."},
        {"at": now, "event": "index", "actor": "system"},
        {"at": now, "event": "approve", "actor": user["username"]},
        {"at": now, "event": "available", "actor": "system"},
    ]
    with db() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                document_id, file_name, file_type, version, uploaded_at, uploaded_by,
                status, processing_status, indexing_status, size_bytes, page_count,
                category, last_updated, source_path, origin, history
            ) VALUES (?, ?, ?, '1.0', ?, ?, 'indexed', 'complete', 'indexed', ?, ?, 'Uploaded', ?, ?, 'upload', ?)
            """,
            (
                document_id,
                dest.name,
                suffix or "unknown",
                now,
                user["username"],
                dest.stat().st_size,
                max(1, content.count(b"\n") // 40) if suffix in {"md", "txt"} else None,
                now,
                str(dest),
                dumps(history),
            ),
        )
    audit(
        user=user,
        action="document.upload",
        resource=document_id,
        result="success",
        request=request,
        detail={"file_name": dest.name},
    )
    return knowledge_document(document_id, user)


@router.get("/audit")
def audit_logs(
    q: str | None = None,
    action: str | None = None,
    user: dict[str, Any] = Depends(require("audit.read")),
) -> dict[str, Any]:
    sql = "SELECT * FROM audit_logs WHERE 1=1"
    params: list[Any] = []
    if action:
        sql += " AND action = ?"
        params.append(action)
    if q:
        sql += " AND (username LIKE ? OR resource LIKE ? OR action LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY id DESC LIMIT 400"
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["detail"] = loads(item.get("detail"), {})
        items.append(item)
    return {"logs": items}


@router.get("/admin/users")
def list_users(user: dict[str, Any] = Depends(require("users.manage"))) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    return {"users": [public_user(dict(r)) for r in rows]}


@router.post("/admin/users")
def create_user(
    body: UserCreateBody,
    request: Request,
    user: dict[str, Any] = Depends(require("users.manage")),
) -> dict[str, Any]:
    if body.role not in {"super_admin", "approver", "viewer"}:
        raise HTTPException(status_code=400, detail="Role must be super_admin, approver, or viewer.")
    now = _utcnow()
    try:
        with db() as conn:
            conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, role, status, created_at, created_by, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    body.username.strip(),
                    body.display_name.strip(),
                    hash_password(body.password),
                    body.role,
                    now,
                    user["username"],
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (body.username.strip(),)
            ).fetchone()
    except Exception as exc:  # noqa: BLE001
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="That user ID already exists.") from exc
        raise
    created = public_user(dict(row))
    audit(
        user=user,
        action="user.create",
        resource=created["username"],
        result="success",
        request=request,
        detail={"role": body.role},
    )
    return {"user": created}


@router.patch("/admin/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdateBody,
    request: Request,
    user: dict[str, Any] = Depends(require("users.manage")),
) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="That user was not found.")
        fields: dict[str, Any] = {"updated_at": _utcnow()}
        action = "user.modify"
        if body.role:
            if body.role not in {"super_admin", "approver", "viewer"}:
                raise HTTPException(status_code=400, detail="Invalid role.")
            fields["role"] = body.role
            action = "user.role_change"
        if body.status:
            if body.status not in {"active", "disabled"}:
                raise HTTPException(status_code=400, detail="Status must be active or disabled.")
            fields["status"] = body.status
            action = "user.deactivate" if body.status == "disabled" else "user.modify"
        if body.display_name:
            fields["display_name"] = body.display_name
        if body.password:
            fields["password_hash"] = hash_password(body.password)
            action = "user.reset_credentials"
        assignments = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", [*fields.values(), user_id])
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    audit(
        user=user,
        action=action,
        resource=row["username"],
        result="success",
        request=request,
        detail=body.model_dump(exclude_none=True, exclude={"password"}),
    )
    return {"user": public_user(dict(updated))}
