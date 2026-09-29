from typing import Any

from pydantic import BaseModel, Field


class RAGDocument(BaseModel):
    """Typed internal representation of a knowledge item.

    The schema is intentionally generic so it can be reused across SACCO
    clients. ``sacco_id`` exists conceptually even though the MVP initially
    operates on a single demo SACCO.
    """

    document_id: str
    title: str
    content: str
    source: str = ""
    content_type: str = "general"
    sacco_id: str = ""
    language: str = "en"
    topic: str = ""
    audience: str = ""
    goals: list[str] = Field(default_factory=list)
    effective_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGChunk(BaseModel):
    """A deterministic chunk of a :class:`RAGDocument`.

    Chunking preserves all document-level metadata so filtering and
    evidence display keep working at chunk granularity.
    """

    chunk_id: str
    document_id: str
    chunk_index: int
    title: str
    content: str
    source: str = ""
    content_type: str = "general"
    sacco_id: str = ""
    language: str = "en"
    topic: str = ""
    audience: str = ""
    goals: list[str] = Field(default_factory=list)
    effective_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGResult(BaseModel):
    """A single structured retrieval result (evidence, not an answer)."""

    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    source: str = ""
    sacco_id: str = ""
    language: str = "en"
    topic: str = ""
    content_type: str = "general"
    metadata: dict[str, Any] = Field(default_factory=dict)
