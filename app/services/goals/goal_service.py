"""Goal service layer coordinating repositories, deterministic math, and safety boundaries."""

import logging
import uuid
from datetime import date
from typing import Optional

from app.database.goal_repository import GoalRepository
from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.models.goal import FinancialGoal, GoalStatus, GoalType, ContributionFrequency
from app.schemas.goal import (
    GoalCalculationResult,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    ScenarioAnalysisResult,
)
from app.services.goals.goal_calculator import (
    calculate_goal_metrics,
    calculate_scenario,
)

logger = logging.getLogger(__name__)


class GoalService:
    """Business logic for member financial goals."""

    def __init__(self, repository: Optional[GoalRepository | InMemoryGoalRepository] = None):
        self._repo = repository or GoalRepository()

    def create_goal(self, data: GoalCreate) -> GoalResponse:
        """Create a new financial goal with validation."""
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        goal = FinancialGoal(
            id=goal_id,
            member_id=data.member_id,
            goal_type=data.goal_type,
            name=data.name,
            target_amount=data.target_amount,
            current_amount=data.current_amount,
            target_date=data.target_date,
            contribution_amount=data.contribution_amount,
            contribution_frequency=data.contribution_frequency,
            status=GoalStatus.ACTIVE,
            notification_frequency=data.notification_frequency,
            notes=data.notes,
            is_demo=True,
        )
        saved = self._repo.create(goal)
        return self._to_response(saved)

    def get_goal(self, goal_id: str) -> Optional[GoalResponse]:
        """Fetch goal by ID with attached deterministic calculations."""
        goal = self._repo.get_by_id(goal_id)
        if not goal:
            return None
        return self._to_response(goal)

    def get_goal_progress(self, goal_id: str) -> Optional[GoalCalculationResult]:
        """Return the calculation progress metrics for a goal."""
        goal_resp = self.get_goal(goal_id)
        return goal_resp.calculation if goal_resp else None

    def get_member_goals(
        self,
        member_id: str,
        status: Optional[GoalStatus] = None,
    ) -> list[GoalResponse]:
        """List all goals for a member."""
        goals = self._repo.get_by_member(member_id, status=status)
        return [self._to_response(g) for g in goals]

    def get_active_goal(self, member_id: str) -> Optional[GoalResponse]:
        """Fetch the most urgent active goal for a member."""
        goal = self._repo.get_active_goal(member_id)
        if not goal:
            return None
        return self._to_response(goal)

    def update_goal(self, goal_id: str, data: GoalUpdate) -> Optional[GoalResponse]:
        """Update fields of an existing goal."""
        kwargs = data.model_dump(exclude_unset=True)
        updated = self._repo.update(goal_id, **kwargs)
        if not updated:
            return None
        return self._to_response(updated)

    def update_goal_current_amount(self, goal_id: str, current_amount: float) -> Optional[GoalResponse]:
        """Update current savings / starting balance for an existing goal."""
        return self.update_goal(goal_id, GoalUpdate(current_amount=current_amount))

    def calculate_scenario(
        self,
        goal_id: str,
        proposed_monthly_contribution: float,
    ) -> Optional[ScenarioAnalysisResult]:
        """Run what-if analysis against an existing goal."""
        goal = self._repo.get_by_id(goal_id)
        if not goal:
            return None
        return calculate_scenario(
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            proposed_monthly_contribution=proposed_monthly_contribution,
            current_monthly_contribution=goal.contribution_amount,
        )

    def _to_response(self, goal: FinancialGoal) -> GoalResponse:
        calc = calculate_goal_metrics(goal)
        return GoalResponse(
            id=goal.id,
            member_id=goal.member_id,
            goal_type=goal.goal_type,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            contribution_amount=goal.contribution_amount,
            contribution_frequency=goal.contribution_frequency,
            status=goal.status,
            notification_frequency=goal.notification_frequency,
            notes=goal.notes,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            calculation=calc,
        )
