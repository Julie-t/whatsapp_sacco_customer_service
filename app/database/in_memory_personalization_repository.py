"""In-memory repository for member education history (unit testing)."""

from datetime import datetime, timezone
from typing import Optional

from app.models.personalization import EducationHistoryRecord


class InMemoryPersonalizationHistoryRepository:
    """Fast, in-memory repository for personalization history tests."""

    def __init__(self) -> None:
        self._history: list[EducationHistoryRecord] = []
        self._next_id: int = 1

    def record_topic(
        self,
        member_id: str,
        topic: str,
        summary: Optional[str] = None,
        goal_id: Optional[str] = None,
    ) -> EducationHistoryRecord:
        record = EducationHistoryRecord(
            id=self._next_id,
            member_id=member_id,
            topic=topic,
            summary=summary,
            goal_id=goal_id,
            created_at=datetime.now(timezone.utc),
        )
        self._next_id += 1
        self._history.append(record)
        return record

    def get_recent_topics(self, member_id: str, limit: int = 5) -> list[str]:
        matching = [r for r in reversed(self._history) if r.member_id == member_id]
        seen: set[str] = set()
        unique_topics: list[str] = []
        for r in matching[:limit]:
            if r.topic not in seen:
                seen.add(r.topic)
                unique_topics.append(r.topic)
        return unique_topics

    def get_history(self, member_id: str, limit: int = 20) -> list[EducationHistoryRecord]:
        matching = [r for r in reversed(self._history) if r.member_id == member_id]
        return matching[:limit]

    def clear(self) -> None:
        self._history.clear()
        self._next_id = 1
