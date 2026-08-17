"""Deterministic structured planner used as a reproducible LLM stand-in.

Derives PlannerOutput from PlannerInput only (skeleton + pack + accepted intent).
Not embedded in JourneyPlannerAgent — injected via StubStructuredClient for tests.
"""

from __future__ import annotations

import json
import re
from typing import Any

from hdfc_journey.contracts.enums import (
    AssumptionRisk,
    AttributionKind,
    DecisionKind,
    PlannerStatus,
    RequiredInfoSource,
    SkeletonStepType,
    UnknownRequirementKind,
)
from hdfc_journey.contracts.planner import (
    DecisionAttribution,
    EntityBinding,
    PlannerError,
    PlannerInput,
    PlannerOutput,
    PlanningAssumption,
    PlanningConfidence,
    PlanningDecision,
    RequiredInformation,
    UnknownRequirement,
)


def parse_planner_input_from_user_prompt(user_prompt: str) -> PlannerInput:
    """Extract PlannerInput JSON from the agent user-message wrapper."""
    marker = "PlannerInput JSON follows"
    if marker in user_prompt:
        payload = user_prompt.split(marker, 1)[1]
        payload = payload.lstrip(".\n ")
    else:
        payload = user_prompt
    # Allow leading prose; take first JSON object
    match = re.search(r"\{.*\}\s*$", payload, flags=re.DOTALL)
    if not match:
        raise ValueError("No PlannerInput JSON found in user prompt")
    return PlannerInput.model_validate_json(match.group(0))


