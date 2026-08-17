"""
Platform Capability Agent — core reasoning.

Architecture (matches the brief's non-chatbot pipeline):

    Request -> normalize -> retrieve platform knowledge -> compare requirements
    against knowledge -> classify each capability -> compute confidence
    -> build structured, sourced response

Design decision: no LLM in the decision path.
-----------------------------------------------
The comparison logic below (supported / unsupported / needs investigation /
conflict) is plain, deterministic set comparison against the knowledge index —
not an LLM call. This is a deliberate choice, not a shortcut:

- The one hard requirement in the brief is "the agent should not invent
  capabilities when knowledge is unavailable." An LLM asked to reason over
  retrieved context can still fill gaps with plausible-sounding pretrained
  knowledge. A deterministic lookup structurally cannot do that: a capability is
  either found in the index or it isn't.
- Every field in the output (supported/unsupported/constraints) must be
  traceable to a specific knowledge file for audit purposes. Deterministic
  lookup gives that for free; free-text LLM generation does not.
- It keeps the agent fully unit-testable without mocking a model.

An LLM is still a natural fit *on top* of this — e.g. to turn `reasoning` into a
friendlier paragraph for a human, or to help a journey planner extract the
`required_capabilities` list from a natural-language journey description in the
first place. Both are optional, additive steps that consume this agent's output
or feed its input; neither is allowed to change what counts as "supported."
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .knowledge_loader import PlatformKnowledge, load_knowledge_base
from .normalize import normalize_capability, normalize_platform
from .schema import AgentResponse, CapabilityRequest, Conflict, KnowledgeSourceRef, SupportStatus

# Tuning: how much a conflict vs. an undocumented capability should hurt
# confidence. Conflicts are weighted higher because they indicate the
# knowledge base itself is wrong/stale somewhere, which is worse than simply
# being incomplete.
_CONFLICT_PENALTY = 0.5
_UNKNOWN_PENALTY = 0.3


def _error(code: str, message: str) -> dict:
    """Standard failure envelope, matching the Tool Layer's `ok: false` + `error.code` contract."""
    return {"ok": False, "error": {"code": code, "message": message}}


