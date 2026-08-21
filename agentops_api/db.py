"""SQLite persistence for AgentOps sessions, executions, audit, and documents."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from agentops_api.config import DATA_DIR, DB_PATH, SEED_USERS, UPLOAD_DIR
from agentops_api.security import hash_password

_lock = threading.Lock()
_initialized = False


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    global _initialized
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    created_by TEXT,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    action TEXT NOT NULL,
                    resource TEXT,
                    result TEXT NOT NULL,
                    ip TEXT,
                    session_jti TEXT,
                    trace_id TEXT,
                    detail TEXT
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flow_id TEXT NOT NULL UNIQUE,
                    execution_id TEXT NOT NULL UNIQUE,
                    trace_id TEXT NOT NULL UNIQUE,
                    parent_trace_id TEXT,
                    user_id INTEGER,
                    username TEXT,
                    request_text TEXT NOT NULL,
                    channel TEXT,
                    environment TEXT NOT NULL DEFAULT 'local',
                    mode TEXT NOT NULL DEFAULT 'live',
                    runtime_mode TEXT,
                    status TEXT NOT NULL,
                    current_stage TEXT,
                    failed_agent_id TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_ms INTEGER,
                    error_summary TEXT,
                    approval_status TEXT,
                    approval_comment TEXT,
                    replay_of TEXT,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    at TEXT NOT NULL,
                    agent_id TEXT,
                    event_type TEXT NOT NULL,
                    status TEXT,
                    message TEXT,
                    duration_ms INTEGER,
                    payload TEXT
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '1.0',
                    uploaded_at TEXT NOT NULL,
                    uploaded_by TEXT,
                    status TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    indexing_status TEXT NOT NULL,
                    size_bytes INTEGER,
                    page_count INTEGER,
                    category TEXT,
                    last_updated TEXT NOT NULL,
                    source_path TEXT,
                    origin TEXT NOT NULL,
                    error_message TEXT,
                    history TEXT
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL UNIQUE,
                    agent_id TEXT,
                    title TEXT NOT NULL,
                    category TEXT,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    failure_count INTEGER NOT NULL DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    resolution TEXT,
                    sample_execution_id TEXT,
                    detail TEXT
                );
                """
            )
            conn.commit()
            _seed_users(conn)
            conn.commit()
        finally:
            conn.close()
        _initialized = True


def _seed_users(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if count:
        return
    now = _utcnow()
    for user in SEED_USERS:
        conn.execute(
            """
            INSERT INTO users (username, display_name, password_hash, role, status,
                               created_at, created_by, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, 'system', ?)
            """,
            (
                user["username"],
                user["display_name"],
                hash_password(user["password"]),
                user["role"],
                now,
                now,
            ),
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def loads(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    return json.loads(value)


def dumps(value: Any) -> str:
    return json.dumps(value, default=str)
