"""PostgreSQL-backed knowledge-gap repository."""

import json

from psycopg2.extras import Json

from app.database.connection import get_connection
from app.models.knowledge_gap_event import KnowledgeGapEvent
from app.services.knowledge_gap_repository import KnowledgeGapRepository


class PostgresKnowledgeGapRepository(KnowledgeGapRepository):
    """Persist knowledge-gap events in PostgreSQL."""

    async def record(self, event: KnowledgeGapEvent) -> str:
        if event.id is None:
            raise ValueError("Knowledge gap event must have an id before persistence")
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO knowledge_gap_events "
                "(id, conversation_id, sacco_id, query, language, retrieval_score, "
                "fallback_reason, created_at, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (
                    event.id,
                    event.conversation_id,
                    event.sacco_id,
                    event.query,
                    event.language,
                    event.top_retrieval_score,
                    event.fallback_reason,
                    event.timestamp,
                    Json(event.metadata or {}),
                ),
            )
        return event.id

    async def query_gaps_by_sacco(
        self, sacco_id: str, limit: int = 100, offset: int = 0
    ) -> list[KnowledgeGapEvent]:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, conversation_id, sacco_id, query, language, retrieval_score, "
                "fallback_reason, created_at, metadata FROM knowledge_gap_events "
                "WHERE sacco_id = %s ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                (sacco_id, limit, offset),
            )
            rows = cursor.fetchall()
        return [self._event_from_row(row) for row in rows]

    async def count_gaps_by_fallback(self, sacco_id: str) -> dict[str, int]:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT fallback_reason, COUNT(*) FROM knowledge_gap_events "
                "WHERE sacco_id = %s GROUP BY fallback_reason",
                (sacco_id,),
            )
            return {reason: count for reason, count in cursor.fetchall()}

    @staticmethod
    def _event_from_row(row) -> KnowledgeGapEvent:
        metadata = row[8] if isinstance(row[8], dict) else json.loads(row[8] or "{}")
        return KnowledgeGapEvent(
            id=row[0],
            conversation_id=row[1],
            sacco_id=row[2],
            query=row[3],
            language=row[4],
            top_retrieval_score=row[5],
            fallback_reason=row[6],
            timestamp=row[7],
            metadata=metadata,
        )
