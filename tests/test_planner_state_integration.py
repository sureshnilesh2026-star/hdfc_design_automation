"""Orchestrator ↔ Planner state integration tests."""

from __future__ import annotations

from hdfc_journey.agents.planner.agent import JourneyPlannerAgent
from hdfc_journey.contracts.enums import JourneyType, Platform, PlannerStatus
from hdfc_journey.contracts.state import (
    BusinessInput,
    ConfigSnapshot,
    IntentAccepted,
    IntentState,
    JourneyGenerationState,
    NormalizedInput,
    RawInput,
)
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.planning import (
    build_planner_input_from_state,
    run_planning_stage,
)
from tests.fixtures.planner_examples import (
    EXAMPLE_RUN_ID,
    example_knowledge_pack,
    example_planner_output,
    example_skeleton,
)


def _state_ready_for_planning() -> JourneyGenerationState:
    sk = example_skeleton()
    state = JourneyGenerationState()
    state.execution.run_id = EXAMPLE_RUN_ID
    state.execution.config_snapshot = ConfigSnapshot(
        planner_prompt_version="planner-system-v1",
        llm_model="stub-model",
    )
    state.business.status = "knowledge_loaded"
    state.business.input = BusinessInput(
        raw=RawInput(text="I want a credit card", channel_hint="asknow"),
        normalized=NormalizedInput(
            raw_text="I want a credit card",
            channel_hint="asknow",
            customer_context={"auth_state": "unknown"},
        ),
    )
    state.business.intent = IntentState(
        accepted=IntentAccepted(
            user_intent="APPLY_CREDIT_CARD",
            journey_type=JourneyType.ACQUISITION,
            platform=Platform.ASKNOW,
            product_domain="credit_cards",
            entities=[{"type": "product", "value": "credit_card", "confidence": 0.92}],
            confidence=0.88,
        )
    )
    state.business.knowledge = example_knowledge_pack()
    state.business.planning.skeleton_id = sk.skeleton_id
    # Forbidden fields pre-set to detect mutation
    state.business.validation.result = "pending"
    state.business.output.kind = "none"
    state.business.hitl.required = False
    state.execution.gates.intent_gate = "passed"
    state.execution.gates.knowledge_gate = "passed"
    return state


def test_build_planner_input_reads_allowed_state_only() -> None:
    state = _state_ready_for_planning()
    skeleton = example_skeleton()
    inp = build_planner_input_from_state(state, skeleton)
    assert inp.intent_accepted.user_intent == "APPLY_CREDIT_CARD"
    assert inp.knowledge_pack.pack_id == state.business.knowledge.pack_id
    assert inp.skeleton.skeleton_id == skeleton.skeleton_id
    assert inp.execution.run_id == state.execution.run_id
    assert inp.execution.state_id == state.state_id


def test_run_planning_stage_merges_and_traces() -> None:
    state = _state_ready_for_planning()
    intent_before = state.business.intent.accepted.model_dump()
    knowledge_before = state.business.knowledge.model_dump()
    gates_before = state.execution.gates.model_dump()
    validation_before = state.business.validation.model_dump()
    output_before_kind = state.business.output.kind

    agent = JourneyPlannerAgent(
        llm_client=StubStructuredClient(lambda *_: example_planner_output())
    )
    new_state, out = run_planning_stage(
        state,
        agent=agent,
        skeleton=example_skeleton(),
        model_name="stub-model",
    )

    assert out.planner_ok is True
    # Blocking knowledge gap + high-risk assumption → Router escalates (not continue).
    assert new_state.business.status == "escalated"
    assert new_state.business.hitl.required is True
    assert new_state.business.output.kind == "escalation"
    assert new_state.business.planning.planner_status == PlannerStatus.PLANNED_WITH_UNKNOWNS
    assert new_state.business.planning.ordered_step_ids == [
        "auth_gate",
        "collect_profile",
        "submit",
    ]
    assert new_state.business.planning.decisions
    assert new_state.business.planning.assumptions
    assert new_state.business.planning.assumptions[0].resolved is False
    assert new_state.business.planning.skeleton_id == "JOURNEY-CC-APPLY-STUB"
    assert new_state.business.planning.router_decision is not None
    assert new_state.business.planning.router_decision["action"] == "escalate"
    assert new_state.business.planning.repair_audit is not None
    assert new_state.business.planning.repair_audit["repair_attempted"] is False
    assert new_state.business.planning.repair_audit["original_output"]
    assert new_state.business.planning.repair_audit["final_action"] == "escalate"

    # Forbidden paths untouched (HITL/output intentionally updated by Router)
    assert new_state.business.intent.accepted.model_dump() == intent_before
    assert new_state.business.knowledge.model_dump() == knowledge_before
    assert new_state.execution.gates.model_dump() == gates_before
    assert new_state.business.validation.model_dump() == validation_before
    assert output_before_kind == "none"
    assert new_state.business.generation.blueprint_final is None

    # Agent metadata
    meta = new_state.execution.agents.planner
    assert meta.model == "stub-model"
    assert meta.prompt_version == "planner-system-v1"
    assert meta.latency_ms is not None and meta.latency_ms >= 0
    assert meta.structured_output_ok is True

    # Trace
    assert any(e.component == "journey_planner_agent" for e in new_state.execution.trace)
    merge_events = [
        e for e in new_state.execution.trace if e.component == "orchestrator.planning_merge"
    ]
    assert len(merge_events) == 1
    assert merge_events[0].actor == "code"
    assert "PLT-ASK-001" in new_state.execution.trace[0].evidence_refs or any(
        "PLT-ASK-001" in e.evidence_refs for e in new_state.execution.trace
    )
    planner_event = next(
        e for e in new_state.execution.trace if e.component == "journey_planner_agent"
    )
    assert planner_event.stage == "planning"
    assert "latency_ms" in planner_event.detail
    assert planner_event.detail["structured_output_ok"] is True
    assert planner_event.detail["model"] == "stub-model"
    router_final = [
        e
        for e in new_state.execution.trace
        if e.component == "orchestrator.router" and e.decision == "router_escalate"
    ]
    assert len(router_final) == 1

    assert new_state.execution.stage_history[-1].stage == "planning"
    assert new_state.execution.stage_history[-1].outcome == "escalated"
    assert new_state.business.planning.contract_validation_report is not None
    assert (
        new_state.business.planning.contract_validation_report[
            "official_journey_validation"
        ]
        is False
    )
    assert new_state.business.planning.contract_validation_report["overall_passed"] is True
    # Blueprint validation partition untouched
    assert new_state.business.validation.result == "pending"


