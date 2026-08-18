"""Deterministic intent Router tests.

The Router is the component that decides continue / clarify / escalate. The
agent never does. These tests pin the routing table, especially the rule that
structural failures beat clarifiable ones.
"""

from __future__ import annotations

from hdfc_journey.contracts.intent import IntentError, IntentProposalOutput
from hdfc_journey.contracts.intent_enums import (
    IntentFailureClass,
    IntentRouteAction,
    IntentStatus,
)
from hdfc_journey.contracts.intent_validation import validate_intent_proposal_report
from hdfc_journey.orchestrator.intent_gate import evaluate_intent_gate
from hdfc_journey.orchestrator.intent_router import route_intent_result
from tests.fixtures.intent_examples import (
    make_ambiguous_proposal,
    make_clean_proposal,
    make_intent_input,
    make_unknown_proposal,
)


def _route(output, *, repair_pass=0, intent_input=None, max_clarifications=1, **gate_kwargs):
    intent_input = intent_input or make_intent_input()
    report = validate_intent_proposal_report(output, intent_input)
    gate_result = evaluate_intent_gate(
        output=output, intent_input=intent_input, report=report, **gate_kwargs
    )
    decision = route_intent_result(
        output=output,
        report=report,
        gate_result=gate_result,
        repair_pass=repair_pass,
        max_clarifications=max_clarifications,
    )
    return decision, gate_result


class TestContinue:
    def test_accepted_intent_continues(self):
        decision, _ = _route(make_clean_proposal())
        assert decision.action == IntentRouteAction.CONTINUE
        assert decision.allow_continue is True
        assert decision.failure_class == IntentFailureClass.NONE


class TestClarify:
    def test_ambiguity_earns_one_clarification(self):
        decision, _ = _route(make_ambiguous_proposal(), repair_pass=0)
        assert decision.action == IntentRouteAction.CLARIFY
        assert decision.failure_class == IntentFailureClass.AMBIGUOUS
        assert decision.clarify_fields == ["user_intent"]

    def test_unknown_intent_earns_one_clarification(self):
        decision, _ = _route(make_unknown_proposal(), repair_pass=0)
        assert decision.action == IntentRouteAction.CLARIFY
        assert decision.failure_class == IntentFailureClass.UNKNOWN_INTENT

    def test_low_confidence_earns_one_clarification(self):
        decision, _ = _route(make_clean_proposal(confidence=0.4), repair_pass=0)
        assert decision.action == IntentRouteAction.CLARIFY
        assert decision.failure_class == IntentFailureClass.LOW_CONFIDENCE

    def test_second_failure_escalates_no_loop(self):
        """Budget is one. A second failure must not buy another attempt."""
        decision, _ = _route(make_ambiguous_proposal(), repair_pass=1)
        assert decision.action == IntentRouteAction.ESCALATE
        assert decision.failure_class == IntentFailureClass.REPAIR_EXHAUSTED

    def test_budget_hard_capped_at_one(self):
        decision, _ = _route(make_ambiguous_proposal(), max_clarifications=5)
        assert decision.max_clarifications == 1


class TestEscalate:
    def test_unsupported_intent_escalates_immediately(self):
        """Asking the customer cannot make an unsupported intent supported."""
        decision, _ = _route(
            make_clean_proposal(user_intent="TRANSFER_TO_CRYPTO"), repair_pass=0
        )
        assert decision.action == IntentRouteAction.ESCALATE
        assert decision.failure_class == IntentFailureClass.NOT_ALLOWLISTED

    def test_underivable_platform_escalates_immediately(self):
        decision, _ = _route(
            make_clean_proposal(), intent_input=make_intent_input(channel_hint=None)
        )
        assert decision.action == IntentRouteAction.ESCALATE
        assert decision.failure_class == IntentFailureClass.PLATFORM_UNDERIVABLE

    def test_structural_beats_clarifiable(self):
        """Mixed signals must not buy a clarification round."""
        out = make_ambiguous_proposal()
        decision, _ = _route(out, intent_input=make_intent_input(channel_hint=None))
        assert decision.action == IntentRouteAction.ESCALATE
        assert decision.structural_codes

    def test_invalid_artifact_escalates(self):
        out = make_clean_proposal().model_copy(
            update={"rationale": "already accepted and approved"}
        )
        decision, _ = _route(out)
        assert decision.action == IntentRouteAction.ESCALATE
        assert decision.failure_class == IntentFailureClass.STRUCTURAL


class TestAgentFailure:
    def _failed(self, retriable: bool) -> IntentProposalOutput:
        return IntentProposalOutput(
            intent_status=IntentStatus.FAILED,
            proposal_ok=False,
            error=IntentError(
                code="llm_failure", message="timeout", retriable=retriable
            ),
        )

    def test_retriable_failure_earns_one_retry(self):
        decision, _ = _route(self._failed(True), repair_pass=0)
        assert decision.action == IntentRouteAction.CLARIFY
        assert decision.failure_class == IntentFailureClass.AGENT_FAILED

    def test_non_retriable_failure_escalates(self):
        decision, _ = _route(self._failed(False), repair_pass=0)
        assert decision.action == IntentRouteAction.ESCALATE

    def test_retriable_failure_exhausted_escalates(self):
        decision, _ = _route(self._failed(True), repair_pass=1)
        assert decision.action == IntentRouteAction.ESCALATE


class TestRouterProperties:
    def test_router_is_deterministic(self):
        out = make_ambiguous_proposal()
        a, _ = _route(out)
        b, _ = _route(out)
        assert a.model_dump() == b.model_dump()

    def test_router_never_continues_on_rejection(self):
        for out in (
            make_ambiguous_proposal(),
            make_unknown_proposal(),
            make_clean_proposal(user_intent="NOT_REAL"),
            make_clean_proposal(confidence=0.1),
        ):
            decision, gate = _route(out)
            assert gate.is_accepted() is False
            assert decision.allow_continue is False
            assert decision.action != IntentRouteAction.CONTINUE
