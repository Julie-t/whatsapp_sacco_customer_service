from typing import Any, Literal

from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    query: str
    sacco_id: str | None = None
    language: str | None = None
    content_type: str | None = None
    topic: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    filters: dict[str, Any] | None = None


class RAGSearchResult(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    source: str = ""
    sacco_id: str = ""
    language: str = ""
    topic: str = ""
    content_type: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGSearchResponse(BaseModel):
    query: str
    results: list[RAGSearchResult] = Field(default_factory=list)
