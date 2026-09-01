"""Service for recording knowledge gap events.

Encapsulates the logic for determining when a knowledge gap should be recorded
and interacts with the repository layer.
"""

import logging
from datetime import UTC, datetime
import uuid

from app.core.fallback import FallbackCategory
from app.core.metrics import record_knowledge_gap
from app.models.knowledge_gap_event import KnowledgeGapEvent
from app.services.knowledge_gap_repository import (
    get_knowledge_gap_repository,
    KnowledgeGapRepository,
)

logger = logging.getLogger(__name__)


class KnowledgeGapService:
    """Service for tracking and recording knowledge gaps."""

    def __init__(self, repository: KnowledgeGapRepository | None = None):
        """Initialize with optional custom repository.

        Args:
            repository: Optional repository implementation. Uses default if None.
        """
        self.repository = repository or get_knowledge_gap_repository()

    async def record_gap(
        self,
        query: str,
        sacco_id: str,
        language: str = "en",
        top_retrieval_score: float | None = None,
        fallback_reason: str = "knowledge_gap",
        conversation_id: str | None = None,
        member_id: str | None = None,
    ) -> str:
        """Record a knowledge gap event.

        This is called when the RAG system cannot answer a member's question
        due to insufficient knowledge base coverage.

        Args:
            query: The member's question (will be stored as-is for analysis).
            sacco_id: Which SACCO this gap is for.
            language: Language of the query (default: "en").
            top_retrieval_score: Best retrieval score if results were found (optional).
            fallback_reason: Why the query couldn't be answered.
            conversation_id: Optional conversation ID for context.
            member_id: Optional member ID (should be hashed/anonymized if stored).

        Returns:
            The recorded event ID.
        """
        # Generate event ID
        event_id = f"gap_{int(datetime.now(UTC).timestamp())}_{uuid.uuid4().hex[:8]}"

        # Create event
        event = KnowledgeGapEvent(
            id=event_id,
            timestamp=datetime.now(UTC),
            query=query,
            language=language,
            sacco_id=sacco_id,
            top_retrieval_score=top_retrieval_score,
            fallback_reason=fallback_reason,
            conversation_id=conversation_id,
            member_id=member_id,
        )

        # Record
        recorded_id = await self.repository.record(event)
        logger.info(
            "Knowledge gap recorded | id=%s sacco=%s fallback=%s query=%r",
            recorded_id,
            sacco_id,
            fallback_reason,
            query[:80],
        )
        record_knowledge_gap(sacco_id, language)

        return recorded_id

    async def get_gaps_by_sacco(
        self,
        sacco_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeGapEvent]:
        """Get knowledge gap events for a SACCO.

        Args:
            sacco_id: Which SACCO to query.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            List of knowledge gap events.
        """
        return await self.repository.query_gaps_by_sacco(sacco_id, limit, offset)

    async def get_gap_summary(
        self, sacco_id: str
    ) -> dict[str, list[tuple[str, int]]]:
        """Get a summary of knowledge gaps grouped by fallback reason.

        Args:
            sacco_id: Which SACCO to query.

        Returns:
            Dictionary with fallback reason as key, list of (query, count) as value.
        """
        counts = await self.repository.count_gaps_by_fallback(sacco_id)
        # Sort by count descending
        summary = {
            reason: count for reason, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        }
        return summary
