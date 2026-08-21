"""AgentOps API smoke tests — auth, RBAC, and registry visibility."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

os.environ.setdefault("AGENTOPS_SECRET_KEY", "test-secret-key-not-for-production")
os.environ["AGENTOPS_DATA_DIR"] = str(Path(__file__).resolve().parent / "_agentops_tmp")
os.environ.setdefault("AGENTOPS_ADMIN_PASSWORD", "ChangeMeAdmin!1")

from fastapi.testclient import TestClient  # noqa: E402

from agentops_api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_login_and_overview_hides_fabricated_metrics(client: TestClient) -> None:
    denied = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert denied.status_code == 401

    ok = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "ChangeMeAdmin!1"},
    )
    assert ok.status_code == 200
    token = ok.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    overview = client.get("/api/overview", headers=headers)
    assert overview.status_code == 200
    body = overview.json()
    assert body["agent_counts"]["operational"] == 4
    assert body["agent_counts"]["in_development"] >= 6
    assert body["executions"]["telemetry_available"] in {True, False}

    agents = client.get("/api/agents", headers=headers).json()["agents"]
    future = next(a for a in agents if a["agent_id"] == "json-compiler")
    assert future["status"] == "IN_DEVELOPMENT"
    assert future["metrics"]["success_rate"] is None
    assert future["metrics"]["average_latency_ms"] is None

    viewer = client.post(
        "/api/auth/login",
        json={"username": "viewer", "password": "ChangeMeViewer!1"},
    )
    vheaders = {"Authorization": f"Bearer {viewer.json()['token']}"}
    blocked = client.post(
        "/api/executions",
        headers=vheaders,
        json={"request_text": "change my address", "channel": "asknow"},
    )
    assert blocked.status_code == 403
