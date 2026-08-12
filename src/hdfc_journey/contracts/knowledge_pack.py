"""KnowledgePack contract — closed world for Planner citations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class KnowledgeReference(BaseModel):
    """One document (or section slice) included in the pack."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(..., min_length=1, description="Document ID; citation key.")
    level: int = Field(..., ge=1, le=5)
    path: str | None = None
    sections: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness: str = Field(default="current")
    status: str = Field(default="loaded")
    authority_rank: int | None = None


class KnowledgeExcerpt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    section_path: list[str] = Field(default_factory=list)
    text: str
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)


class MissingKnowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    level: int | None = Field(default=None, ge=1, le=5)
    reason: str
    blocking: bool = False


class KnowledgeConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    document_ids: list[str] = Field(..., min_length=1)
    severity: str = Field(default="warning")
    description: str


class AttributionIndex(BaseModel):
    """Closed-world allowlists for Planner knowledge_source_ids / chunk refs."""

    model_config = ConfigDict(extra="forbid")

    by_document: list[str] = Field(default_factory=list)
    by_chunk: list[str] = Field(default_factory=list)

    @field_validator("by_document", "by_chunk", mode="before")
    @classmethod
    def _dedupe(cls, value: Any) -> list[str]:
        if value is None:
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out


class KnowledgePack(BaseModel):
    """Assembled pack written by Knowledge Retrieval; immutable for Planner."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str
    registry_version: str | None = None
    query_id: str | None = None
    references: list[KnowledgeReference] = Field(default_factory=list)
    excerpts: list[KnowledgeExcerpt] = Field(default_factory=list)
    missing_knowledge: list[MissingKnowledge] = Field(default_factory=list)
    conflicts: list[KnowledgeConflict] = Field(default_factory=list)
    attribution_index: AttributionIndex = Field(default_factory=AttributionIndex)
    retrieval_policy: str | None = "journey > product > platform > enterprise"
    assembled_at: datetime | None = None

    @model_validator(mode="after")
    def _sync_attribution(self) -> KnowledgePack:
        """Ensure attribution_index covers every reference/excerpt document and chunk."""
        docs = set(self.attribution_index.by_document)
        chunks = set(self.attribution_index.by_chunk)
        for ref in self.references:
            docs.add(ref.asset_id)
            chunks.update(ref.chunk_ids)
        for ex in self.excerpts:
            docs.add(ex.document_id)
            chunks.add(ex.chunk_id)
        self.attribution_index = AttributionIndex(
            by_document=sorted(docs),
            by_chunk=sorted(chunks),
        )
        return self

    def document_ids(self) -> set[str]:
        return set(self.attribution_index.by_document)

    def chunk_ids(self) -> set[str]:
        return set(self.attribution_index.by_chunk)

    def allows_document(self, document_id: str) -> bool:
        return document_id in self.document_ids()

    def allows_chunk(self, chunk_id: str) -> bool:
        return chunk_id in self.chunk_ids()
