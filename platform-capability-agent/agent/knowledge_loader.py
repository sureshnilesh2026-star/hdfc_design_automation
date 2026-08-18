"""
Knowledge loader: turns the markdown knowledge base into structured, queryable
Python objects.

Retrieval approach
-------------------
This is deliberately NOT semantic/vector search. The knowledge base is small and
the questions it answers are precise ("does platform X support capability Y?"),
so retrieval is exact-match lookup by platform ID and capability ID against a
structured index built once at load time. This avoids the failure mode of a
similarity search returning a plausible-but-wrong chunk, and it makes every
answer traceable to an exact line in an exact file.

Knowledge file convention
--------------------------
Each markdown file describes ONE platform (frontmatter `platform:` field) and
must use these section headers:

    ## Supported Capabilities
    ## Unsupported Capabilities
    ## Constraints
    ## Notes   (optional, free text, not parsed structurally)

Capability bullet lines look like:

    - `capability_id`: free text description

A bullet under "Supported Capabilities" or "Unsupported Capabilities" that
doesn't match this exact shape (e.g. missing backticks) raises `ValueError`
naming the file and the offending line, rather than being silently dropped —
a capability quietly missing from the index is a worse failure mode than a
loud one for something a validator will trust. Constraints are more lenient
(see below) because an untied free-text constraint is a valid, intentional
form, not a formatting mistake.

Constraint bullet lines look like:

    - `capability_id`: free text constraint

or, for a constraint not tied to one capability:

    - free text constraint

Multiple files may describe the same platform (e.g. an old doc plus a newer one).
The loader merges them and flags any capability that is marked supported in one
file and unsupported in another as a CONFLICT rather than silently picking one.

Metadata contract
-----------------
Frontmatter follows the enterprise Knowledge Layer's metadata contract:
`document_id`, `level`, `level_name`, `domain`, `product`, `platform`,
`tags` (bracket list), `status`, `version`, `last_updated`, `authority_rank`,
`supersedes` (bracket list of document_ids), `conflicts_with` (bracket list).

Only documents with `status: approved` are loaded into the retrievable index —
this mirrors the rule "only status=approved is retrievable by default."
A document that exists but isn't approved is tracked separately (see
`load_knowledge_base`'s second return value) so the agent can distinguish
"no knowledge exists for this platform" from "knowledge exists but hasn't
cleared governance yet" — those are different situations and deserve
different messages, not the same generic "unknown platform" response.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .normalize import normalize_capability, normalize_platform

_BULLET_WITH_ID = re.compile(r"^-\s*`([a-zA-Z0-9_\-]+)`\s*:\s*(.*)$")
_SECTION_HEADER = re.compile(r"^##\s+(.*?)\s*$")
_FRONTMATTER_KV = re.compile(r"^([a-zA-Z0-9_]+):\s*(.*)$")
_BRACKET_LIST = re.compile(r"^\[(.*)\]$")


@dataclass
class CapabilityFact:
    capability: str
    description: str
    source_file: str


@dataclass
class ConstraintFact:
    capability: Optional[str]
    text: str
    source_file: str


@dataclass
class DocumentMeta:
    """One knowledge file's metadata-contract fields."""
    document_id: str
    source_file: str
    level: Optional[int] = None
    domain: Optional[str] = None
    status: str = "approved"
    version: Optional[str] = None
    authority_rank: Optional[int] = None
    supersedes: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)


@dataclass
class PlatformKnowledge:
    platform_id: str
    platform_full_name: str
    source_files: List[str] = field(default_factory=list)
    supported: Dict[str, List[CapabilityFact]] = field(default_factory=dict)
    unsupported: Dict[str, List[CapabilityFact]] = field(default_factory=dict)
    constraints: List[ConstraintFact] = field(default_factory=list)
    documents: Dict[str, DocumentMeta] = field(default_factory=dict)  # keyed by source_file

    def all_documented_capabilities(self) -> set:
        return set(self.supported.keys()) | set(self.unsupported.keys())

    def document_id_for(self, source_file: str) -> str:
        doc = self.documents.get(source_file)
        return doc.document_id if doc else source_file

    def authority_rank_for(self, source_file: str) -> Optional[int]:
        doc = self.documents.get(source_file)
        return doc.authority_rank if doc else None


def _coerce_value(raw: str):
    """Bracket lists (`[a, b]`) become Python lists; everything else stays a string."""
    m = _BRACKET_LIST.match(raw.strip())
    if m:
        inner = m.group(1).strip()
        if not inner:
            return []
        return [item.strip() for item in inner.split(",") if item.strip()]
    return raw


