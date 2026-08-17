"""One-shot Journey Planner demonstration — no new agents."""

from __future__ import annotations

import json
from pathlib import Path

from hdfc_journey.agents.planner.agent import JourneyPlannerAgent
from hdfc_journey.contracts.enums import AttributionKind
from hdfc_journey.contracts.planner import DecisionAttribution
from hdfc_journey.contracts.validation import validate_planner_output_report
from hdfc_journey.llm.deterministic_planner import (
    deterministic_planner_llm_handler,
    plan_from_planner_input,
)
from hdfc_journey.llm.stub_client import StubStructuredClient
from hdfc_journey.orchestrator.planning import (
    build_planner_input_from_state,
    run_planning_stage,
)
from hdfc_journey.orchestrator.router import route_planner_result
from tests.fixtures.address_change import (
    USER_UTTERANCE,
    address_change_knowledge_pack,
    address_change_skeleton,
    address_change_state,
)
from tests.fixtures.adversarial import _pack

OUT = Path("examples/planner_demo")
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    # ── Scenario A: "I want to change my address." ─────────────────────
    state_before = address_change_state()
    skeleton = address_change_skeleton()
    pack = address_change_knowledge_pack()
    planner_input = build_planner_input_from_state(state_before, skeleton)

    agent_preview = JourneyPlannerAgent(
        llm_client=StubStructuredClient(deterministic_planner_llm_handler)
    )
    propose_out = agent_preview.propose(planner_input)
    report = agent_preview.last_validation_report
    assert report is not None

    state2 = address_change_state()
    stub2 = StubStructuredClient(deterministic_planner_llm_handler)
    agent2 = JourneyPlannerAgent(llm_client=stub2)
    state_after, planner_output = run_planning_stage(
        state2,
        agent=agent2,
        skeleton=skeleton,
        model_name="deterministic-planner-v1",
    )

    accepted = state_before.business.intent.accepted
    assert accepted is not None

    demo_a = {
        "scenario": "address_change_nominal",
        "utterance": USER_UTTERANCE,
        "1_accepted_input": {
            "raw_text": state_before.business.input.normalized.raw_text,
            "channel_hint": state_before.business.input.normalized.channel_hint,
            "locale": state_before.business.input.normalized.locale,
            "customer_context": state_before.business.input.normalized.customer_context,
        },
        "2_accepted_intent": {
            "user_intent": accepted.user_intent,
            "journey_type": accepted.journey_type.value,
            "platform": accepted.platform.value,
            "product_domain": accepted.product_domain,
            "entities": [e.model_dump(mode="json") for e in accepted.entities],
            "confidence": accepted.confidence,
            "accepted_by": accepted.accepted_by,
        },
        "3_knowledge_pack": {
            "pack_id": pack.pack_id,
            "documents": pack.document_ids(),
            "excerpt_count": len(pack.excerpts),
            "missing_knowledge": [m.model_dump(mode="json") for m in pack.missing_knowledge],
            "retrieval_policy": pack.retrieval_policy,
        },
        "4_journey_skeleton": {
            "skeleton_id": skeleton.skeleton_id,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "ordinal": s.ordinal,
                    "optional": s.optional,
                    "type": s.type.value,
                }
                for s in sorted(skeleton.steps, key=lambda x: x.ordinal)
            ],
        },
        "5_planner_input": {
            "schema_version": planner_input.schema_version,
            "intent": planner_input.intent_accepted.user_intent,
            "pack_id": planner_input.knowledge_pack.pack_id,
            "skeleton_id": planner_input.skeleton.skeleton_id,
            "repair_pass": planner_input.execution.repair_pass,
            "replan_context": planner_input.replan_context,
        },
        "6_llm_execution": {
            "provider_stand_in": "deterministic-planner-v1",
            "llm_calls": len(stub2.calls),
            "prompt_version": agent2.prompt_version,
            "self_retry": False,
        },
        "7_planner_output": {
            "artifact_type": planner_output.artifact_type,
            "planner_status": planner_output.planner_status.value,
            "planner_ok": planner_output.planner_ok,
            "ordered_step_ids": planner_output.ordered_step_ids,
            "skipped_optional_step_ids": planner_output.skipped_optional_step_ids,
            "decision_kinds": [d.kind.value for d in planner_output.decisions],
            "entity_bindings": [
                f"{b.entity_type}:{b.entity_value}->{b.target_step_id}"
                for b in planner_output.entity_bindings
            ],
            "required_information_ids": [r.id for r in planner_output.required_information],
            "assumptions": [
                {
                    "id": a.id,
                    "risk": a.risk.value,
                    "must_confirm": a.must_confirm,
                    "statement": a.statement,
                }
                for a in planner_output.assumptions
            ],
            "unknown_requirements": [
                {
                    "id": u.id,
                    "kind": u.kind.value,
                    "blocking_hint": u.blocking_hint,
                    "description": u.description,
                }
                for u in planner_output.unknown_requirements
            ],
            "knowledge_references": planner_output.knowledge_references,
        },
        "8_validation": {
            "official_journey_validation": report.official_journey_validation,
            "overall_passed": report.overall_passed,
            "layers": [
                {
                    "layer": layer.layer.value,
                    "passed": layer.passed,
                    "violation_codes": [v.code for v in layer.violations],
                }
                for layer in report.layers
            ],
            "error_summary": None
            if report.overall_passed
            else report.error_summary(),
        },
        "9_router_decision": state_after.business.planning.router_decision,
        "10_state_update": {
            "status": state_after.business.status,
            "hitl_required": state_after.business.hitl.required,
            "hitl_reasons": state_after.business.hitl.reasons,
            "output_kind": state_after.business.output.kind,
            "planning_ordered_steps": state_after.business.planning.ordered_step_ids,
            "planning_planner_status": (
                state_after.business.planning.planner_status.value
                if state_after.business.planning.planner_status
                else None
            ),
            "intent_untouched": accepted.user_intent
            == state_after.business.intent.accepted.user_intent,  # type: ignore[union-attr]
            "knowledge_untouched": state_after.business.knowledge.pack_id  # type: ignore[union-attr]
            == pack.pack_id,
            "blueprint_validation_untouched": state_after.business.validation.result,
            "blueprint_final": state_after.business.generation.blueprint_final,
            "repair_attempted": (state_after.business.planning.repair_audit or {}).get(
                "repair_attempted"
            ),
        },
        "11_execution_trace": [
            {
                "component": e.component,
                "actor": e.actor,
                "decision": e.decision,
            }
            for e in state_after.execution.trace
        ],
        "12_final_planning_result": {
            "workflow_status": state_after.business.status,
            "allow_continue": (state_after.business.planning.router_decision or {}).get(
                "allow_continue"
            ),
            "failure_class": (state_after.business.planning.router_decision or {}).get(
                "failure_class"
            ),
            "reason": (state_after.business.planning.router_decision or {}).get("reason"),
            "next_gate": "HITL / knowledge backfill — Blueprint generation must NOT start",
        },
    }

    (OUT / "A_01_input.json").write_text(
        json.dumps(demo_a["1_accepted_input"], indent=2), encoding="utf-8"
    )
    (OUT / "A_02_intent.json").write_text(
        json.dumps(demo_a["2_accepted_intent"], indent=2), encoding="utf-8"
    )
    (OUT / "A_03_knowledge_pack.json").write_text(
        pack.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "A_04_skeleton.json").write_text(
        skeleton.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "A_05_planner_input.json").write_text(
        planner_input.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "A_07_planner_output.json").write_text(
        planner_output.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "A_08_validation.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "A_09_router.json").write_text(
        json.dumps(demo_a["9_router_decision"], indent=2), encoding="utf-8"
    )
    (OUT / "A_10_state_after.json").write_text(
        state_after.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "A_11_trace.json").write_text(
        json.dumps(
            [e.model_dump(mode="json") for e in state_after.execution.trace], indent=2
        ),
        encoding="utf-8",
    )

    # ── Scenario B: empty KnowledgePack ────────────────────────────────
    empty_pack = _pack(empty=True)
    state_b = address_change_state()
    state_b.business.knowledge = empty_pack
    sk_b = address_change_skeleton()
    calls_b = {"n": 0}

    def handler_b(_system: str, _user: str, _model: type):
        calls_b["n"] += 1
        return plan_from_planner_input(build_planner_input_from_state(state_b, sk_b))

    agent_b = JourneyPlannerAgent(llm_client=StubStructuredClient(handler_b))
    state_b_after, out_b = run_planning_stage(
        state_b, agent=agent_b, skeleton=sk_b, model_name="deterministic-planner-v1"
    )

    # Counterfactual: invent docs against empty pack
    hall = plan_from_planner_input(
        build_planner_input_from_state(address_change_state(), skeleton)
    ).model_copy(deep=True)
    hall.knowledge_references = list(
        set(hall.knowledge_references) | {"FAKE-ELIGIBILITY-DOC", "TECH-ADDR-UPDATE-APIS"}
    )
    hall.decisions[0] = hall.decisions[0].model_copy(
        update={
            "knowledge_source_ids": ["FAKE-ELIGIBILITY-DOC"],
            "attributions": [
                DecisionAttribution(
                    kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref="FAKE-ELIGIBILITY-DOC"
                )
            ],
        }
    )
    empty_inp = build_planner_input_from_state(address_change_state(), skeleton)
    empty_inp = empty_inp.model_copy(update={"knowledge_pack": empty_pack})
    hall_report = validate_planner_output_report(hall, empty_inp)
    hall_route = route_planner_result(
        output=hall, report=hall_report, repair_pass=0, max_repairs=1
    )

    demo_b = {
        "scenario": "insufficient_knowledge_empty_pack",
        "setup": "Empty KnowledgePack (no docs/excerpts). Same utterance + skeleton.",
        "llm_stand_in_result": {
            "planner_ok": out_b.planner_ok,
            "planner_status": out_b.planner_status.value,
            "ordered_step_ids": out_b.ordered_step_ids,
            "error": out_b.error.model_dump(mode="json") if out_b.error else None,
            "unknowns": [u.id for u in out_b.unknown_requirements],
            "assumptions": [a.id for a in out_b.assumptions],
            "knowledge_references": out_b.knowledge_references,
            "llm_calls": calls_b["n"],
        },
        "validation": {
            "overall_passed": (
                state_b_after.business.planning.contract_validation_report or {}
            ).get("overall_passed"),
            "official_journey_validation": (
                state_b_after.business.planning.contract_validation_report or {}
            ).get("official_journey_validation"),
        },
        "router": state_b_after.business.planning.router_decision,
        "state": {
            "status": state_b_after.business.status,
            "hitl_required": state_b_after.business.hitl.required,
            "hitl_reasons": state_b_after.business.hitl.reasons[:4],
            "output_kind": state_b_after.business.output.kind,
            "repair_attempted": (state_b_after.business.planning.repair_audit or {}).get(
                "repair_attempted"
            ),
        },
        "hallucination_counterfactual": {
            "description": (
                "If the LLM invented FAKE-ELIGIBILITY-DOC / TECH-ADDR-UPDATE-APIS "
                "as confirmed knowledge against an empty pack"
            ),
            "validation_passed": hall_report.overall_passed,
            "violation_codes": sorted({v.code for v in hall_report.violations}),
            "router_action": hall_route.action.value,
            "router_failure_class": hall_route.failure_class.value,
            "allow_continue": hall_route.allow_continue,
        },
    }

    (OUT / "B_empty_pack_run.json").write_text(
        json.dumps(demo_b, indent=2), encoding="utf-8"
    )
    (OUT / "B_state_after.json").write_text(
        state_b_after.model_dump_json(indent=2), encoding="utf-8"
    )
    (OUT / "demo_summary.json").write_text(
        json.dumps({"A": demo_a, "B": demo_b}, indent=2, default=str),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "artifacts": str(OUT.resolve()),
                "A_final": demo_a["12_final_planning_result"],
                "A_steps": demo_a["7_planner_output"]["ordered_step_ids"],
                "A_unknowns": [
                    u["id"] for u in demo_a["7_planner_output"]["unknown_requirements"]
                ],
                "B_llm": demo_b["llm_stand_in_result"],
                "B_state": demo_b["state"],
                "B_hallucination": demo_b["hallucination_counterfactual"],
                "A_trace": demo_a["11_execution_trace"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
