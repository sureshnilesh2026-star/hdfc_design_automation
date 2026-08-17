"""
End-to-end Journey Planner test: UPDATE_ADDRESS / "I want to change my address."

Reproducible: fixed UUIDs, deterministic LLM stand-in that plans from PlannerInput
(not a hard-coded golden answer inside JourneyPlannerAgent).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hdfc_journey.agents.planner.agent import JourneyPlannerAgent
from hdfc_journey.contracts.enums import DecisionKind, PlannerStatus
from hdfc_journey.contracts.validation import validate_planner_output
from hdfc_journey.llm.deterministic_planner import (
    deterministic_planner_llm_handler,
    plan_from_planner_input,
)
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.planning import (
    build_planner_input_from_state,
    run_planning_stage,
)
from tests.fixtures.address_change import (
    USER_UTTERANCE,
    address_change_knowledge_pack,
    address_change_skeleton,
    address_change_state,
)

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "examples" / "e2e_address_change"


@pytest.fixture(scope="module")
def e2e_address_change_run():
    """Run the full planning stage once; reuse for assertions + artifact dumps."""
    state_before = address_change_state()
    skeleton = address_change_skeleton()
    pack = address_change_knowledge_pack()

    stub = StubStructuredClient(deterministic_planner_llm_handler)
    agent = JourneyPlannerAgent(llm_client=stub)

    planner_input = build_planner_input_from_state(state_before, skeleton)
    # Prove stand-in derives from input (same bytes → same plan)
    direct = plan_from_planner_input(planner_input)

    state_after, planner_output = run_planning_stage(
        state_before,
        agent=agent,
        skeleton=skeleton,
        model_name="deterministic-planner-v1",
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    # Fresh fixture snapshot — run_planning_stage mutates the in-memory state object.
    (ARTIFACT_DIR / "01_input_state_pre_planning.json").write_text(
        address_change_state().model_dump_json(indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "02_knowledge_pack.json").write_text(
        pack.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "03_skeleton.json").write_text(
        skeleton.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "04_planner_input.json").write_text(
        planner_input.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "05_planner_output.json").write_text(
        planner_output.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "06_state_after_orchestration.json").write_text(
        state_after.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "07_trace.json").write_text(
        json.dumps(
            [e.model_dump(mode="json") for e in state_after.execution.trace],
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "utterance": USER_UTTERANCE,
        "state_after": state_after,
        "planner_input": planner_input,
        "planner_output": planner_output,
        "skeleton": skeleton,
        "pack": pack,
        "stub": stub,
        "direct": direct,
        "artifact_dir": ARTIFACT_DIR,
    }


def test_e2e_reproducible_and_structured(e2e_address_change_run) -> None:
    out = e2e_address_change_run["planner_output"]
    direct = e2e_address_change_run["direct"]
    stub = e2e_address_change_run["stub"]

    assert out.artifact_type == "journey_plan"
    assert out.schema_version == "1.0.0"
    assert out.planner_ok is True
    assert isinstance(out.model_dump(mode="json"), dict)

    # Same input ⇒ same deterministic plan (reproducibility)
    assert out.model_dump(mode="json") == direct.model_dump(mode="json")
    assert len(stub.calls) == 1
    assert stub.calls[0]["response_model"] == "PlannerOutput"


def test_e2e_selects_and_orders_skeleton_steps(e2e_address_change_run) -> None:
    out = e2e_address_change_run["planner_output"]
    skeleton = e2e_address_change_run["skeleton"]

    required = [s.id for s in sorted(skeleton.steps, key=lambda x: x.ordinal) if not s.optional]
    optional = [s.id for s in skeleton.steps if s.optional]

    assert out.ordered_step_ids == required
    assert set(out.skipped_optional_step_ids) == set(optional)
    assert set(out.ordered_step_ids).isdisjoint(out.skipped_optional_step_ids)
    # Ordering matches skeleton ordinals
    ordinal = {s.id: s.ordinal for s in skeleton.steps}
    assert out.ordered_step_ids == sorted(out.ordered_step_ids, key=lambda i: ordinal[i])
    assert "optional_comm_pref" not in out.ordered_step_ids
    assert "auth_gate" in out.ordered_step_ids
    assert out.ordered_step_ids[0] == "auth_gate"
    assert out.ordered_step_ids[-1] == "review_and_submit"


def test_e2e_binds_entities_and_required_information(e2e_address_change_run) -> None:
    out = e2e_address_change_run["planner_output"]
    inp = e2e_address_change_run["planner_input"]

    accepted_keys = {f"{e.type}:{e.value}" for e in inp.intent_accepted.entities}
    assert out.entity_bindings, "expected entity bindings from accepted entities"
    for binding in out.entity_bindings:
        assert f"{binding.entity_type}:{binding.entity_value}" in accepted_keys
        assert binding.target_step_id in out.ordered_step_ids

    bound_types = {b.entity_type for b in out.entity_bindings}
    assert "customer_id" in bound_types
    assert "address_type" in bound_types

    assert out.required_information, "expected required information from skeleton fields"
    field_ids = {r.id for r in out.required_information}
    assert "address_line_1" in field_ids
    assert "postal_code" in field_ids
    assert "customer_id" in field_ids
    for req in out.required_information:
        assert req.target_step_id in out.ordered_step_ids
        assert req.attributions


def test_e2e_references_pack_and_does_not_invent_facts(e2e_address_change_run) -> None:
    out = e2e_address_change_run["planner_output"]
    inp = e2e_address_change_run["planner_input"]
    pack_docs = inp.knowledge_pack.document_ids()

    assert out.knowledge_references
    assert set(out.knowledge_references) <= pack_docs

    for decision in out.decisions:
        assert set(decision.knowledge_source_ids) <= pack_docs
        assert decision.attributions

    # No invented enterprise API/fee/eligibility claims as knowledge refs
    invented = {
        "TECH-ADDR-UPDATE-APIS",
        "FAKE-FEE-TABLE",
        "FAKE-ELIGIBILITY",
        "POST /v1/address",
    }
    assert invented.isdisjoint(set(out.knowledge_references))

    dumped = json.dumps(out.model_dump(mode="json"))
    assert "POST /" not in dumped
    assert "eligibility approved" not in dumped.lower()
    assert "fee of" not in dumped.lower()

    result = validate_planner_output(out, inp)
    assert result.ok, result.violations


def test_e2e_explicit_assumptions_for_missing_knowledge(e2e_address_change_run) -> None:
    out = e2e_address_change_run["planner_output"]
    pack = e2e_address_change_run["pack"]

    missing_ids = {m.asset_id for m in pack.missing_knowledge}
    assert "TECH-ADDR-UPDATE-APIS" in missing_ids

    assert out.unknown_requirements, "gaps must surface as unknown_requirements"
    assert out.assumptions, "gaps must surface as explicit assumptions"
    assert out.planner_status == PlannerStatus.PLANNED_WITH_UNKNOWNS

    unk_subjects = {u.id for u in out.unknown_requirements} | {
        u.description for u in out.unknown_requirements
    }
    assert any("TECH-ADDR-UPDATE-APIS" in str(x) for x in unk_subjects)
    assert any(a.must_confirm for a in out.assumptions)
    assert any(
        d.kind == DecisionKind.MARK_UNKNOWN_REQUIREMENT for d in out.decisions
    )
    assert any(d.kind == DecisionKind.FLAG_ASSUMPTION for d in out.decisions)


def test_e2e_orchestration_state_and_trace(e2e_address_change_run) -> None:
    state = e2e_address_change_run["state_after"]
    out = e2e_address_change_run["planner_output"]
    pack = e2e_address_change_run["pack"]

    # Blocking TECH-ADDR-UPDATE-APIS + high-risk assumptions → escalate
    assert state.business.status == "escalated"
    assert state.business.hitl.required is True
    assert state.business.output.kind == "escalation"
    assert state.business.intent.accepted is not None
    assert state.business.intent.accepted.user_intent == "UPDATE_ADDRESS"
    assert state.business.intent.accepted.journey_type.value == "servicing"
    assert state.business.intent.accepted.platform.value == "asknow"
    assert state.business.input.normalized.raw_text == USER_UTTERANCE

    # Knowledge unchanged (same pack id)
    assert state.business.knowledge is not None
    assert state.business.knowledge.pack_id == pack.pack_id

    # Planning merged
    assert state.business.planning.ordered_step_ids == out.ordered_step_ids
    assert state.business.planning.decisions
    assert state.business.planning.assumptions
    assert state.business.planning.planner_status == out.planner_status
    assert state.business.planning.router_decision["action"] == "escalate"
    assert state.business.planning.repair_audit["repair_attempted"] is False

    # Forbidden partitions untouched (except HITL/output via Router)
    assert state.business.validation.result == "pending"
    assert state.business.generation.blueprint_final is None
    assert state.execution.gates.intent_gate == "passed"
    assert state.execution.gates.knowledge_gate == "passed"
    assert state.execution.gates.validation_gate == "not_run"

    # Agent metadata + trace
    meta = state.execution.agents.planner
    assert meta.model == "deterministic-planner-v1"
    assert meta.prompt_version == "planner-system-v1"
    assert meta.structured_output_ok is True
    assert meta.latency_ms is not None
    assert meta.repair_pass == 0

    assert state.execution.trace
    planner_events = [
        e for e in state.execution.trace if e.component == "journey_planner_agent"
    ]
    merge_events = [
        e for e in state.execution.trace if e.component == "orchestrator.planning_merge"
    ]
    router_final = [
        e
        for e in state.execution.trace
        if e.component == "orchestrator.router" and e.decision == "router_escalate"
    ]
    assert len(planner_events) == 1
    assert len(merge_events) == 1
    assert len(router_final) == 1
    assert planner_events[0].stage == "planning"
    assert planner_events[0].detail["structured_output_ok"] is True
    assert "latency_ms" in planner_events[0].detail
    assert planner_events[0].evidence_refs
    assert set(planner_events[0].evidence_refs) <= pack.document_ids()

    # Artifacts written for inspection
    artifact_dir = e2e_address_change_run["artifact_dir"]
    for name in (
        "01_input_state_pre_planning.json",
        "02_knowledge_pack.json",
        "04_planner_input.json",
        "05_planner_output.json",
        "06_state_after_orchestration.json",
        "07_trace.json",
    ):
        path = artifact_dir / name
        assert path.is_file(), f"missing artifact {path}"
        assert path.stat().st_size > 0
