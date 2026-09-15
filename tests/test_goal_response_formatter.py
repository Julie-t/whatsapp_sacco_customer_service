"""Unit tests for goal response formatter."""

from datetime import date

import pytest

from app.models.goal import FinancialGoal, GoalStatus, GoalType, ContributionFrequency
from app.schemas.goal import GoalResponse, ScenarioAnalysisResult
from app.services.goals.goal_calculator import calculate_goal_metrics
from app.services.goals.goal_response_formatter import (
    format_clarification_prompt,
    format_goal_created,
    format_goal_progress,
    format_goal_scenario,
    format_no_goals_message,
)


@pytest.fixture
def sample_goal_response():
    goal = FinancialGoal(
        id="goal_1",
        member_id="m1",
        goal_type=GoalType.EDUCATION,
        name="School Fees",
        target_amount=240000.0,
        current_amount=40000.0,
        target_date=date(2028, 1, 1),
        contribution_amount=10000.0,
        status=GoalStatus.ACTIVE,
    )
    calc = calculate_goal_metrics(goal, as_of=date(2026, 1, 1))
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
        notes=None,
        calculation=calc,
    )


def test_format_goal_created_hygiene(sample_goal_response):
    text = format_goal_created(sample_goal_response, demo_label=True)
    assert "*" not in text
    assert "—" not in text
    assert "KSh 240,000" in text
    assert "KSh 40,000" in text
    assert "KSh 8,333.33/month" in text or "KSh" in text
    assert "(demo data)" in text


def test_format_goal_created_no_demo(sample_goal_response):
    text = format_goal_created(sample_goal_response, demo_label=False)
    assert "(demo data)" not in text


def test_format_goal_progress(sample_goal_response):
    text = format_goal_progress(sample_goal_response)
    assert "*" not in text
    assert "Progress for School Fees:" in text
    assert "Progress: 17% of your target" in text


def test_format_goal_scenario():
    scenario = ScenarioAnalysisResult(
        current_monthly_contribution=10000.0,
        proposed_monthly_contribution=15000.0,
        amount_remaining=200000.0,
        current_projected_months=20,
        proposed_projected_months=14,
        current_projected_date=date(2027, 9, 1),
        proposed_projected_date=date(2027, 3, 1),
        months_difference=6,
        narrative_summary="Saving KSh 15,000/month would reach your goal in 14 months—6 months sooner than your current plan.",
    )
    text = format_goal_scenario(scenario)
    assert "*" not in text
    assert "—" not in text
    assert "KSh 15,000/month" in text
    assert "14 months" in text


def test_format_clarification_prompt():
    assert "How much would you like to save" in format_clarification_prompt(["target_amount"])
    assert "By when would you like to reach" in format_clarification_prompt(["target_date"])
    assert "how much" in format_clarification_prompt(["target_amount", "target_date"]).lower()


def test_format_no_goals_message():
    text = format_no_goals_message("Edna Maina")
    assert "Hello Edna Maina!" in text
    assert "do not have an active financial goal" in text