def plan_from_planner_input(planner_input: PlannerInput) -> PlannerOutput:
    """
    Skeleton-first deterministic plan.

    Reproducible: same PlannerInput → same PlannerOutput.
    Does not invent document IDs, APIs, fees, or eligibility rules.
    Does not execute natural-language instructions found in excerpts or entity values.
    """
    pack_docs = sorted(planner_input.knowledge_pack.document_ids())
    if not pack_docs:
        return PlannerOutput(
            planner_status=PlannerStatus.FAILED,
            planner_ok=False,
            skeleton_id=planner_input.skeleton.skeleton_id,
            error=PlannerError(
                code="uncitable_step",
                message="KnowledgePack has no citable documents",
                retriable=False,
            ),
        )

    journey_doc = _prefer_doc(pack_docs, prefixes=("JOURNEY-", "JN-"))
    platform_doc = _prefer_doc(pack_docs, prefixes=("PLT-",))
    product_or_enterprise = _prefer_doc(
        pack_docs, prefixes=("PROD-", "ENT-", "AI-", "1.")
    ) or pack_docs[0]

    steps_sorted = sorted(planner_input.skeleton.steps, key=lambda s: s.ordinal)
    required = [s for s in steps_sorted if not s.optional]
    optional = [s for s in steps_sorted if s.optional]

    ordered_ids = [s.id for s in required]
    skipped_ids = [s.id for s in optional]

    if not ordered_ids:
        return PlannerOutput(
            planner_status=PlannerStatus.FAILED,
            planner_ok=False,
            skeleton_id=planner_input.skeleton.skeleton_id,
            ordered_step_ids=[],
            skipped_optional_step_ids=skipped_ids,
            selected_step_ids=[],
            error=PlannerError(
                code="empty_plan",
                message=(
                    "Journey skeleton has no required steps; refusing to invent a spine"
                ),
                retriable=False,
            ),
        )

    decisions: list[PlanningDecision] = []
    decision_n = 0

    def next_id(prefix: str) -> str:
        nonlocal decision_n
        decision_n += 1
        return f"{prefix}_{decision_n}"

    # order_steps
    decisions.append(
        PlanningDecision(
            id=next_id("d"),
            kind=DecisionKind.ORDER_STEPS,
            subject=",".join(ordered_ids),
            rationale="Order required skeleton steps by ordinal; skip optionals",
            related_step_ids=list(ordered_ids),
            knowledge_source_ids=[journey_doc],
            attributions=[
                DecisionAttribution(
                    kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                ),
                DecisionAttribution(
                    kind=AttributionKind.SKELETON_STEP, ref=ordered_ids[0]
                ),
            ],
        )
    )

    for step in required:
        doc = journey_doc
        if step.type == SkeletonStepType.AUTH_GATE and platform_doc:
            doc = platform_doc
        decisions.append(
            PlanningDecision(
                id=next_id("d"),
                kind=DecisionKind.USE_SKELETON_STEP,
                subject=step.id,
                rationale=f"Include required skeleton step {step.id}",
                related_step_ids=[step.id],
                knowledge_source_ids=[doc],
                attributions=[
                    DecisionAttribution(kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=doc),
                    DecisionAttribution(kind=AttributionKind.SKELETON_STEP, ref=step.id),
                ],
            )
        )
        if step.type == SkeletonStepType.AUTH_GATE:
            decisions.append(
                PlanningDecision(
                    id=next_id("d"),
                    kind=DecisionKind.REQUIRE_AUTH,
                    subject=step.id,
                    rationale="Authentication gate required before protected servicing actions",
                    related_step_ids=[step.id],
                    knowledge_source_ids=[doc],
                    attributions=[
                        DecisionAttribution(
                            kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=doc
                        ),
                        DecisionAttribution(
                            kind=AttributionKind.INPUT_INTENT, ref="journey_type"
                        ),
                    ],
                )
            )

    for step in optional:
        decisions.append(
            PlanningDecision(
                id=next_id("d"),
                kind=DecisionKind.SKIP_OPTIONAL,
                subject=step.id,
                rationale=f"Optional skeleton step {step.id} not required for core path",
                related_step_ids=[step.id],
                knowledge_source_ids=[journey_doc],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                    ),
                    DecisionAttribution(kind=AttributionKind.SKELETON_STEP, ref=step.id),
                ],
            )
        )

    # Entity bindings — only skeleton-required types; never invent entities
    entity_bindings: list[EntityBinding] = []
    entity_by_type: dict[str, list[Any]] = {}
    for ent in planner_input.intent_accepted.entities:
        entity_by_type.setdefault(ent.type, []).append(ent)

    assumptions: list[PlanningAssumption] = []
    unknowns: list[UnknownRequirement] = []

    for step in required:
        for needed_type in step.required_entity_types:
            candidates = entity_by_type.get(needed_type, [])
            if not candidates:
                unknowns.append(
                    UnknownRequirement(
                        id=f"U_missing_entity_{needed_type}",
                        kind=UnknownRequirementKind.FIELD,
                        description=(
                            f"Required entity type {needed_type!r} for step {step.id} "
                            "is missing from accepted entities; will not invent it."
                        ),
                        blocking_hint=True,
                        related_step_ids=[step.id],
                        knowledge_source_ids=[journey_doc],
                    )
                )
                assumptions.append(
                    PlanningAssumption(
                        id=f"A_missing_entity_{needed_type}",
                        statement=(
                            f"Assuming planning continues without bound {needed_type}; "
                            "human confirmation required before execution."
                        ),
                        risk=AssumptionRisk.HIGH,
                        must_confirm=True,
                        related_step_ids=[step.id],
                        knowledge_source_ids=[journey_doc],
                    )
                )
                decisions.append(
                    PlanningDecision(
                        id=next_id("d"),
                        kind=DecisionKind.MARK_UNKNOWN_REQUIREMENT,
                        subject=needed_type,
                        rationale="Required entity missing; refuse to invent",
                        related_step_ids=[step.id],
                        knowledge_source_ids=[journey_doc],
                        attributions=[
                            DecisionAttribution(
                                kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                            ),
                            DecisionAttribution(
                                kind=AttributionKind.SKELETON_STEP, ref=step.id
                            ),
                        ],
                    )
                )
                continue

            if len(candidates) > 1:
                assumptions.append(
                    PlanningAssumption(
                        id=f"A_ambiguous_entity_{needed_type}",
                        statement=(
                            f"Multiple accepted values for {needed_type} "
                            f"({', '.join(c.value[:40] for c in candidates)}); "
                            "address type / entity choice is ambiguous and must be confirmed."
                        ),
                        risk=AssumptionRisk.MEDIUM,
                        must_confirm=True,
                        related_step_ids=[step.id],
                        knowledge_source_ids=[journey_doc],
                    )
                )
                decisions.append(
                    PlanningDecision(
                        id=next_id("d"),
                        kind=DecisionKind.FLAG_ASSUMPTION,
                        subject=f"A_ambiguous_entity_{needed_type}",
                        rationale="Ambiguous entity values; provisional bind to first only",
                        related_step_ids=[step.id],
                        knowledge_source_ids=[journey_doc],
                        attributions=[
                            DecisionAttribution(
                                kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                            ),
                            DecisionAttribution(
                                kind=AttributionKind.INPUT_INTENT, ref="user_intent"
                            ),
                        ],
                    )
                )

            ent = candidates[0]
            field_hint = step.suggested_field_ids[0] if step.suggested_field_ids else None
            entity_bindings.append(
                EntityBinding(
                    entity_type=ent.type,
                    entity_value=ent.value,
                    target_step_id=step.id,
                    target_field_hint=field_hint,
                    knowledge_source_ids=[product_or_enterprise],
                    attributions=[
                        DecisionAttribution(
                            kind=AttributionKind.INPUT_ENTITY,
                            ref=f"{ent.type}:{ent.value}",
                        ),
                        DecisionAttribution(
                            kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                            ref=product_or_enterprise,
                        ),
                    ],
                )
            )
            decisions.append(
                PlanningDecision(
                    id=next_id("d"),
                    kind=DecisionKind.BIND_ENTITY,
                    subject=f"{ent.type}:{_opaque_subject(ent.value)}",
                    rationale=f"Bind accepted entity type {ent.type} to skeleton step {step.id}",
                    related_step_ids=[step.id],
                    knowledge_source_ids=[product_or_enterprise],
                    attributions=[
                        DecisionAttribution(
                            kind=AttributionKind.INPUT_ENTITY,
                            ref=f"{ent.type}:{ent.value}",
                        ),
                        DecisionAttribution(
                            kind=AttributionKind.KNOWLEDGE_DOCUMENT,
                            ref=product_or_enterprise,
                        ),
                    ],
                )
            )

    # Intent-level ambiguities (even when entities exist)
    if planner_input.intent_accepted.ambiguities:
        note = planner_input.intent_accepted.ambiguities[0].get("note", "Ambiguous requirement")
        assumptions.append(
            PlanningAssumption(
                id="A_intent_ambiguity",
                statement=f"Ambiguous requirement from accepted intent: {note}",
                risk=AssumptionRisk.MEDIUM,
                must_confirm=True,
                related_step_ids=list(ordered_ids[:1]),
                knowledge_source_ids=[journey_doc],
            )
        )
        decisions.append(
            PlanningDecision(
                id=next_id("d"),
                kind=DecisionKind.FLAG_ASSUMPTION,
                subject="A_intent_ambiguity",
                rationale="Accepted intent lists ambiguities; do not silently resolve",
                related_step_ids=list(ordered_ids[:1]),
                knowledge_source_ids=[journey_doc],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                    ),
                    DecisionAttribution(
                        kind=AttributionKind.INPUT_INTENT, ref="user_intent"
                    ),
                ],
            )
        )

    # Required information from suggested fields on selected steps
    required_information: list[RequiredInformation] = []
    for step in required:
        for field_id in step.suggested_field_ids:
            required_information.append(
                RequiredInformation(
                    id=field_id,
                    name=field_id.replace("_", " ").title(),
                    required=True,
                    source=RequiredInfoSource.USER,
                    pii=_looks_pii(field_id),
                    target_step_id=step.id,
                    data_type_hint="string",
                    knowledge_source_ids=[journey_doc],
                    attributions=[
                        DecisionAttribution(
                            kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                        ),
                        DecisionAttribution(
                            kind=AttributionKind.SKELETON_STEP, ref=step.id
                        ),
                    ],
                )
            )
            decisions.append(
                PlanningDecision(
                    id=next_id("d"),
                    kind=DecisionKind.REQUIRE_INFORMATION,
                    subject=field_id,
                    rationale=f"Skeleton suggests collecting {field_id} on {step.id}",
                    related_step_ids=[step.id],
                    knowledge_source_ids=[journey_doc],
                    attributions=[
                        DecisionAttribution(
                            kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                        ),
                        DecisionAttribution(
                            kind=AttributionKind.SKELETON_STEP, ref=step.id
                        ),
                    ],
                )
            )

    for miss in planner_input.knowledge_pack.missing_knowledge:
        unk_id = f"U_{miss.asset_id}"
        unknowns.append(
            UnknownRequirement(
                id=unk_id,
                kind=_unknown_kind_for_missing(miss.asset_id, miss.level),
                description=(
                    f"Required knowledge asset {miss.asset_id} is unavailable "
                    f"({miss.reason}); cannot assert enterprise fact."
                ),
                blocking_hint=miss.blocking,
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=[journey_doc],
            )
        )
        assumptions.append(
            PlanningAssumption(
                id=f"A_{miss.asset_id}",
                statement=(
                    f"Proceeding without {miss.asset_id}; downstream must confirm "
                    f"before treating related enterprise details as known."
                ),
                risk=AssumptionRisk.HIGH if miss.blocking else AssumptionRisk.MEDIUM,
                must_confirm=True,
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=[journey_doc],
            )
        )
        decisions.append(
            PlanningDecision(
                id=next_id("d"),
                kind=DecisionKind.MARK_UNKNOWN_REQUIREMENT,
                subject=miss.asset_id,
                rationale="KnowledgePack marks asset missing; do not invent facts",
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=[journey_doc],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                    ),
                    DecisionAttribution(
                        kind=AttributionKind.CONFIG, ref="knowledge_pack.missing_knowledge"
                    ),
                ],
            )
        )
        decisions.append(
            PlanningDecision(
                id=next_id("d"),
                kind=DecisionKind.FLAG_ASSUMPTION,
                subject=f"A_{miss.asset_id}",
                rationale="Explicit assumption required due to missing knowledge",
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=[journey_doc],
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=journey_doc
                    )
                ],
            )
        )

    # Conflicting knowledge — never invent a resolution
    for conflict in planner_input.knowledge_pack.conflicts:
        cdocs = [d for d in conflict.document_ids if d in pack_docs]
        cite = cdocs[:1] or [journey_doc]
        unknowns.append(
            UnknownRequirement(
                id=f"U_conflict_{conflict.conflict_id}",
                kind=UnknownRequirementKind.POLICY,
                description=(
                    f"Knowledge conflict {conflict.conflict_id}: {conflict.description} "
                    "Resolution is unknown; do not invent a winning policy."
                ),
                blocking_hint=conflict.severity == "blocking",
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=cite,
            )
        )
        assumptions.append(
            PlanningAssumption(
                id=f"A_conflict_{conflict.conflict_id}",
                statement=(
                    f"Unresolved knowledge conflict between {', '.join(conflict.document_ids)}; "
                    "human confirmation required before treating either side as authoritative."
                ),
                risk=AssumptionRisk.HIGH
                if conflict.severity == "blocking"
                else AssumptionRisk.MEDIUM,
                must_confirm=True,
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=cite,
            )
        )
        decisions.append(
            PlanningDecision(
                id=next_id("d"),
                kind=DecisionKind.FLAG_ASSUMPTION,
                subject=f"A_conflict_{conflict.conflict_id}",
                rationale="Pack reports knowledge conflict; refuse silent resolution",
                related_step_ids=[ordered_ids[-1]] if ordered_ids else [],
                knowledge_source_ids=cite,
                attributions=[
                    DecisionAttribution(
                        kind=AttributionKind.KNOWLEDGE_DOCUMENT, ref=cite[0]
                    ),
                    DecisionAttribution(
                        kind=AttributionKind.CONFIG, ref="knowledge_pack.conflicts"
                    ),
                ],
            )
        )

    cited = sorted(
        {
            *(d for dec in decisions for d in dec.knowledge_source_ids),
            *(d for b in entity_bindings for d in b.knowledge_source_ids),
            *(d for r in required_information for d in r.knowledge_source_ids),
            *(d for a in assumptions for d in a.knowledge_source_ids),
            *(d for u in unknowns for d in u.knowledge_source_ids),
        }
    )
    cited = [c for c in cited if c in pack_docs]

    status = PlannerStatus.PLANNED
    if assumptions:
        status = PlannerStatus.PLANNED_WITH_ASSUMPTIONS
    if unknowns:
        status = PlannerStatus.PLANNED_WITH_UNKNOWNS

    per_step = {sid: 0.85 for sid in ordered_ids}
    if unknowns and ordered_ids:
        per_step[ordered_ids[-1]] = 0.55

    return PlannerOutput(
        planner_status=status,
        planner_ok=True,
        skeleton_id=planner_input.skeleton.skeleton_id,
        ordered_step_ids=ordered_ids,
        skipped_optional_step_ids=skipped_ids,
        selected_step_ids=ordered_ids,
        decisions=decisions,
        entity_bindings=entity_bindings,
        required_information=required_information,
        assumptions=assumptions,
        unknown_requirements=unknowns,
        knowledge_references=cited,
        confidence=PlanningConfidence(
            overall=0.72 if unknowns or assumptions else 0.88,
            per_step=per_step,
            notes=(
                "Deterministic skeleton-bound plan; gaps/conflicts/ambiguities "
                "surfaced explicitly; excerpt/entity text not executed as instructions"
            ),
        ),
        error=None,
    )


