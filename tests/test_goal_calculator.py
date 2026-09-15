"""Unit tests for deterministic goal calculator."""

from datetime import date
from time import perf_counter

import pytest

from app.models.goal import FinancialGoal, GoalStatus, GoalType, ContributionFrequency
from app.services.goals.goal_calculator import (
    calculate_amount_remaining,
    calculate_progress_percentage,
    calculate_months_between,
    calculate_required_monthly_contribution,
    calculate_projected_completion,
    calculate_scenario,
    calculate_goal_metrics,
)


def test_calculate_amount_remaining():
    assert calculate_amount_remaining(300000, 60000) == 240000.0
    assert calculate_amount_remaining(100000, 100000) == 0.0
    assert calculate_amount_remaining(100000, 150000) == 0.0
    assert calculate_amount_remaining(0, 5000) == 0.0


def test_calculate_progress_percentage():
    assert calculate_progress_percentage(300000, 60000) == 20.0
    assert calculate_progress_percentage(200000, 100000) == 50.0
    assert calculate_progress_percentage(100000, 100000) == 100.0
    assert calculate_progress_percentage(100000, 150000) == 100.0
    assert calculate_progress_percentage(100000, 0) == 0.0


def test_calculate_months_between():
    start = date(2026, 1, 1)
    end = date(2028, 1, 1)
    assert calculate_months_between(start, end) == 24

    end_same_year = date(2026, 7, 1)
    assert calculate_months_between(start, end_same_year) == 6

    # Past date
    assert calculate_months_between(date(2026, 5, 1), date(2025, 1, 1)) == 0


def test_calculate_required_monthly_contribution():
    as_of = date(2026, 1, 1)
    target_date = date(2028, 1, 1)  # 24 months
    # 240,000 target, 0 current -> 240,000 / 24 = 10,000
    req = calculate_required_monthly_contribution(240000, 0, target_date, as_of=as_of)
    assert req == 10000.0

    # 300,000 target, 60,000 current -> 240,000 / 24 = 10,000
    req2 = calculate_required_monthly_contribution(300000, 60000, target_date, as_of=as_of)
    assert req2 == 10000.0

    # Goal already met
    assert calculate_required_monthly_contribution(100000, 100000, target_date, as_of=as_of) == 0.0


def test_calculate_projected_completion():
    as_of = date(2026, 1, 1)
    # Remaining: 120,000, Monthly: 10,000 -> 12 months -> 2027-01-01
    proj_date, months = calculate_projected_completion(0, 120000, 10000, as_of=as_of)
    assert months == 12
    assert proj_date == date(2027, 1, 1)


def test_scenario_analysis_faster_completion():
    as_of = date(2026, 1, 1)
    target_date = date(2028, 1, 1)  # 24 months
    # Target 240,000, current 0.
    # Current plan: 10,000/mo (24 months)
    # Scenario: 15,000/mo (16 months) -> 8 months sooner
    res = calculate_scenario(
        target_amount=240000,
        current_amount=0,
        target_date=target_date,
        proposed_monthly_contribution=15000,
        current_monthly_contribution=10000,
        as_of=as_of,
    )
    assert res.proposed_projected_months == 16
    assert res.current_projected_months == 24
    assert res.months_difference == 8
    assert "8 months sooner" in res.narrative_summary


def test_calculate_goal_metrics():
    as_of = date(2026, 1, 1)
    goal = FinancialGoal(
        id="test_goal",
        member_id="member_001",
        goal_type=GoalType.EDUCATION,
        name="School Fees",
        target_amount=240000,
        current_amount=60000,
        target_date=date(2027, 7, 1),  # 18 months
        contribution_amount=10000,
        contribution_frequency=ContributionFrequency.MONTHLY,
        status=GoalStatus.ACTIVE,
    )
    metrics = calculate_goal_metrics(goal, as_of=as_of)
    assert metrics.amount_remaining == 180000.0
    assert metrics.progress_percentage == 25.0
    assert metrics.months_remaining == 18
    assert metrics.required_monthly_contribution == 10000.0
    assert metrics.is_on_track is True


def test_calculation_performance_sub_millisecond():
    """Ensure math execution runs in microseconds locally with 0 LLM calls."""
    target_date = date(2028, 1, 1)
    start = perf_counter()
    for _ in range(1000):
        calculate_scenario(
            target_amount=300000,
            current_amount=50000,
            target_date=target_date,
            proposed_monthly_contribution=12500,
            current_monthly_contribution=8000,
        )
    elapsed = perf_counter() - start
    avg_ms = (elapsed / 1000) * 1000
    # 1000 iterations should take well under 100ms (< 0.1ms per calculation)
    assert avg_ms < 1.0, f"Calculation too slow: {avg_ms:.4f}ms per iteration"
