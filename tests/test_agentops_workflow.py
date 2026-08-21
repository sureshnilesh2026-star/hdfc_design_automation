"""Live workflow through operational agents — uses deterministic LLM stand-ins."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

os.environ.setdefault("AGENTOPS_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("HDFC_LLM_PROVIDER", "stub")

from fastapi.testclient import TestClient  # noqa: E402

from agentops_api.main import app  # noqa: E402


def test_live_address_change_flow_reaches_planner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTOPS_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    token = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!1"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/executions",
        headers=headers,
        json={
            "request_text": "I want to change my address",
            "channel": "asknow",
            "mode": "live",
        },
    )
    assert created.status_code == 200
    execution_id = created.json()["execution_id"]
    deadline = time.time() + 30
    record = None
    while time.time() < deadline:
        record = client.get(f"/api/executions/{execution_id}", headers=headers).json()
        if record["status"] in {"completed", "failed"}:
            break
        time.sleep(0.2)
    assert record is not None
    stages = {s["agent_id"]: s for s in record["payload"]["stages"]}
    assert stages["intent-recognition"]["status"] in {"completed", "warning", "failed"}
    assert stages["json-compiler"]["status"] == "not_implemented"
    assert stages["json-compiler"].get("duration_ms") is None
    if record["status"] == "completed":
        assert stages["journey-planner"]["status"] in {"completed", "warning"}
        assert stages["intent-recognition"]["output"]["human"]["intent"]
    else:
        assert record["failed_agent_id"]
        assert record["error_summary"]
