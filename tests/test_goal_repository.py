"""Unit tests for GoalRepository / InMemoryGoalRepository."""

from datetime import date

import pytest

from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.models.goal import FinancialGoal, GoalStatus, GoalType, ContributionFrequency


@pytest.fixture
def repo():
    return InMemoryGoalRepository()


def test_create_and_get_goal(repo):
    goal = FinancialGoal(
        id="goal_101",
        member_id="member_001",
        goal_type=GoalType.EDUCATION,
        name="School Fees",
        target_amount=300000.0,
        current_amount=50000.0,
        target_date=date(2028, 1, 1),
        contribution_amount=10000.0,
    )
    saved = repo.create(goal)
    assert saved.id == "goal_101"
    assert saved.created_at is not None

    fetched = repo.get_by_id("goal_101")
    assert fetched is not None
    assert fetched.name == "School Fees"
    assert fetched.target_amount == 300000.0


def test_get_by_member_multiple_goals(repo):
    g1 = FinancialGoal(
        id="g1",
        member_id="member_001",
        goal_type=GoalType.EDUCATION,
        name="School Fees",
        target_amount=200000.0,
        target_date=date(2027, 6, 1),
    )
    g2 = FinancialGoal(
        id="g2",
        member_id="member_001",
        goal_type=GoalType.EMERGENCY_FUND,
        name="Emergency",
        target_amount=100000.0,
        target_date=date(2026, 12, 1),
    )
    g3 = FinancialGoal(
        id="g3",
        member_id="member_002",
        goal_type=GoalType.RETIREMENT,
        name="Retirement",
        target_amount=1000000.0,
        target_date=date(2035, 1, 1),
    )
    repo.create(g1)
    repo.create(g2)
    repo.create(g3)

    m1_goals = repo.get_by_member("member_001")
    assert len(m1_goals) == 2
    # Sorted by target_date ascending: g2 (2026) before g1 (2027)
    assert m1_goals[0].id == "g2"
    assert m1_goals[1].id == "g1"

    # Member isolation
    m2_goals = repo.get_by_member("member_002")
    assert len(m2_goals) == 1
    assert m2_goals[0].id == "g3"


def test_get_active_goal(repo):
    g_active = FinancialGoal(
        id="g_active",
        member_id="member_001",
        goal_type=GoalType.EDUCATION,
        name="Active Goal",
        target_amount=200000.0,
        target_date=date(2027, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    g_completed = FinancialGoal(
        id="g_completed",
        member_id="member_001",
        goal_type=GoalType.GENERAL_SAVINGS,
        name="Old Goal",
        target_amount=50000.0,
        target_date=date(2025, 1, 1),
        status=GoalStatus.COMPLETED,
    )
    repo.create(g_active)
    repo.create(g_completed)

    active = repo.get_active_goal("member_001")
    assert active is not None
    assert active.id == "g_active"


def test_update_goal(repo):
    goal = FinancialGoal(
        id="g_update",
        member_id="member_001",
        goal_type=GoalType.ASSET_PURCHASE,
        name="Land",
        target_amount=500000.0,
        current_amount=50000.0,
        target_date=date(2029, 1, 1),
    )
    repo.create(goal)

    updated = repo.update("g_update", current_amount=100000.0, status=GoalStatus.COMPLETED)
    assert updated is not None
    assert updated.current_amount == 100000.0
    assert updated.status == GoalStatus.COMPLETED


def test_delete_goal(repo):
    goal = FinancialGoal(
        id="g_delete",
        member_id="member_001",
        goal_type=GoalType.CUSTOM,
        name="Trip",
        target_amount=50000.0,
        target_date=date(2027, 1, 1),
    )
    repo.create(goal)
    assert repo.delete("g_delete") is True
    assert repo.get_by_id("g_delete") is None
    assert repo.delete("nonexistent") is False