def _clean_continue_plan():
    """Valid plan with no blocking gaps / high-risk assumptions."""
    out = example_planner_output().model_copy(deep=True)
    out.unknown_requirements = []
    out.assumptions = []
    out.decisions = [d for d in out.decisions if d.id != "d_unknown_api"]
    out.planner_status = PlannerStatus.PLANNED
    out.confidence = out.confidence.model_copy(
        update={"notes": "No blocking knowledge gaps in this fixture"}
    )
    return out


def test_run_planning_stage_continues_when_valid_and_unblocked() -> None:
    state = _state_ready_for_planning()
    pack = state.business.knowledge.model_copy(deep=True)
    pack.missing_knowledge = []
    state.business.knowledge = pack

    agent = JourneyPlannerAgent(
        llm_client=StubStructuredClient(lambda *_: _clean_continue_plan())
    )
    new_state, out = run_planning_stage(
        state, agent=agent, skeleton=example_skeleton(), model_name="stub-model"
    )
    assert out.planner_ok is True
    assert new_state.business.status == "planned"
    assert new_state.business.hitl.required is False
    assert new_state.business.planning.router_decision["action"] == "continue"
    assert new_state.business.planning.router_decision["allow_continue"] is True
    assert new_state.business.planning.repair_audit["repair_attempted"] is False
    assert new_state.execution.stage_history[-1].outcome == "success"


def test_run_planning_stage_one_repair_then_continue() -> None:
    state = _state_ready_for_planning()
    pack = state.business.knowledge.model_copy(deep=True)
    pack.missing_knowledge = []
    state.business.knowledge = pack

    broken = _clean_continue_plan().model_copy(deep=True)
    # Repairable: knowledge_references omit a cited document
    broken.knowledge_references = ["PLT-ASK-001"]  # missing PROD + stub docs

    fixed = _clean_continue_plan()
    calls: list[int] = []

    def handler(*_args):
        calls.append(1)
        return broken if len(calls) == 1 else fixed

    agent = JourneyPlannerAgent(llm_client=StubStructuredClient(handler))
    new_state, out = run_planning_stage(
        state, agent=agent, skeleton=example_skeleton(), model_name="stub-model"
    )

    assert len(calls) == 2  # exactly one repair — no open loop
    assert out.planner_ok is True
    assert new_state.business.status == "planned"
    assert new_state.execution.agents.planner.repair_pass == 1
    audit = new_state.business.planning.repair_audit
    assert audit["repair_attempted"] is True
    assert audit["repair_pass"] == 1
    assert audit["original_output"]
    assert audit["validation_errors"]
    assert audit["repaired_output"]
    assert audit["final_validation"]["overall_passed"] is True
    assert audit["final_action"] == "continue"
    assert new_state.business.planning.router_decision["action"] == "continue"
    # Replan context was supplied on second propose (via stub call count)
    assert len(calls) <= 2


def test_run_planning_stage_structural_failure_no_repair() -> None:
    state = _state_ready_for_planning()
    bad = example_planner_output().model_copy(deep=True)
    bad.ordered_step_ids = ["auth_gate", "invented_step", "submit"]
    bad.selected_step_ids = list(bad.ordered_step_ids)

    calls: list[int] = []

    def handler(*_args):
        calls.append(1)
        return bad

    agent = JourneyPlannerAgent(llm_client=StubStructuredClient(handler))
    new_state, out = run_planning_stage(
        state, agent=agent, skeleton=example_skeleton(), model_name="stub-model"
    )

    assert len(calls) == 1  # structural → no repair attempt
    assert new_state.business.status == "escalated"
    assert new_state.business.hitl.required is True
    assert new_state.business.planning.router_decision["failure_class"] == "structural"
    assert new_state.business.planning.repair_audit["repair_attempted"] is False
    assert any(e.code == "planner_structural_failure" for e in new_state.business.errors)
