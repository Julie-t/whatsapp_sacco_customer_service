"""Tests for GoalAlertService (milestone celebrations and deterministic risk alerts)."""

from datetime import date
from unittest.mock import MagicMock
import pytest

from app.models.engagement import NotificationType
from app.models.goal import FinancialGoal, GoalType, GoalStatus
from app.services.proactive.goal_alert_service import GoalAlertService, GoalAlertType


def test_goal_milestone_alert():
    mock_goal_service = MagicMock()
    # Goal at exactly 50%
    goal = FinancialGoal(
        id="goal_100",
        member_id="mem_100",
        goal_type=GoalType.EDUCATION,
        name="School Fees",
        target_amount=100000.0,
        current_amount=50000.0,
        target_date=date(2027, 12, 31),
        contribution_amount=5000.0,
        status=GoalStatus.ACTIVE,
    )
    mock_goal_service.get_member_goals.return_value = [goal]

    service = GoalAlertService(goal_service=mock_goal_service)
    alerts = service.check_goal_alerts("mem_100", as_of=date(2026, 1, 1))

    assert len(alerts) >= 1
    milestone_alert = [a for a in alerts if a.alert_type == GoalAlertType.MILESTONE][0]
    assert milestone_alert.notification_type == NotificationType.GOAL_PROGRESS
    assert "Hongera!" in milestone_alert.message_body
    assert "50%" in milestone_alert.message_body
    assert "KSh 50,000" in milestone_alert.message_body
    assert "*" not in milestone_alert.message_body
    assert "—" not in milestone_alert.message_body


def test_goal_risk_trajectory_alert():
    mock_goal_service = MagicMock()
    # Goal with 6 months left, saving 2,000/mo but needs 10,000/mo
    goal = FinancialGoal(
        id="goal_200",
        member_id="mem_200",
        goal_type=GoalType.EMERGENCY_FUND,
        name="Emergency Reserve",
        target_amount=100000.0,
        current_amount=40000.0,
        target_date=date(2026, 7, 1),
        contribution_amount=2000.0,
        status=GoalStatus.ACTIVE,
    )
    mock_goal_service.get_member_goals.return_value = [goal]

    service = GoalAlertService(goal_service=mock_goal_service)
    alerts = service.check_goal_alerts("mem_200", as_of=date(2026, 1, 1))

    risk_alerts = [a for a in alerts if a.alert_type == GoalAlertType.RISK_TRAJECTORY]
    assert len(risk_alerts) == 1
    alert = risk_alerts[0]
    assert alert.notification_type == NotificationType.GOAL_RISK
    assert "may be challenging" in alert.message_body
    assert "KSh 2,000" in alert.message_body
    assert "KSh 10,000" in alert.message_body
    assert "*" not in alert.message_body
    assert "—" not in alert.message_body
