"""PostgreSQL repository for member education history."""

import logging
from typing import Optional

from app.database.connection import get_connection
from app.models.personalization import EducationHistoryRecord

logger = logging.getLogger(__name__)


class PersonalizationHistoryRepository:
    """PostgreSQL storage and retrieval for member educational interactions."""

    def record_topic(
        self,
        member_id: str,
        topic: str,
        summary: Optional[str] = None,
        goal_id: Optional[str] = None,
    ) -> EducationHistoryRecord:
        """Record a delivered educational topic for a member."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO member_education_history (member_id, topic, summary, goal_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id, member_id, topic, summary, goal_id, created_at
                """,
                (member_id, topic, summary, goal_id),
            )
            row = cur.fetchone()
            return EducationHistoryRecord(
                id=row[0],
                member_id=row[1],
                topic=row[2],
                summary=row[3],
                goal_id=row[4],
                created_at=row[5],
            )

    def get_recent_topics(self, member_id: str, limit: int = 5) -> list[str]:
        """Fetch distinct topic names delivered to the member recently."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT topic
                FROM (
                    SELECT topic, created_at
                    FROM member_education_history
                    WHERE member_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                ) sub
                """,
                (member_id, limit),
            )
            return [row[0] for row in cur.fetchall()]

    def get_history(self, member_id: str, limit: int = 20) -> list[EducationHistoryRecord]:
        """Fetch full chronological history of topics delivered to a member."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, member_id, topic, summary, goal_id, created_at
                FROM member_education_history
                WHERE member_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (member_id, limit),
            )
            return [
                EducationHistoryRecord(
                    id=row[0],
                    member_id=row[1],
                    topic=row[2],
                    summary=row[3],
                    goal_id=row[4],
                    created_at=row[5],
                )
                for row in cur.fetchall()
            ]
