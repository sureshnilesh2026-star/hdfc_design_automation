"""Deterministic intent gate tests.

The gate is the security boundary of this slice, so these tests are written
adversarially: for every field the model can influence, there is a test that
the gate does not simply trust it.
"""

from __future__ import annotations

from hdfc_journey.contracts.enums import JourneyType, Platform, Priority
from hdfc_journey.contracts.intent import ProposedEntity
from hdfc_journey.contracts.intent_enums import (
    UNKNOWN_INTENT,
    IntentGateVerdict,
    IntentOverrideReason,
)
from hdfc_journey.contracts.intent_validation import validate_intent_proposal_report
from hdfc_journey.orchestrator.intent_gate import (
    REASON_AMBIGUOUS,
    REASON_INTENT_NOT_ALLOWLISTED,
    REASON_INTENT_UNKNOWN,
    REASON_LOW_CONFIDENCE,
    REASON_PLATFORM_NOT_ALLOWLISTED,
    REASON_PLATFORM_UNDERIVABLE,
    REASON_PROPOSAL_INVALID,
    derive_platform,
    evaluate_intent_gate,
)
from tests.fixtures.intent_examples import (
    make_ambiguous_proposal,
    make_clean_proposal,
    make_intent_input,
    make_unknown_proposal,
)


def _gate(output, intent_input=None, **kwargs):
    intent_input = intent_input or make_intent_input()
    report = validate_intent_proposal_report(output, intent_input)
    return evaluate_intent_gate(
        output=output, intent_input=intent_input, report=report, **kwargs
    )


class TestHappyPath:
    def test_clean_proposal_accepted(self):
        result = _gate(make_clean_proposal())
        assert result.verdict == IntentGateVerdict.ACCEPTED
        assert result.accepted_intent is not None
        assert result.accepted_intent.user_intent == "UPDATE_ADDRESS"

    def test_accepted_intent_matches_planner_contract(self):
        """The handoff must be consumable by the Planner with zero glue."""
        from hdfc_journey.contracts.planner import AcceptedIntent

        result = _gate(make_clean_proposal())
        assert isinstance(result.accepted_intent, AcceptedIntent)

    def test_accepted_intent_carries_no_ambiguities(self):
        result = _gate(make_clean_proposal())
        assert result.accepted_intent.ambiguities == []

    def test_gate_is_deterministic(self):
        """Same inputs must always produce the same verdict — replayability."""
        intent_input = make_intent_input()
        out = make_clean_proposal()
        a = _gate(out, intent_input)
        b = _gate(out, intent_input)

        def strip_timestamps(result):
            d = result.model_dump(mode="json")
            d.pop("evaluated_at", None)
            if d.get("accepted_intent"):
                d["accepted_intent"].pop("accepted_at", None)
            return d

        assert a.verdict == b.verdict
        assert strip_timestamps(a) == strip_timestamps(b)


class TestClosedWorldIntent:
    def test_unknown_intent_rejected(self):
        result = _gate(make_unknown_proposal())
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_INTENT_UNKNOWN in result.reason_codes

    def test_intent_outside_registry_rejected(self):
        """A confident, well-formed, entirely invented intent must not pass."""
        out = make_clean_proposal(user_intent="TRANSFER_TO_CRYPTO", confidence=0.99)
        result = _gate(out)
        assert result.verdict == IntentGateVerdict.REJECTED

    def test_registered_but_not_enabled_for_run_rejected(self):
        out = make_clean_proposal(user_intent="BLOCK_CARD", product_domain="cards")
        result = _gate(out, intent_allowlist=["UPDATE_ADDRESS"])
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_INTENT_NOT_ALLOWLISTED in result.reason_codes

    def test_intent_case_is_normalized_and_recorded(self):
        out = make_clean_proposal(user_intent="update_address")
        result = _gate(out)
        assert result.verdict == IntentGateVerdict.ACCEPTED
        assert any(
            o.reason == IntentOverrideReason.INTENT_CASE_NORMALIZED
            for o in result.overrides
        )


class TestAmbiguityBlocks:
    def test_ambiguous_proposal_rejected(self):
        result = _gate(make_ambiguous_proposal())
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_AMBIGUOUS in result.reason_codes

    def test_ambiguity_fields_surfaced_for_hitl(self):
        result = _gate(make_ambiguous_proposal())
        assert result.unresolved_ambiguity_fields == ["user_intent"]

    def test_high_confidence_does_not_override_ambiguity(self):
        """Confidence is a backstop, not a bypass."""
        out = make_ambiguous_proposal().model_copy(update={"confidence": 0.9})
        result = _gate(out)
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_AMBIGUOUS in result.reason_codes