def _parse_frontmatter(lines: List[str]) -> Tuple[dict, int]:
    """Parse a leading `---\\n key: value \\n---` block. Returns (dict, next_line_index)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    meta = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        m = _FRONTMATTER_KV.match(lines[i].strip())
        if m:
            meta[m.group(1)] = _coerce_value(m.group(2).strip())
        i += 1
    return meta, i + 1


def _parse_sections(lines: List[str]) -> Dict[str, List[str]]:
    """Split remaining lines into {section_title_lower: [body_lines]} by '## ' headers."""
    sections: Dict[str, List[str]] = {}
    current = None
    for line in lines:
        header_match = _SECTION_HEADER.match(line)
        if header_match:
            current = header_match.group(1).strip().lower()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def _fold_bullets(body_lines: List[str]) -> List[str]:
    """
    Join soft-wrapped continuation lines back onto their bullet.

    A markdown bullet like:

        - `document_upload`: some long description that
          wraps onto the next line.

    is written across multiple physical lines for readability. Any non-blank
    line that doesn't start a new bullet ('-') is folded onto the previous
    bullet with a single space, so downstream regex matching sees one logical
    line per bullet regardless of how the source file wrapped it.
    """
    folded: List[str] = []
    for raw in body_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            folded.append(stripped)
        elif folded:
            folded[-1] = f"{folded[-1]} {stripped}"
        # else: stray continuation line before any bullet — ignore
    return folded


def _parse_single_file(path: Path) -> Tuple[PlatformKnowledge, DocumentMeta]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    meta, body_start = _parse_frontmatter(lines)

    platform_raw = meta.get("platform", "")
    if not platform_raw:
        raise ValueError(f"{path.name}: missing required frontmatter field 'platform'")
    platform_id = normalize_platform(platform_raw)
    full_name = meta.get("platform_full_name", platform_raw)

    sections = _parse_sections(lines[body_start:])
    source_name = path.name

    doc_meta = DocumentMeta(
        document_id=meta.get("document_id", source_name),
        source_file=source_name,
        level=int(meta["level"]) if str(meta.get("level", "")).strip().isdigit() else None,
        domain=meta.get("domain") or None,
        status=(meta.get("status") or "approved"),
        version=meta.get("version") or None,
        authority_rank=int(meta["authority_rank"]) if str(meta.get("authority_rank", "")).strip().isdigit() else None,
        supersedes=meta.get("supersedes") if isinstance(meta.get("supersedes"), list) else [],
        conflicts_with=meta.get("conflicts_with") if isinstance(meta.get("conflicts_with"), list) else [],
    )

    pk = PlatformKnowledge(platform_id=platform_id, platform_full_name=full_name,
                            source_files=[source_name],
                            documents={source_name: doc_meta})

    for bullet in _fold_bullets(sections.get("supported capabilities", [])):
        m = _BULLET_WITH_ID.match(bullet)
        if not m:
            raise ValueError(
                f"{path.name}: malformed bullet in 'Supported Capabilities' — expected "
                f"'- `capability_id`: description', got: {bullet!r}"
            )
        cap = normalize_capability(m.group(1))
        pk.supported.setdefault(cap, []).append(
            CapabilityFact(cap, m.group(2).strip(), source_name)
        )

    for bullet in _fold_bullets(sections.get("unsupported capabilities", [])):
        m = _BULLET_WITH_ID.match(bullet)
        if not m:
            raise ValueError(
                f"{path.name}: malformed bullet in 'Unsupported Capabilities' — expected "
                f"'- `capability_id`: description', got: {bullet!r}"
            )
        cap = normalize_capability(m.group(1))
        pk.unsupported.setdefault(cap, []).append(
            CapabilityFact(cap, m.group(2).strip(), source_name)
        )

    for bullet in _fold_bullets(sections.get("constraints", [])):
        m = _BULLET_WITH_ID.match(bullet)
        if m:
            cap = normalize_capability(m.group(1))
            pk.constraints.append(ConstraintFact(cap, m.group(2).strip(), source_name))
        else:
            text_only = bullet.lstrip("- ").strip()
            if text_only:
                pk.constraints.append(ConstraintFact(None, text_only, source_name))

    return pk, doc_meta


def _merge(a: PlatformKnowledge, b: PlatformKnowledge) -> PlatformKnowledge:
    a.source_files.extend(b.source_files)
    a.documents.update(b.documents)
    for cap, facts in b.supported.items():
        a.supported.setdefault(cap, []).extend(facts)
    for cap, facts in b.unsupported.items():
        a.unsupported.setdefault(cap, []).extend(facts)
    a.constraints.extend(b.constraints)
    return a


def _capability_markdown_paths(directory: Path) -> List[Path]:
    """Prefer machine-readable ``*capabilities*.md`` companions.

    Shared ``Knowledge_Base/Level 3`` also contains large narrative docs and
    ``PLATFORM_IDS.md``; those must not be parsed. If a directory has no
    capability-named files (e.g. tempfile fixtures in unit tests), fall back to
    every ``*.md`` file.
    """
    capability_paths = sorted(directory.glob("*capabilities*.md"))
    if capability_paths:
        return capability_paths
    return sorted(directory.glob("*.md"))


def load_knowledge_base(directory: str) -> Tuple[Dict[str, PlatformKnowledge], Dict[str, List[str]]]:
    """
    Load and merge capability markdown files in `directory` into a
    {platform_id: PlatformKnowledge} index, honoring the metadata contract's
    retrieval gate: only `status: approved` documents are indexed.

    Returns (approved_index, excluded_non_approved) where `excluded_non_approved`
    maps platform_id -> ["document_id (status)", ...] for documents that exist on
    disk but were excluded because they haven't cleared governance. This lets the
    agent tell "no knowledge exists" apart from "knowledge exists but isn't approved
    yet" instead of collapsing both into one generic unknown-platform response.
    """
    index: Dict[str, PlatformKnowledge] = {}
    excluded: Dict[str, List[str]] = {}
    root = Path(directory)
    for path in _capability_markdown_paths(root):
        pk, doc_meta = _parse_single_file(path)
        status = (doc_meta.status or "approved").strip().lower()
        doc_meta.status = status
        if status != "approved":
            excluded.setdefault(pk.platform_id, []).append(
                f"{doc_meta.document_id} (status={doc_meta.status})"
            )
            continue
        if pk.platform_id in index:
            index[pk.platform_id] = _merge(index[pk.platform_id], pk)
        else:
            index[pk.platform_id] = pk
    return index, excluded