class PlatformCapabilityAgent:
    """
    Implements two read-only tools from the agentic architecture's Tool Layer —
    `get_platform_capabilities` and `check_supported_component` — plus a
    deterministic `evaluate()` that composes `check_supported_component` once
    per required capability. In the full architecture a Planner LLM decides
    *when* to call these tools; here, since this slice has no planner, that
    composition is done by plain orchestration code, which is exactly how the
    architecture classifies this kind of work (class A, deterministic) —
    not LLM reasoning. No LLM is used anywhere in this module.
    """

    def __init__(self, knowledge_dir: str):
        self.knowledge_dir = knowledge_dir
        self.knowledge_index: Dict[str, PlatformKnowledge] = {}
        self.excluded_non_approved: Dict[str, List[str]] = {}
        self.reload()

    def reload(self) -> None:
        """Re-read the knowledge base from disk (useful after editing markdown files)."""
        self.knowledge_index, self.excluded_non_approved = load_knowledge_base(self.knowledge_dir)

    # -- Tool: get_platform_capabilities -------------------------------------

    def get_platform_capabilities(self, platform: str, keys: Optional[List[str]] = None) -> dict:
        """
        Tool contract: in {platform, keys?} -> out {ok, capabilities, unsupported,
        constraints, sources} | {ok: false, error}.

        Read-only. Scoped to exactly the platform requested — never returns
        data for any other platform, and never widens scope on its own.
        """
        platform_id = normalize_platform(platform)
        pk = self.knowledge_index.get(platform_id)
        if pk is None:
            if platform_id in self.excluded_non_approved:
                return _error(
                    "not_retrievable",
                    f"Documentation for '{platform_id}' exists but is not yet approved "
                    f"({', '.join(self.excluded_non_approved[platform_id])}).",
                )
            return _error("not_found", f"No knowledge document found for platform '{platform_id}'.")

        want = {normalize_capability(k) for k in keys} if keys else None
        supported = {cap: [f.description for f in facts] for cap, facts in pk.supported.items()
                     if want is None or cap in want}
        unsupported = {cap: [f.description for f in facts] for cap, facts in pk.unsupported.items()
                       if want is None or cap in want}
        constraints = [c.text for c in pk.constraints if want is None or c.capability in (want | {None})]
        sources = sorted({pk.document_id_for(sf) for sf in pk.source_files})
        return {
            "ok": True,
            "platform": platform_id,
            "capabilities": supported,
            "unsupported": unsupported,
            "constraints": constraints,
            "sources": sources,
        }

    # -- Tool: check_supported_component -------------------------------------

    def check_supported_component(self, platform: str, pattern: str) -> dict:
        """
        Tool contract: in {platform, pattern} -> out {ok, supported, constraints,
        sources} | {ok: false, error}.

        `supported` is `true`, `false`, or `"unknown"` — never guessed. Read-only
        registry lookup; no reasoning beyond exact-match retrieval.
        """
        platform_id = normalize_platform(platform)
        pk = self.knowledge_index.get(platform_id)
        if pk is None:
            if platform_id in self.excluded_non_approved:
                return _error(
                    "not_retrievable",
                    f"Documentation for '{platform_id}' exists but is not yet approved.",
                )
            return _error("not_found", f"No knowledge document found for platform '{platform_id}'.")

        cap = normalize_capability(pattern)
        sup_facts = pk.supported.get(cap, [])
        unsup_facts = pk.unsupported.get(cap, [])
        constraints = [c.text for c in pk.constraints if c.capability == cap]

        sup_files = sorted({f.source_file for f in sup_facts})
        unsup_files = sorted({f.source_file for f in unsup_facts})

        if sup_facts and unsup_facts:
            return {
                "ok": True,
                "supported": "conflict",
                "supported_in_files": sup_files,
                "unsupported_in_files": unsup_files,
                "supported_in": sorted({pk.document_id_for(f) for f in sup_files}),
                "unsupported_in": sorted({pk.document_id_for(f) for f in unsup_files}),
                "constraints": constraints,
                "sources": sorted(set(sup_files) | set(unsup_files)),
            }
        if sup_facts:
            return {"ok": True, "supported": True, "constraints": constraints, "sources": sup_files}
        if unsup_facts:
            return {"ok": True, "supported": False, "constraints": constraints, "sources": unsup_files}
        return {"ok": True, "supported": "unknown", "constraints": [], "sources": []}

    def evaluate(self, request: CapabilityRequest) -> AgentResponse:
        """
        Answers "can this platform support this journey?" by composing
        `check_supported_component` once per required capability — the same
        deterministic orchestration a Journey Planner would perform after
        deciding it needs a full capability check, not a single lookup.
        """
        if not request.required_capabilities:
            raise ValueError("required_capabilities must contain at least one capability")

        platform_id = normalize_platform(request.platform)
        required_ordered: List[str] = []
        seen = set()
        for raw in request.required_capabilities:
            cap = normalize_capability(raw)
            if cap not in seen:
                seen.add(cap)
                required_ordered.append(cap)

        platform = self.knowledge_index.get(platform_id)

        if platform is None:
            return self._unknown_platform_response(platform_id, required_ordered)

        return self._evaluate_against_platform(platform, required_ordered)

    # -- internal -----------------------------------------------------------

    def _unknown_platform_response(self, platform_id: str, required: List[str]) -> AgentResponse:
        known = ", ".join(sorted(self.knowledge_index.keys())) or "(none loaded)"
        pending = platform_id in self.excluded_non_approved
        reasoning = [f"No approved knowledge document found for platform '{platform_id}'."]
        if pending:
            reasoning.append(
                f"Note: documentation exists for '{platform_id}' but is not yet approved "
                f"for retrieval: {', '.join(self.excluded_non_approved[platform_id])}. "
                f"This is different from no documentation existing at all — flag for "
                f"governance follow-up rather than treating it as fully unknown."
            )
        reasoning.append(f"Known (approved) platforms: {known}.")
        reasoning.append("Refusing to guess capabilities for an undocumented or unapproved platform.")
        return AgentResponse(
            platform=platform_id,
            status=(SupportStatus.PLATFORM_PENDING_APPROVAL.value if pending
                    else SupportStatus.UNKNOWN_PLATFORM.value),
            supported=False,
            requested_capabilities=required,
            supported_capabilities=[],
            unsupported_capabilities=[],
            capabilities_needing_investigation=required,
            conflicts=[],
            constraints=[],
            knowledge_sources=[],
            confidence=0.0,
            reasoning=reasoning,
        )

    @staticmethod
    def _higher_authority(platform: PlatformKnowledge, sup_files: List[str],
                           unsup_files: List[str]) -> Optional[str]:
        """
        Informational only: which side of a conflict should likely be treated as
        current. Never used to auto-resolve the conflict — a human still decides.

        An explicit `supersedes` declaration is a stated governance fact (a
        document author asserting "this replaces that document_id"), so it is
        checked first and wins outright if present. `authority_rank` is a
        fallback heuristic for when no document has explicitly declared a
        supersession relationship over the other. The two are expected to
        agree, but nothing enforces that at authoring time, so `supersedes`
        must be checked independently rather than assumed to already be
        reflected in `authority_rank`.
        """
        sup_ids = {platform.document_id_for(f) for f in sup_files}
        unsup_ids = {platform.document_id_for(f) for f in unsup_files}

        for f in sup_files:
            doc = platform.documents.get(f)
            if doc and unsup_ids & set(doc.supersedes):
                return doc.document_id
        for f in unsup_files:
            doc = platform.documents.get(f)
            if doc and sup_ids & set(doc.supersedes):
                return doc.document_id

        sup_rank = max((platform.authority_rank_for(f) or -1) for f in sup_files) if sup_files else -1
        unsup_rank = max((platform.authority_rank_for(f) or -1) for f in unsup_files) if unsup_files else -1
        if sup_rank == unsup_rank:
            return None
        winning_files = sup_files if sup_rank > unsup_rank else unsup_files
        best_file = max(winning_files, key=lambda f: platform.authority_rank_for(f) or -1)
        return platform.document_id_for(best_file)

    def _evaluate_against_platform(self, platform: PlatformKnowledge, required: List[str]) -> AgentResponse:
        resolved_supported: List[str] = []
        resolved_unsupported: List[str] = []
        needs_investigation: List[str] = []
        conflicts: List[Conflict] = []
        used_sources: set = set()
        reasoning: List[str] = [
            f"Loaded knowledge for platform '{platform.platform_id}' "
            f"({platform.platform_full_name}) from {', '.join(platform.source_files)}."
        ]

        for cap in required:
            result = self.check_supported_component(platform.platform_id, cap)
            supported = result["supported"]

            if supported == "conflict":
                conflicts.append(Conflict(
                    capability=cap,
                    supported_in=result["supported_in_files"],
                    unsupported_in=result["unsupported_in_files"],
                    higher_authority_source=self._higher_authority(
                        platform, result["supported_in_files"], result["unsupported_in_files"]
                    ),
                ))
                used_sources.update(result["sources"])
                reasoning.append(
                    f"'{cap}': CONFLICTING knowledge — marked supported in "
                    f"{result['supported_in_files']} but unsupported in "
                    f"{result['unsupported_in_files']}. Not resolved automatically; "
                    f"flagged for human review."
                )
            elif supported is True:
                resolved_supported.append(cap)
                used_sources.update(result["sources"])
                reasoning.append(f"'{cap}': supported (source: {result['sources']}).")
            elif supported is False:
                resolved_unsupported.append(cap)
                used_sources.update(result["sources"])
                reasoning.append(f"'{cap}': NOT supported (source: {result['sources']}).")
            else:  # "unknown"
                needs_investigation.append(cap)
                reasoning.append(
                    f"'{cap}': not documented for {platform.platform_id} in any known "
                    f"source. Not assuming support or non-support."
                )

        constraints_out = []
        for c in platform.constraints:
            if c.capability is None or c.capability in required:
                constraints_out.append(c.text)
                used_sources.add(c.source_file)

        status, supported = self._classify(resolved_supported, resolved_unsupported,
                                            needs_investigation, conflicts)
        confidence = self._confidence(len(required), len(resolved_supported) + len(resolved_unsupported),
                                       len(conflicts), len(needs_investigation))

        reasoning.append(f"Overall status: {status.value} (confidence {confidence}).")

        source_docs = [
            KnowledgeSourceRef(
                document_id=platform.document_id_for(sf),
                source_file=sf,
                authority_rank=platform.authority_rank_for(sf),
                status=platform.documents[sf].status if sf in platform.documents else "approved",
            )
            for sf in sorted(used_sources)
        ]

        return AgentResponse(
            platform=platform.platform_id,
            status=status.value,
            supported=supported,
            requested_capabilities=required,
            supported_capabilities=resolved_supported,
            unsupported_capabilities=resolved_unsupported,
            capabilities_needing_investigation=needs_investigation,
            conflicts=conflicts,
            constraints=constraints_out,
            knowledge_sources=sorted(used_sources),
            confidence=confidence,
            reasoning=reasoning,
            knowledge_source_documents=source_docs,
        )

    @staticmethod
    def _classify(resolved_supported, resolved_unsupported, needs_investigation, conflicts):
        if conflicts or needs_investigation:
            return SupportStatus.INSUFFICIENT_KNOWLEDGE, False
        if resolved_unsupported and resolved_supported:
            return SupportStatus.PARTIALLY_SUPPORTED, False
        if resolved_unsupported and not resolved_supported:
            return SupportStatus.NOT_SUPPORTED, False
        return SupportStatus.FULLY_SUPPORTED, True

    @staticmethod
    def _confidence(total: int, resolved: int, conflict_count: int, unknown_count: int) -> float:
        if total == 0:
            return 0.0
        base = resolved / total
        penalty = (conflict_count * _CONFLICT_PENALTY + unknown_count * _UNKNOWN_PENALTY) / total
        return round(max(0.0, min(1.0, base - penalty)), 2)
