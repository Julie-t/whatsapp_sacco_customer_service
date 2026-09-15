"""Internal and member-facing REST API for financial goals."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.models.goal import GoalStatus
from app.schemas.goal import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    ScenarioAnalysisRequest,
    ScenarioAnalysisResult,
)
from app.services.goals.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])
_goal_service = GoalService()


def get_goal_service() -> GoalService:
    return _goal_service


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalCreate):
    """Create a new financial goal."""
    try:
        return get_goal_service().create_goal(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: str):
    """Get goal by ID including deterministic calculation metrics."""
    goal = get_goal_service().get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.get("/member/{member_id}", response_model=list[GoalResponse])
def get_member_goals(member_id: str, status: Optional[GoalStatus] = None):
    """List all financial goals for a member."""
    return get_goal_service().get_member_goals(member_id, status=status)


@router.post("/{goal_id}/scenario", response_model=ScenarioAnalysisResult)
def calculate_goal_scenario(goal_id: str, request: ScenarioAnalysisRequest):
    """Calculate what-if scenario comparison for a goal."""
    result = get_goal_service().calculate_scenario(goal_id, request.proposed_monthly_contribution)
    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")
    return result


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: str, data: GoalUpdate):
    """Update goal status, target amount, contribution, or dates."""
    updated = get_goal_service().update_goal(goal_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Goal not found")
    return updated
