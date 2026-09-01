from pydantic import BaseModel, Field


class RAGAnswerRequest(BaseModel):
    query: str
    sacco_id: str | None = None
    language: str | None = None
    content_type: str | None = None
    topic: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    conversation_history: list[dict] | None = Field(
        default=None, description="Optional conversation history for query reformulation"
    )


class RAGAnswerSource(BaseModel):
    document_id: str
    chunk_id: str
    title: str
    source: str
    score: float


class RAGAnswerResponse(BaseModel):
    query: str
    answer: str
    sources: list[RAGAnswerSource] = Field(default_factory=list)
    grounded: bool
    no_context: bool = False
    # Internal metadata
    retrieval_confidence: float | None = Field(
        default=None,
        description="Internal: minimum retrieval score from search results",
    )
    answerability_confidence: float | None = Field(
        default=None,
        description="Internal: confidence that the answer addresses the question",
    )
    fallback_category: str | None = Field(
        default=None,
        description="Internal: fallback category if no answer was generated",
    )