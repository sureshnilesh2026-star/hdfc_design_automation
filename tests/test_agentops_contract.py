"""AgentOps contract, security, and metrics helpers — no fabricated telemetry."""

from __future__ import annotations

from agentops_api.registry import (
    AGENT_CATALOG,
    development_agents,
    empty_metrics,
    operational_agents,
)
from agentops_api.security import hash_password, has_permission, verify_password
from agentops_api.workflow import percentile


def test_four_operational_agents_are_registered() -> None:
    ids = {a.agent_id for a in operational_agents()}
    assert ids == {
        "intent-recognition",
        "platform-capability",
        "knowledge-repository",
        "journey-planner",
    }


def test_future_agents_are_in_development_without_metrics() -> None:
    future = development_agents()
    assert len(future) >= 6
    metrics = empty_metrics()
    assert metrics["success_rate"] is None
    assert metrics["average_latency_ms"] is None
    assert metrics["availability"] == "not_applicable"
    for agent in future:
        assert agent.lifecycle == "in_development"
        assert agent.telemetry == "not_applicable"


def test_catalog_pipeline_order_is_unique_and_sorted() -> None:
    orders = [a.pipeline_order for a in AGENT_CATALOG]
    assert orders == sorted(orders)
    assert len(orders) == len(set(orders))


def test_password_is_hashed_and_verified() -> None:
    stored = hash_password("ChangeMeAdmin!1")
    assert stored.startswith("pbkdf2_sha256$")
    assert "ChangeMeAdmin!1" not in stored
    assert verify_password("ChangeMeAdmin!1", stored)
    assert not verify_password("wrong-password", stored)


def test_rbac_boundaries() -> None:
    assert has_permission("viewer", "dashboard.read")
    assert not has_permission("viewer", "users.manage")
    assert not has_permission("viewer", "executions.create")
    assert has_permission("approver", "executions.approve")
    assert not has_permission("approver", "audit.read")
    assert has_permission("super_admin", "users.manage")
    assert has_permission("super_admin", "audit.read")


def test_percentile_empty_is_none() -> None:
    assert percentile([], 95) is None
    assert percentile([10], 99) == 10
    assert percentile([10, 20, 30, 40], 50) == 25
