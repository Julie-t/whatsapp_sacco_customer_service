"""Unit tests for GoalService."""

from datetime import date, timedelta
import pytest

from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.models.goal import GoalStatus, GoalType, ContributionFrequency
from app.schemas.goal import GoalCreate, GoalUpdate
from app.services.goals.goal_service import GoalService


@pytest.fixture
def service():
    repo = InMemoryGoalRepository()
    return GoalService(repository=repo)


def test_create_and_get_goal(service):
    target_date = date.today() + timedelta(days=365)
    create_data = GoalCreate(
        member_id="member_001",
        goal_type=GoalType.EDUCATION,
        name="School Fees",
        target_amount=120000.0,
        current_amount=20000.0,
        target_date=target_date,
        contribution_amount=8500.0,
    )
    res = service.create_goal(create_data)
    assert res.id.startswith("goal_")
    assert res.name == "School Fees"
    assert res.calculation is not None
    assert res.calculation.amount_remaining == 100000.0

    fetched = service.get_goal(res.id)
    assert fetched is not None
    assert fetched.id == res.id


def test_get_member_goals_and_active(service):
    d1 = date.today() + timedelta(days=200)
    d2 = date.today() + timedelta(days=500)

    service.create_goal(
        GoalCreate(
            member_id="member_001",
            goal_type=GoalType.EMERGENCY_FUND,
            name="Emergency Fund",
            target_amount=50000.0,
            target_date=d1,
        )
    )
    service.create_goal(
        GoalCreate(
            member_id="member_001",
            goal_type=GoalType.EDUCATION,
            name="College",
            target_amount=200000.0,
            target_date=d2,
        )
    )

    goals = service.get_member_goals("member_001")
    assert len(goals) == 2

    active = service.get_active_goal("member_001")
    assert active is not None
    assert active.name == "Emergency Fund"  # Earlier target date


def test_update_goal_status(service):
    d = date.today() + timedelta(days=300)
    res = service.create_goal(
        GoalCreate(
            member_id="member_001",
            goal_type=GoalType.GENERAL_SAVINGS,
            name="Vacation",
            target_amount=30000.0,
            target_date=d,
        )
    )
    updated = service.update_goal(res.id, GoalUpdate(status=GoalStatus.COMPLETED, current_amount=30000.0))
    assert updated.status == GoalStatus.COMPLETED
    assert updated.current_amount == 30000.0
    assert updated.calculation.progress_percentage == 100.0


def test_calculate_scenario_service(service):
    d = date.today() + timedelta(days=730)  # ~24 months
    res = service.create_goal(
        GoalCreate(
            member_id="member_001",
            goal_type=GoalType.EDUCATION,
            name="Uni",
            target_amount=240000.0,
            current_amount=0.0,
            target_date=d,
            contribution_amount=10000.0,
        )
    )
    scenario = service.calculate_scenario(res.id, proposed_monthly_contribution=15000.0)
    assert scenario is not None
    assert scenario.proposed_projected_months == 16
    assert scenario.months_difference > 0
    assert "sooner" in scenario.narrative_summary
