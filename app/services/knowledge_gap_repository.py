"""Repository for knowledge gap events.

Provides a data access layer for recording and querying knowledge gaps.
Supports both in-memory and database backends.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

from app.models.knowledge_gap_event import KnowledgeGapEvent

logger = logging.getLogger(__name__)


class KnowledgeGapRepository:
    """Abstract base for knowledge gap persistence."""

    async def record(self, event: KnowledgeGapEvent) -> str:
        """Record a knowledge gap event.

        Args:
            event: The knowledge gap event to record.

        Returns:
            The recorded event ID.
        """
        raise NotImplementedError

    async def query_gaps_by_sacco(
        self,
        sacco_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeGapEvent]:
        """Query knowledge gaps for a specific SACCO.

        Args:
            sacco_id: The SACCO to query.
            limit: Maximum results to return.
            offset: Results to skip.

        Returns:
            List of knowledge gap events.
        """
        raise NotImplementedError

    async def count_gaps_by_fallback(
        self, sacco_id: str
    ) -> dict[str, int]:
        """Count knowledge gaps by fallback reason.

        Args:
            sacco_id: The SACCO to query.

        Returns:
            Dictionary mapping fallback reason to count.
        """
        raise NotImplementedError


class InMemoryKnowledgeGapRepository(KnowledgeGapRepository):
    """In-memory implementation for testing and development."""

    def __init__(self):
        """Initialize with empty event list."""
        self.events: list[KnowledgeGapEvent] = []
        self._counter = 0  # Counter for stable timestamp ordering

    async def record(self, event: KnowledgeGapEvent) -> str:
        """Record a knowledge gap event in memory.

        Args:
            event: The knowledge gap event to record.

        Returns:
            The recorded event ID.
        """
        if event.id is None:
            event.id = f"gap_{int(datetime.now(UTC).timestamp())}_{uuid.uuid4().hex[:8]}"

        event.metadata = dict(event.metadata or {})
        event.metadata["_record_counter"] = self._counter
        self._counter += 1

        self.events.append(event)
        logger.debug("Recorded knowledge gap: %s | query=%r", event.id, event.query[:50])
        return event.id

    async def query_gaps_by_sacco(
        self,
        sacco_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeGapEvent]:
        """Query knowledge gaps for a specific SACCO.

        Args:
            sacco_id: The SACCO to query.
            limit: Maximum results to return.
            offset: Results to skip.

        Returns:
            List of knowledge gap events, sorted by timestamp descending (latest first).
        """
        filtered = [e for e in self.events if e.sacco_id == sacco_id]
        filtered.sort(
            key=lambda e: (
                int(e.metadata.get("_record_counter", 0)) if e.metadata else 0,
                e.timestamp,
            ),
            reverse=True,
        )
        return filtered[offset : offset + limit]

    async def count_gaps_by_fallback(
        self, sacco_id: str
    ) -> dict[str, int]:
        """Count knowledge gaps by fallback reason.

        Args:
            sacco_id: The SACCO to query.

        Returns:
            Dictionary mapping fallback reason to count.
        """
        counts: dict[str, int] = {}
        for event in self.events:
            if event.sacco_id == sacco_id:
                reason = event.fallback_reason
                counts[reason] = counts.get(reason, 0) + 1
        return counts


# Global in-memory repository instance for now
# Later, this can be swapped for a database-backed implementation
_knowledge_gap_repo: Optional[KnowledgeGapRepository] = None


def get_knowledge_gap_repository() -> KnowledgeGapRepository:
    """Get the global knowledge gap repository instance.

    Returns:
        The repository singleton.
    """
    global _knowledge_gap_repo
    if _knowledge_gap_repo is None:
        from app.config.settings import settings

        if settings.app_env.lower() in {"test", "testing"}:
            _knowledge_gap_repo = InMemoryKnowledgeGapRepository()
        else:
            from app.services.postgres_knowledge_gap_repository import (
                PostgresKnowledgeGapRepository,
            )

            _knowledge_gap_repo = PostgresKnowledgeGapRepository()
    return _knowledge_gap_repo


def set_knowledge_gap_repository(repo: KnowledgeGapRepository) -> None:
    """Set the global knowledge gap repository instance.

    Useful for testing with different implementations.

    Args:
        repo: The repository implementation to use.
    """
    global _knowledge_gap_repo
    _knowledge_gap_repo = repo
