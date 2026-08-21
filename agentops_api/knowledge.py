"""Knowledge Repository Engine — filesystem index over Knowledge_Base.

This is a real indexer, not a mock. Retrieval is keyword/heading based.
Vector embedding is not implemented and is reported as such.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentops_api.config import KNOWLEDGE_ROOT, REPO_ROOT, UPLOAD_DIR
from hdfc_journey.contracts.knowledge_pack import (
    AttributionIndex,
    KnowledgeExcerpt,
    KnowledgePack,
    KnowledgeReference,
    MissingKnowledge,
)

LEVEL_FROM_PATH = {
    "Level 1 - Enterprise Knowledge": 1,
    "Level 2 - Product Knowledge": 2,
    "Level 3 - Platform Knowledge": 3,
    "Updated Design System": 4,
}

INGESTION_STAGES = (
    "upload",
    "parse",
    "chunk",
    "tag",
    "version",
    "embed",
    "index",
    "approve",
    "available",
)


def _iso_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _document_id_for(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).as_posix()
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9]+", "-", path.stem).strip("-").upper()[:24]
    return f"KB-{stem}-{digest}"


def _category_for(path: Path) -> str:
    try:
        rel = path.relative_to(KNOWLEDGE_ROOT)
        return rel.parts[0] if rel.parts else "Uncategorised"
    except ValueError:
        return "Uploaded"


def _level_for(path: Path) -> int | None:
    try:
        rel = path.relative_to(KNOWLEDGE_ROOT)
    except ValueError:
        return None
    for prefix, level in LEVEL_FROM_PATH.items():
        if rel.parts and rel.parts[0] == prefix:
            return level
    return None


def _file_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def _chunk_markdown(text: str, document_id: str, limit: int = 12) -> list[dict[str, Any]]:
    sections: list[tuple[str, list[str]]] = []
    current = "Overview"
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if buf:
                sections.append((current, buf))
            current = line.lstrip("#").strip() or current
            buf = []
        else:
            buf.append(line)
    if buf:
        sections.append((current, buf))
    chunks = []
    for index, (heading, lines) in enumerate(sections[:limit]):
        body = "\n".join(lines).strip()
        if not body:
            continue
        excerpt = body[:600]
        chunks.append(
            {
                "chunk_id": f"{document_id}#{index}",
                "heading": heading,
                "text": excerpt,
                "chars": len(body),
            }
        )
    return chunks


def scan_bundled_documents() -> list[dict[str, Any]]:
    if not KNOWLEDGE_ROOT.is_dir():
        return []
    docs: list[dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".pdf", ".txt"}:
            continue
        if path.name.startswith("."):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        page_count = None
        if path.suffix.lower() == ".md":
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                page_count = max(1, text.count("\n") // 40)
            except OSError:
                text = ""
        docs.append(
            {
                "document_id": _document_id_for(path),
                "file_name": path.name,
                "file_type": _file_type(path),
                "version": "bundled",
                "uploaded_at": _iso_from_mtime(path),
                "uploaded_by": "knowledge-base",
                "status": "indexed",
                "processing_status": "complete",
                "indexing_status": "indexed",
                "size_bytes": size,
                "page_count": page_count,
                "category": _category_for(path),
                "knowledge_level": _level_for(path),
                "last_updated": _iso_from_mtime(path),
                "source_path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "origin": "bundled",
                "error_message": None,
                "ingestion": _bundled_ingestion_status(),
            }
        )
    return docs


def _bundled_ingestion_status() -> list[dict[str, Any]]:
    stages = []
    for stage in INGESTION_STAGES:
        if stage == "embed":
            stages.append(
                {
                    "stage": stage,
                    "status": "skipped",
                    "note": "Vector embedding is not yet instrumented.",
                }
            )
        elif stage == "upload":
            stages.append({"stage": stage, "status": "completed", "note": "Shipped with the repository."})
        else:
            stages.append({"stage": stage, "status": "completed"})
    return stages


def document_preview(rel_path: str, max_chars: int = 8000) -> dict[str, Any]:
    candidate = Path(rel_path)
    path = candidate.resolve() if candidate.is_absolute() else (REPO_ROOT / rel_path).resolve()
    allowed_roots = (REPO_ROOT.resolve(), UPLOAD_DIR.resolve())
    if not any(root == path or root in path.parents for root in allowed_roots):
        raise PermissionError("Path is outside the repository")
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    if path.suffix.lower() not in {".md", ".txt"}:
        return {
            "preview_available": False,
            "reason": f"Preview is not available for .{path.suffix.lstrip('.')} files.",
            "file_name": path.name,
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > max_chars
    return {
        "preview_available": True,
        "file_name": path.name,
        "content": text[:max_chars],
        "truncated": truncated,
        "chunks": _chunk_markdown(text, _document_id_for(path)),
    }


def retrieve_pack(*, utterance: str, platform: str | None, intent: str | None) -> dict[str, Any]:
    """Keyword retrieval over markdown knowledge files. Not a vector search."""
    query_terms = {t.lower() for t in re.findall(r"[a-zA-Z]{3,}", utterance)}
    if intent:
        query_terms.update(intent.lower().replace("_", " ").split())
    if platform:
        query_terms.add(platform.lower())

    scored: list[tuple[float, Path, str, list[dict[str, Any]]]] = []
    for path in KNOWLEDGE_ROOT.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hay = f"{path.name}\n{text[:4000]}".lower()
        hits = sum(1 for term in query_terms if term in hay)
        if hits == 0:
            continue
        doc_id = _document_id_for(path)
        chunks = _chunk_markdown(text, doc_id, limit=4)
        relevance = min(1.0, hits / max(4, len(query_terms)))
        scored.append((relevance, path, doc_id, chunks))

    scored.sort(key=lambda row: row[0], reverse=True)
    top = scored[:8]
    references = []
    excerpts = []
    by_document = []
    by_chunk = []
    for relevance, path, doc_id, chunks in top:
        level = _level_for(path) or 1
        references.append(
            KnowledgeReference(
                asset_id=doc_id,
                level=level,
                path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                sections=[c["heading"] for c in chunks[:3]],
                chunk_ids=[c["chunk_id"] for c in chunks[:3]],
                relevance=round(relevance, 3),
                freshness="current",
                status="loaded",
            )
        )
        by_document.append(doc_id)
        for chunk in chunks[:2]:
            excerpts.append(
                KnowledgeExcerpt(
                    chunk_id=chunk["chunk_id"],
                    document_id=doc_id,
                    section_path=[chunk["heading"]],
                    text=chunk["text"],
                    relevance=round(relevance, 3),
                )
            )
            by_chunk.append(chunk["chunk_id"])

    missing: list[MissingKnowledge] = []
    if intent and not any("API" in (r.path or "") for r in references):
        missing.append(
            MissingKnowledge(
                asset_id=f"TECH-{intent}-APIS",
                level=5,
                reason="Level 5 technical API catalogue is not present in Knowledge_Base.",
                blocking=True,
            )
        )

    pack = KnowledgePack(
        pack_id=f"{intent or 'UNKNOWN'}|{platform or 'unspecified'}|kb-v1",
        registry_version="knowledge-base-fs-v1",
        references=references,
        excerpts=excerpts,
        missing_knowledge=missing,
        attribution_index=AttributionIndex(by_document=by_document, by_chunk=by_chunk),
        retrieval_policy="keyword over Knowledge_Base markdown; embedding not instrumented",
    )
    return {
        "pack": pack,
        "query_terms": sorted(query_terms),
        "documents_considered": len(list(KNOWLEDGE_ROOT.rglob("*.md"))),
        "documents_retrieved": len(references),
        "retrieval_method": "keyword",
        "embedding_used": False,
    }


def repository_stats(uploaded_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    bundled = scan_bundled_documents()
    uploaded = uploaded_rows or []
    failed = [d for d in uploaded if d.get("status") == "failed"]
    processing = [d for d in uploaded if d.get("status") in {"uploaded", "processing"}]
    return {
        "healthy": KNOWLEDGE_ROOT.is_dir(),
        "knowledge_root": str(KNOWLEDGE_ROOT.relative_to(REPO_ROOT)).replace("\\", "/"),
        "documents_indexed": len(bundled) + sum(1 for d in uploaded if d.get("indexing_status") == "indexed"),
        "documents_uploaded": len(uploaded),
        "documents_processed": sum(1 for d in uploaded if d.get("processing_status") == "complete"),
        "failed_documents": len(failed),
        "processing_documents": len(processing),
        "knowledge_sources": sorted({d["category"] for d in bundled}),
        "retrieval_method": "keyword",
        "embedding_status": "not_instrumented",
        "version": "knowledge-base-fs-v1",
    }


def save_upload(filename: str, content: bytes, uploaded_by: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "document"
    dest = UPLOAD_DIR / safe
    counter = 1
    while dest.exists():
        dest = UPLOAD_DIR / f"{dest.stem}-{counter}{dest.suffix}"
        counter += 1
    dest.write_bytes(content)
    return dest
