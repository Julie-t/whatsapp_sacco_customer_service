"""Database model for knowledge gap events.

Records when members ask questions that the knowledge base cannot adequately answer.
This B2B capability allows SACCOs to identify and address knowledge gaps.

Schema:
  id: Event ID
  timestamp: When the gap was detected
  query: The member's question (sanitized)
  language: Language of the query
  sacco_id: Which SACCO this gap occurred in
  top_retrieval_score: Best matching document score
  fallback_reason: Why the query couldn't be answered
  conversation_id: Optional conversation context
"""

from datetime import datetime, UTC
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeGapEvent(BaseModel):
    """A knowledge gap event recorded from RAG pipeline."""

    id: str | None = Field(default=None, description="Event ID (auto-generated if None)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    query: str = Field(description="The query that couldn't be answered")
    language: str = Field(default="en")
    sacco_id: str = Field(description="Which SACCO this gap occurred in")
    top_retrieval_score: float | None = Field(
        default=None, description="Best retrieval score for this query"
    )
    fallback_reason: str = Field(description="Internal fallback category that was triggered")
    conversation_id: str | None = Field(
        default=None, description="Associated conversation ID if available"
    )
    member_id: str | None = Field(
        default=None, description="Optional member ID (should be hashed/anon if stored)"
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Optional internal metadata for auditing and repository ordering.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "gap_20240528_001",
                "timestamp": "2024-05-28T10:30:00Z",
                "query": "Can I increase my monthly contribution?",
                "language": "en",
                "sacco_id": "demo_sacco",
                "top_retrieval_score": 0.35,
                "fallback_reason": "knowledge_gap",
                "conversation_id": "conv_12345",
                "member_id": None,
            }
        }
    )
