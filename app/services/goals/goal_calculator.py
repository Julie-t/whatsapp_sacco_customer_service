"""Deterministic mathematical calculation engine for financial goals.

Guiding principles:
- 100% reproducible, zero LLM reliance for arithmetic.
- Explicit math without hidden interest/investment assumptions.
- Rounded cleanly for currency presentation.
"""

import math
from datetime import date, timedelta
from typing import Optional

from app.models.goal import FinancialGoal
from app.schemas.goal import GoalCalculationResult, ScenarioAnalysisResult


def calculate_amount_remaining(target_amount: float, current_amount: float) -> float:
    """Calculate remaining amount to reach target."""
    if target_amount <= 0:
        return 0.0
    return max(0.0, round(target_amount - current_amount, 2))


def calculate_progress_percentage(target_amount: float, current_amount: float) -> float:
    """Calculate progress percentage toward target (0.0 to 100.0)."""
    if target_amount <= 0:
        return 0.0
    if current_amount <= 0:
        return 0.0
    percentage = (current_amount / target_amount) * 100.0
    return min(100.0, round(percentage, 1))


def calculate_months_between(start_date: date, end_date: date) -> int:
    """Calculate the number of months between two dates."""
    if end_date <= start_date:
        return 0
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    # If the end day of month is earlier than start day, adjust if needed, but at least 1 month if in future
    if end_date.day < start_date.day and months > 0:
        # Check if difference is less than 30 days
        if (end_date - start_date).days < 28:
            return 1
    return max(1, months)


def calculate_required_monthly_contribution(
    target_amount: float,
    current_amount: float,
    target_date: date,
    as_of: Optional[date] = None,
) -> float:
    """Calculate required monthly contribution to hit target by target_date."""
    ref_date = as_of or date.today()
    remaining = calculate_amount_remaining(target_amount, current_amount)
    if remaining <= 0:
        return 0.0
    months = calculate_months_between(ref_date, target_date)
    if months <= 0:
        return remaining
    return round(remaining / months, 2)


def add_months(source_date: date, months: int) -> date:
    """Add integer months to a date."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, [31,
        29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def calculate_projected_completion(
    current_amount: float,
    target_amount: float,
    monthly_contribution: float,
    as_of: Optional[date] = None,
) -> tuple[Optional[date], int]:
    """Calculate projected completion date given a monthly savings contribution.
    
    Returns (projected_date, months_needed).
    """
    ref_date = as_of or date.today()
    remaining = calculate_amount_remaining(target_amount, current_amount)
    if remaining <= 0:
        return (ref_date, 0)
    if monthly_contribution <= 0:
        return (None, 0)
    
    months_needed = math.ceil(remaining / monthly_contribution)
    projected_date = add_months(ref_date, months_needed)
    return (projected_date, months_needed)


def calculate_scenario(
    target_amount: float,
    current_amount: float,
    target_date: date,
    proposed_monthly_contribution: float,
    current_monthly_contribution: Optional[float] = None,
    as_of: Optional[date] = None,
) -> ScenarioAnalysisResult:
    """Compare a proposed 'what-if' contribution against current plan."""
    ref_date = as_of or date.today()
    remaining = calculate_amount_remaining(target_amount, current_amount)
    
    # Proposed scenario
    proposed_date, proposed_months = calculate_projected_completion(
        current_amount, target_amount, proposed_monthly_contribution, as_of=ref_date
    )
    
    # Current plan (or required if not set)
    if current_monthly_contribution and current_monthly_contribution > 0:
        current_date, current_months = calculate_projected_completion(
            current_amount, target_amount, current_monthly_contribution, as_of=ref_date
        )
    else:
        req = calculate_required_monthly_contribution(target_amount, current_amount, target_date, as_of=ref_date)
        current_monthly_contribution = req
        current_date, current_months = calculate_projected_completion(
            current_amount, target_amount, req, as_of=ref_date
        )

    months_diff = (current_months or 0) - proposed_months
    
    if months_diff > 0:
        narrative = f"Saving KSh {proposed_monthly_contribution:,.0f}/month would reach your goal in {proposed_months} months—{months_diff} months sooner than your current plan."
    elif months_diff < 0:
        narrative = f"Saving KSh {proposed_monthly_contribution:,.0f}/month would reach your goal in {proposed_months} months—{-months_diff} months later than your current plan."
    else:
        narrative = f"Saving KSh {proposed_monthly_contribution:,.0f}/month matches your current timeline of {proposed_months} months."

    return ScenarioAnalysisResult(
        current_monthly_contribution=current_monthly_contribution,
        proposed_monthly_contribution=proposed_monthly_contribution,
        amount_remaining=remaining,
        current_projected_months=current_months,
        proposed_projected_months=proposed_months,
        current_projected_date=current_date,
        proposed_projected_date=proposed_date or target_date,
        months_difference=months_diff,
        narrative_summary=narrative,
    )


def calculate_goal_metrics(goal: FinancialGoal, as_of: Optional[date] = None) -> GoalCalculationResult:
    """Generate complete deterministic breakdown for a goal."""
    ref_date = as_of or date.today()
    remaining = calculate_amount_remaining(goal.target_amount, goal.current_amount)
    progress = calculate_progress_percentage(goal.target_amount, goal.current_amount)
    months_left = calculate_months_between(ref_date, goal.target_date)
    req_monthly = calculate_required_monthly_contribution(
        goal.target_amount, goal.current_amount, goal.target_date, as_of=ref_date
    )
    
    proj_date = None
    is_on_track = True
    pace = "On track"
    
    if goal.contribution_amount and goal.contribution_amount > 0:
        proj_date, needed_months = calculate_projected_completion(
            goal.current_amount, goal.target_amount, goal.contribution_amount, as_of=ref_date
        )
        if needed_months > months_left:
            is_on_track = False
            pace = f"Pacing behind by {needed_months - months_left} months"
        elif needed_months < months_left:
            pace = f"Ahead of schedule by {months_left - needed_months} months"
    else:
        # Default projection matches target date if required contribution is made
        proj_date = goal.target_date

    return GoalCalculationResult(
        target_amount=goal.target_amount,
        current_amount=goal.current_amount,
        amount_remaining=remaining,
        progress_percentage=progress,
        months_remaining=months_left,
        required_monthly_contribution=req_monthly,
        projected_completion_date=proj_date,
        is_on_track=is_on_track,
        pace_assessment=pace,
    )