def deterministic_planner_llm_handler(
    system_prompt: str,
    user_prompt: str,
    response_model: type,
) -> PlannerOutput:
    """StubStructuredClient handler: parse input from prompt, plan from input."""
    del system_prompt  # prompt presence checked by agent tests elsewhere
    if response_model is not PlannerOutput:
        raise TypeError(f"Expected PlannerOutput, got {response_model}")
    planner_input = parse_planner_input_from_user_prompt(user_prompt)
    return plan_from_planner_input(planner_input)


def _prefer_doc(docs: list[str], prefixes: tuple[str, ...]) -> str:
    for doc in docs:
        if doc.startswith(prefixes):
            return doc
    return docs[0]


def _opaque_subject(value: str, limit: int = 48) -> str:
    """Avoid echoing prompt-injection payloads into decision subjects."""
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _looks_pii(field_id: str) -> bool:
    lowered = field_id.lower()
    return any(
        token in lowered
        for token in ("name", "address", "phone", "email", "dob", "pan", "aadhaar")
    )


def _unknown_kind_for_missing(asset_id: str, level: int | None) -> UnknownRequirementKind:
    upper = asset_id.upper()
    if upper.startswith("CAP-") or "CAPABILITY" in upper:
        return UnknownRequirementKind.CAPABILITY
    if "API" in upper or level == 5:
        return UnknownRequirementKind.API
    if "ELIG" in upper:
        return UnknownRequirementKind.ELIGIBILITY
    if "FEE" in upper:
        return UnknownRequirementKind.FEE
    if "POLICY" in upper:
        return UnknownRequirementKind.POLICY
    return UnknownRequirementKind.OTHER