class TestPlatformDerivation:
    def test_platform_derived_from_channel_not_model(self):
        """The model claims web; the channel says asknow. Channel wins."""
        out = make_clean_proposal(platform_hint=Platform.WEB)
        result = _gate(out, make_intent_input(channel_hint="asknow"))
        assert result.accepted_intent.platform == Platform.ASKNOW
        assert any(
            o.reason == IntentOverrideReason.PLATFORM_FROM_CHANNEL_HINT
            and o.model_value == "web"
            and o.accepted_value == "asknow"
            for o in result.overrides
        )

    def test_missing_channel_hint_rejects_rather_than_falls_back(self):
        out = make_clean_proposal(platform_hint=Platform.ASKNOW)
        result = _gate(out, make_intent_input(channel_hint=None))
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_PLATFORM_UNDERIVABLE in result.reason_codes

    def test_unmappable_channel_rejected(self):
        result = _gate(make_clean_proposal(), make_intent_input(channel_hint="carrier_pigeon"))
        assert REASON_PLATFORM_UNDERIVABLE in result.reason_codes

    def test_platform_not_in_run_allowlist_rejected(self):
        result = _gate(
            make_clean_proposal(),
            make_intent_input(channel_hint="asknow"),
            platform_allowlist=["web"],
        )
        assert REASON_PLATFORM_NOT_ALLOWLISTED in result.reason_codes

    def test_derive_platform_is_case_insensitive(self):
        assert derive_platform("AskNow") == Platform.ASKNOW
        assert derive_platform("  EVA  ") == Platform.EVA_DBU
        assert derive_platform(None) is None
        assert derive_platform("nonsense") is None


class TestConfidenceFloor:
    def test_below_floor_rejected(self):
        result = _gate(make_clean_proposal(confidence=0.4), confidence_floor=0.7)
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_LOW_CONFIDENCE in result.reason_codes

    def test_membership_failure_reported_alongside_confidence(self):
        """An off-registry intent fails on membership regardless of confidence.

        This is the architectural claim: membership is authoritative, and a
        high-confidence invented intent is exactly the failure mode the floor
        cannot catch. The gate reports every applicable reason.
        """
        low = _gate(make_clean_proposal(user_intent="INVENTED_INTENT", confidence=0.1))
        assert REASON_INTENT_NOT_ALLOWLISTED in low.reason_codes

        high = _gate(make_clean_proposal(user_intent="INVENTED_INTENT", confidence=0.99))
        assert REASON_INTENT_NOT_ALLOWLISTED in high.reason_codes
        assert REASON_LOW_CONFIDENCE not in high.reason_codes

    def test_floor_recorded_for_audit(self):
        result = _gate(make_clean_proposal(), confidence_floor=0.75)
        assert result.confidence_floor_applied == 0.75
        assert result.model_confidence == 0.88


class TestDerivedFields:
    def test_journey_type_overridden_from_registry(self):
        """The model guesses acquisition; the registry says servicing."""
        out = make_clean_proposal(journey_type=JourneyType.ACQUISITION)
        result = _gate(out)
        assert result.accepted_intent.journey_type == JourneyType.SERVICING
        assert any(
            o.reason == IntentOverrideReason.JOURNEY_TYPE_FROM_REGISTRY
            for o in result.overrides
        )

    def test_product_domain_overridden_from_registry(self):
        out = make_clean_proposal(product_domain="crypto")
        result = _gate(out)
        assert result.accepted_intent.product_domain == "accounts"

    def test_priority_comes_from_config_not_model(self):
        out = make_clean_proposal(priority_hint=Priority.HIGH)
        result = _gate(out, default_priority=Priority.NORMAL)
        assert result.accepted_intent.priority == Priority.NORMAL
        assert any(
            o.reason == IntentOverrideReason.PRIORITY_FROM_CONFIG
            for o in result.overrides
        )

    def test_accepted_by_is_always_the_gate(self):
        result = _gate(make_clean_proposal())
        assert result.accepted_intent.accepted_by == "intent_gate"


class TestEntityFiltering:
    def test_unregistered_entity_type_dropped(self):
        out = make_clean_proposal(
            entities=[
                ProposedEntity(type="address_type", value="home"),
                ProposedEntity(type="secret_override_flag", value="true"),
            ]
        )
        result = _gate(out)
        types = {e.type for e in result.accepted_intent.entities}
        assert types == {"address_type"}
        assert "secret_override_flag" in result.dropped_entity_types

    def test_duplicate_entities_collapsed(self):
        out = make_clean_proposal(
            entities=[
                ProposedEntity(type="address_type", value="home"),
                ProposedEntity(type="address_type", value="home"),
            ]
        )
        result = _gate(out)
        assert len(result.accepted_intent.entities) == 1

    def test_entity_whitespace_sanitized(self):
        out = make_clean_proposal(
            entities=[ProposedEntity(type="address_type", value="  home   office ")]
        )
        result = _gate(out)
        assert result.accepted_intent.entities[0].value == "home office"


class TestInvalidArtifacts:
    def test_failed_proposal_rejected(self):
        from hdfc_journey.contracts.intent import IntentError, IntentProposalOutput
        from hdfc_journey.contracts.intent_enums import IntentStatus

        out = IntentProposalOutput(
            intent_status=IntentStatus.FAILED,
            proposal_ok=False,
            error=IntentError(code="llm_failure", message="timeout", retriable=True),
        )
        result = _gate(out)
        assert result.verdict == IntentGateVerdict.REJECTED

    def test_invalid_artifact_rejected_before_acceptance(self):
        out = make_clean_proposal().model_copy(
            update={"rationale": "this is accepted and approved"}
        )
        result = _gate(out)
        assert result.verdict == IntentGateVerdict.REJECTED
        assert REASON_PROPOSAL_INVALID in result.reason_codes

    def test_rejection_never_produces_accepted_intent(self):
        for out in (
            make_unknown_proposal(),
            make_ambiguous_proposal(),
            make_clean_proposal(user_intent=UNKNOWN_INTENT, confidence=0.2),
        ):
            result = _gate(out)
            assert result.accepted_intent is None
