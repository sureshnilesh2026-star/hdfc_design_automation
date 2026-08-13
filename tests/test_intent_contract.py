"""Contract + deterministic validation tests for the Intent Recognition slice."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hdfc_journey.contracts.enums import JourneyType
from hdfc_journey.contracts.intent import (
    AcceptedIntent,
    IntentAmbiguity,
    IntentProposalOutput,
)
from hdfc_journey.contracts.intent_enums import (
    UNKNOWN_INTENT,
    AmbiguityField,
    IntentStatus,
)
from hdfc_journey.contracts.intent_registry import IntentRegistry
from hdfc_journey.contracts.intent_validation import (
    validate_intent_proposal_report,
)
from tests.fixtures.intent_examples import (
    make_ambiguous_proposal,
    make_clean_proposal,
    make_intent_input,
    make_unknown_proposal,
)


class TestProposalContract:
    def test_proposal_forbids_extra_fields(self):
        """The proposal must not be able to smuggle an acceptance field."""
        with pytest.raises(ValidationError):
            IntentProposalOutput(
                intent_status=IntentStatus.PROPOSED,
                proposal_ok=True,
                user_intent="UPDATE_ADDRESS",
                accepted=True,  # type: ignore[call-arg]
            )

    def test_proposal_has_no_priority_or_platform_authority(self):
        """Only *hint* fields exist; the real fields belong to the gate."""
        fields = set(IntentProposalOutput.model_fields)
        assert "platform" not in fields
        assert "priority" not in fields
        assert "platform_hint" in fields
        assert "priority_hint" in fields

    def test_artifact_type_is_literal(self):
        with pytest.raises(ValidationError):
            IntentProposalOutput(
                intent_status=IntentStatus.PROPOSED,
                proposal_ok=True,
                artifact_type="journey_plan",  # type: ignore[arg-type]
            )

    def test_confidence_bounds_enforced(self):
        with pytest.raises(ValidationError):
            IntentProposalOutput(
                intent_status=IntentStatus.PROPOSED, proposal_ok=True, confidence=1.5
            )

    def test_accepted_intent_is_the_planner_contract(self):
        """The handoff type must be Syed's, not a re-declaration."""
        from hdfc_journey.contracts.planner import AcceptedIntent as PlannerAccepted

        assert AcceptedIntent is PlannerAccepted


class TestRegistry:
    def test_registry_lookup(self):
        reg = IntentRegistry()
        d = reg.get("UPDATE_ADDRESS")
        assert d is not None
        assert d.journey_type == JourneyType.SERVICING
        assert d.product_domain == "accounts"

    def test_unknown_intent_not_in_registry(self):
        assert IntentRegistry().get("WIRE_MONEY_TO_MARS") is None

    def test_vocabulary_renders_all_intents(self):
        reg = IntentRegistry()
        vocab = reg.vocabulary_for_prompt()
        for intent_id in reg.intent_ids():
            assert intent_id in vocab


class TestValidationLayers:
    def test_clean_proposal_passes(self):
        report = validate_intent_proposal_report(
            make_clean_proposal(), make_intent_input()
        )
        assert report.overall_passed
        assert report.violations == []

    def test_report_never_grants_acceptance(self):
        report = validate_intent_proposal_report(
            make_clean_proposal(), make_intent_input()
        )
        assert report.grants_acceptance is False

    def test_ambiguous_proposal_is_valid(self):
        """Declaring ambiguity is correct behaviour, not a contract violation."""
        report = validate_intent_proposal_report(
            make_ambiguous_proposal(), make_intent_input()
        )
        assert report.overall_passed

    def test_unknown_proposal_is_valid(self):
        report = validate_intent_proposal_report(
            make_unknown_proposal(), make_intent_input()
        )
        assert report.overall_passed

    def test_intent_outside_registry_is_warning_not_error(self):
        """The proposer is allowed to be wrong; catching it is the gate's job.

        Making this an artifact error would mask the specific
        `intent_not_allowlisted` gate reason behind a generic `proposal_invalid`.
        """
        out = make_clean_proposal(user_intent="TRANSFER_TO_CRYPTO")
        report = validate_intent_proposal_report(out, make_intent_input())
        assert report.overall_passed
        assert any(w.code == "intent_not_in_registry" for w in report.warnings)

    def test_malformed_intent_id_flagged(self):
        """Genuinely non-conforming ids fail; mere formatting does not."""
        out = make_clean_proposal(user_intent="change@address!")
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "malformed_intent_id" in report.codes()

    def test_non_canonical_casing_is_warning_not_error(self):
        """Case/hyphen/space variants are recoverable by the gate, not fatal."""
        out = make_clean_proposal(user_intent="update address")
        report = validate_intent_proposal_report(out, make_intent_input())
        assert report.overall_passed
        assert any(w.code == "intent_id_not_canonical" for w in report.warnings)

    def test_overconfident_with_ambiguity_rejected(self):
        out = make_ambiguous_proposal().model_copy(update={"confidence": 0.99})
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "overconfident_with_ambiguity" in report.codes()

    def test_overconfident_unknown_rejected(self):
        out = make_unknown_proposal().model_copy(update={"confidence": 0.95})
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "overconfident_unknown" in report.codes()

    def test_ambiguity_status_mismatch_flagged(self):
        out = make_clean_proposal().model_copy(
            update={
                "ambiguities": [
                    IntentAmbiguity(field=AmbiguityField.SCOPE, note="unclear")
                ]
            }
        )
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "ambiguity_status_mismatch" in report.codes()

    def test_unknown_intent_status_mismatch_flagged(self):
        out = make_clean_proposal(user_intent=UNKNOWN_INTENT, confidence=0.3)
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "unknown_intent_status_mismatch" in report.codes()

    def test_rationale_claiming_decision_rejected(self):
        out = make_clean_proposal().model_copy(
            update={"rationale": "This intent is accepted and validated."}
        )
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "rationale_claims_decision" in report.codes()

    def test_failed_without_error_flagged(self):
        out = IntentProposalOutput(
            intent_status=IntentStatus.FAILED, proposal_ok=False, error=None
        )
        report = validate_intent_proposal_report(out, make_intent_input())
        assert "failed_without_error" in report.codes()

    def test_entity_type_not_registered_is_warning_not_error(self):
        from hdfc_journey.contracts.intent import ProposedEntity

        out = make_clean_proposal(
            entities=[ProposedEntity(type="favourite_colour", value="teal")]
        )
        report = validate_intent_proposal_report(out, make_intent_input())
        assert report.overall_passed
        assert any(w.code == "entity_type_not_registered" for w in report.warnings)
