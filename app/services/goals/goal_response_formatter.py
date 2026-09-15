"""Format financial goal responses into WhatsApp-friendly text.

Design rules:
- No asterisks, no markdown bold/italic markers
- No em dashes (replace with normal hyphens)
- Use KSh formatting with comma separators (e.g. KSh 300,000)
- Encouraging, respectful, coach-like tone
- Optional '(demo data)' tag
"""

from app.schemas.goal import GoalResponse, ScenarioAnalysisResult


def _ksh(amount: float) -> str:
    """Format monetary amount as 'KSh 32,450'."""
    if amount == int(amount):
        return f"KSh {int(amount):,}"
    return f"KSh {amount:,.2f}"


def format_goal_created(goal: GoalResponse, *, demo_label: bool = True) -> str:
    """Format confirmation of a newly created financial goal."""
    lines = [
        f"Goal set: {goal.name}!",
        "",
        f"Target amount: {_ksh(goal.target_amount)}",
        f"Target date: {goal.target_date.strftime('%B %Y')}",
    ]
    if goal.calculation:
        calc = goal.calculation
        lines.append(f"Starting savings: {_ksh(goal.current_amount)}")
        lines.append(f"Amount remaining: {_ksh(calc.amount_remaining)}")
        lines.append(f"Required monthly contribution: {_ksh(calc.required_monthly_contribution)}/month")
        lines.append(f"Timeline: {calc.months_remaining} months")

    lines.append("")
    lines.append("I will help you track this goal as you save.")
    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)


def format_goal_progress(goal: GoalResponse, *, demo_label: bool = True) -> str:
    """Format current progress on an active goal."""
    lines = [
        f"Progress for {goal.name}:",
        "",
        f"Target: {_ksh(goal.target_amount)} by {goal.target_date.strftime('%B %Y')}",
        f"Current saved: {_ksh(goal.current_amount)}",
    ]
    if goal.calculation:
        calc = goal.calculation
        lines.append(f"Amount remaining: {_ksh(calc.amount_remaining)}")
        lines.append(f"Progress: {calc.progress_percentage:.0f}% of your target")
        lines.append(f"Required contribution: {_ksh(calc.required_monthly_contribution)}/month ({calc.months_remaining} months left)")
        if calc.pace_assessment:
            lines.append(f"Status: {calc.pace_assessment}")

    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)


def format_goal_updated(goal: GoalResponse, *, demo_label: bool = True) -> str:
    """Format confirmation when a member updates their current savings or goal progress."""
    lines = [
        f"Updated: {goal.name}!",
        "",
        f"Target amount: {_ksh(goal.target_amount)}",
        f"Target date: {goal.target_date.strftime('%B %Y')}",
        f"Current saved: {_ksh(goal.current_amount)}",
    ]
    if goal.calculation:
        calc = goal.calculation
        lines.append(f"Amount remaining: {_ksh(calc.amount_remaining)}")
        lines.append(f"Progress: {calc.progress_percentage:.0f}% of your target")
        lines.append(f"Required monthly contribution: {_ksh(calc.required_monthly_contribution)}/month")
        lines.append(f"Timeline: {calc.months_remaining} months")

    lines.append("")
    lines.append("I have updated your savings plan accordingly.")
    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)


def format_goal_scenario(scenario: ScenarioAnalysisResult, *, demo_label: bool = True) -> str:
    """Format what-if scenario comparison."""
    lines = [
        "Here is what that would look like:",
        "",
        f"Proposed monthly savings: {_ksh(scenario.proposed_monthly_contribution)}/month",
        f"Projected completion: {scenario.proposed_projected_months} months ({scenario.proposed_projected_date.strftime('%B %Y')})",
        "",
        scenario.narrative_summary.replace("—", " - "),
    ]
    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)


def format_clarification_prompt(missing_fields: list[str]) -> str:
    """Return a single, concise question asking for missing goal information."""
    if "target_amount" in missing_fields and "target_date" in missing_fields:
        return "That sounds like a great goal! How much would you like to save, and by when would you like to reach it?"
    if "target_amount" in missing_fields:
        return "How much would you like to save toward this goal?"
    if "target_date" in missing_fields or "timeline_months" in missing_fields:
        return "By when would you like to reach this goal (for example: in 2 years, or 18 months)?"
    return "Could you share a bit more detail about your target amount and timeline so I can calculate your savings plan?"


def format_no_goals_message(member_name: str, *, demo_label: bool = True) -> str:
    """Prompt when a member asks about goals but has none recorded yet."""
    lines = [
        f"Hello {member_name}!",
        "",
        "You do not have an active financial goal set up yet.",
        "You can create one anytime by telling me what you want to save for. For example:",
        "\"I want to save KSh 200,000 for school fees in 2 years.\"",
    ]
    if demo_label:
        lines.append("")
        lines.append("(demo data)")
    return "\n".join(lines)
