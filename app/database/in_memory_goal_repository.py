"""In-memory goal repository for isolated unit testing without PostgreSQL."""

from datetime import datetime, timezone
from typing import Optional

from app.models.goal import FinancialGoal, GoalStatus


class InMemoryGoalRepository:
    """Dict-backed goal repository for unit testing."""

    def __init__(self) -> None:
        self._goals: dict[str, FinancialGoal] = {}

    def create(self, goal: FinancialGoal) -> FinancialGoal:
        now = datetime.now(timezone.utc)
        goal.created_at = now
        goal.updated_at = now
        self._goals[goal.id] = goal
        return goal

    def get_by_id(self, goal_id: str) -> Optional[FinancialGoal]:
        return self._goals.get(goal_id)

    def get_by_member(
        self,
        member_id: str,
        status: Optional[GoalStatus] = None,
    ) -> list[FinancialGoal]:
        results = [g for g in self._goals.values() if g.member_id == member_id]
        if status:
            results = [g for g in results if g.status == status]
        return sorted(results, key=lambda g: g.target_date)

    def get_active_goal(self, member_id: str) -> Optional[FinancialGoal]:
        active = self.get_by_member(member_id, status=GoalStatus.ACTIVE)
        return active[0] if active else None

    def update(self, goal_id: str, **kwargs) -> Optional[FinancialGoal]:
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        for k, v in kwargs.items():
            if hasattr(goal, k) and v is not None:
                setattr(goal, k, v)
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def delete(self, goal_id: str) -> bool:
        if goal_id in self._goals:
            del self._goals[goal_id]
            return True
        return False
