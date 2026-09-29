"""Personalization Context Builder.

Assembles member profile, knowledge level, active financial goals, deterministic
progress calculations, and prior educational history into a unified structured context.
"""

import logging
from typing import Optional

from app.database.personalization_repository import PersonalizationHistoryRepository
from app.models.goal import GoalStatus
from app.models.personalization import (
    CommunicationStyle,
    KnowledgeLevel,
    PersonalizationContext,
)
from app.services.goals.goal_service import GoalService
from app.services.members.member_service import MemberDataService

logger = logging.getLogger(__name__)


class PersonalizationContextBuilder:
    """Orchestrates gathering of member context for personalized financial education."""

    def __init__(
        self,
        member_service: Optional[MemberDataService] = None,
        goal_service: Optional[GoalService] = None,
        history_repo: Optional[PersonalizationHistoryRepository] = None,
    ) -> None:
        self.member_service = member_service or MemberDataService()
        self.goal_service = goal_service or GoalService()
        self.history_repo = history_repo or PersonalizationHistoryRepository()

    def build_context(
        self,
        member_id_or_phone: str,
        query: str = "",
        retrieved_evidence: Optional[list[str]] = None,
    ) -> PersonalizationContext:
        """Construct structured PersonalizationContext for a member and query."""
        member = None
        if member_id_or_phone.startswith("whatsapp:") or member_id_or_phone.startswith("+"):
            member = self.member_service.resolve_member(member_id_or_phone)
        else:
            member = self.member_service.get_member_profile(member_id_or_phone)

        # Fallback for unregistered or anonymous member
        if not member:
            return PersonalizationContext(
                member_id="",
                display_name="Member",
                preferred_language="en",
                knowledge_level=KnowledgeLevel.BEGINNER,
                communication_style=CommunicationStyle.SIMPLE,
                active_goal=None,
                goal_progress=None,
                recent_topics=[],
                query=query,
                retrieved_evidence=retrieved_evidence or [],
            )

        # Resolve knowledge level
        raw_level = (getattr(member, "knowledge_level", None) or "beginner").lower()
        if "advanced" in raw_level:
            level = KnowledgeLevel.ADVANCED
            style = CommunicationStyle.DETAILED
        elif "intermediate" in raw_level:
            level = KnowledgeLevel.INTERMEDIATE
            style = CommunicationStyle.STANDARD
        else:
            level = KnowledgeLevel.BEGINNER
            style = CommunicationStyle.SIMPLE

        # Fetch active goal and deterministic calculations
        active_goal = None
        goal_progress = None
        try:
            active_goals = self.goal_service.get_member_goals(member.id, status=GoalStatus.ACTIVE)
            if active_goals:
                active_goal = active_goals[0]
                goal_progress = getattr(active_goal, "calculation", None)
                if goal_progress is None and hasattr(self.goal_service, "get_goal_progress"):
                    goal_progress = self.goal_service.get_goal_progress(active_goal.id)
        except Exception as exc:
            logger.warning("Failed to fetch goals for member %s: %s", member.id, exc)

        # Fetch prior delivered topics
        recent_topics: list[str] = []
        try:
            recent_topics = self.history_repo.get_recent_topics(member.id, limit=5)
        except Exception as exc:
            logger.warning("Failed to fetch history for member %s: %s", member.id, exc)

        return PersonalizationContext(
            member_id=member.id,
            display_name=member.display_name,
            preferred_language=member.preferred_language or "en",
            knowledge_level=level,
            communication_style=style,
            active_goal=active_goal,
            goal_progress=goal_progress,
            recent_topics=recent_topics,
            query=query,
            retrieved_evidence=retrieved_evidence or [],
        )
