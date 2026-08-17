"""Map Intent contracts ↔ JourneyGenerationState.business.intent (documentation helpers).

The write-permission split is the whole point of this module: the agent may
cause ``intent.proposal`` to be written, and NOTHING else. ``intent.accepted``
is gate-only, and the frozen sets below are asserted in the test suite.
"""

from __future__ import annotations

from typing import Any

from hdfc_journey.contracts.intent import IntentGateResult, IntentProposalOutput
from hdfc_journey.contracts.state import IntentAccepted, IntentProposal

# Fields the Intent agent may cause to be written (only via orchestrator merge).
AGENT_WRITABLE_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.intent.proposal",
    }
)

# Written by the deterministic gate alone. The agent must never reach these.
GATE_ONLY_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.intent.accepted",
        "execution.gates.intent_gate",
    }
)

# Set by orchestrator before/after the Intent stage; agent must not write.
ORCHESTRATOR_ONLY_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.status",
        "business.hitl",
        "business.output",
        "business.errors",
        "execution.current_stage",
        "execution.stage_history",
        "execution.agents.intent",
        "execution.trace",
        "execution.gates",
    }
)

# Sealed at intake; nothing in the Intent stage may modify these.
IMMUTABLE_INPUT_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.input.raw",
        "business.input.normalized",
        "execution.run_id",
        "execution.config_snapshot",
    }
)

# Paths the Intent stage must never touch — later stages own them entirely.
FORBIDDEN_DOWNSTREAM_STATE_PATHS: frozenset[str] = frozenset(
    {
        "business.knowledge",
        "business.planning",
        "business.generation",
        "business.validation",
    }
)


def intent_proposal_state_patch(output: IntentProposalOutput) -> dict[str, Any]:
    """Project an agent proposal onto ``business.intent.proposal``.

    Note the deliberate lossiness: ``platform_hint`` lands in the state's
    advisory ``platform`` slot, and no acceptance-shaped field is carried at all.
    """
    return {
        "proposal": IntentProposal(
            user_intent=output.user_intent,
            journey_type=output.journey_type.value if output.journey_type else None,
            platform=output.platform_hint.value if output.platform_hint else None,
            product_domain=output.product_domain,
            entities=[
                # ProposedEntity -> AcceptedEntity shape (state reuses the model);
                # this is a shape conversion only, NOT an acceptance.
                {
                    "type": e.type,
                    "value": e.value,
                    "raw_span": e.raw_span,
                    "confidence": e.confidence,
                }
                for e in output.entities
            ],
            confidence=output.confidence,
            ambiguities=[a.model_dump(mode="json") for a in output.ambiguities],
            priority_hint=output.priority_hint.value if output.priority_hint else None,
            rationale=output.rationale or None,
        )
    }


def intent_accepted_state_patch(gate_result: IntentGateResult) -> dict[str, Any]:
    """Project an ACCEPTED gate result onto ``business.intent.accepted``.

    Raises if called on a rejection — there is no such thing as a partially
    accepted intent.
    """
    if not gate_result.is_accepted() or gate_result.accepted_intent is None:
        raise ValueError(
            "intent_accepted_state_patch requires an accepted gate result; "
            "a rejected proposal must never be written to business.intent.accepted"
        )
    ai = gate_result.accepted_intent
    return {
        "accepted": IntentAccepted(
            user_intent=ai.user_intent,
            journey_type=ai.journey_type,
            platform=ai.platform,
            product_domain=ai.product_domain,
            entities=list(ai.entities),
            confidence=ai.confidence,
            ambiguities=list(ai.ambiguities),
            priority=ai.priority,
            accepted_by="intent_gate",
            accepted_at=ai.accepted_at,
        )
    }
