"""Goal Progress & Risk Alert Service for System 10.

Evaluates member financial goals deterministically, identifying milestone celebrations
and trajectory risks without directive financial advice.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from app.models.engagement import NotificationType
from app.models.goal import FinancialGoal, GoalStatus
from app.services.goals.goal_calculator import calculate_goal_metrics
from app.services.goals.goal_service import GoalService


class GoalAlertType(str, Enum):
    MILESTONE = "milestone"
    RISK_TRAJECTORY = "risk_trajectory"


@dataclass
class GoalAlert:
    """A proactive alert regarding a member's financial goal progress."""
    member_id: str
    goal_id: str
    goal_name: str
    alert_type: GoalAlertType
    notification_type: NotificationType
    message_body: str
    progress_percentage: float
    is_triggered: bool = True
    metadata: Optional[dict] = None


class GoalAlertService:
    """Identifies and constructs goal alerts using deterministic calculations."""

    MILESTONES = (100.0, 75.0, 50.0, 25.0)

    def __init__(self, goal_service: Optional[GoalService] = None) -> None:
        self.goal_service = goal_service or GoalService()

    def check_goal_alerts(
        self, member_id: str, as_of: Optional[date] = None
    ) -> list[GoalAlert]:
        """Inspect all active goals for a member and return any triggered alerts."""
        alerts: list[GoalAlert] = []
        goals = self.goal_service.get_member_goals(member_id)

        for goal in goals:
            if goal.status != GoalStatus.ACTIVE:
                continue

            metrics = calculate_goal_metrics(goal, as_of=as_of)

            # 1. Milestone Check
            # Check highest reached milestone
            for milestone in self.MILESTONES:
                if metrics.progress_percentage >= milestone:
                    alerts.append(self._create_milestone_alert(goal, metrics, milestone))
                    break  # Alert on the highest relevant milestone

            # 2. Risk Trajectory Check
            if not metrics.is_on_track and metrics.months_remaining <= 12:
                alerts.append(self._create_risk_alert(goal, metrics))

        return alerts

    def _create_milestone_alert(
        self, goal: FinancialGoal, metrics, milestone: float
    ) -> GoalAlert:
        """Construct deterministic milestone celebration message."""
        milestone_pct = int(milestone)
        if milestone_pct == 100:
            msg = (
                f"Hongera! You have reached 100% of your {goal.name} goal! "
                f"You saved KSh {goal.current_amount:,.0f} of your KSh {goal.target_amount:,.0f} target. "
                "Well done on achieving your savings target! (demo data)"
            )
        else:
            msg = (
                f"Hongera! You have reached {milestone_pct}% of your {goal.name} goal. "
                f"You have saved KSh {goal.current_amount:,.0f} of KSh {goal.target_amount:,.0f}, "
                f"with KSh {metrics.amount_remaining:,.0f} remaining. (demo data)"
            )

        return GoalAlert(
            member_id=goal.member_id,
            goal_id=goal.id,
            goal_name=goal.name,
            alert_type=GoalAlertType.MILESTONE,
            notification_type=NotificationType.GOAL_PROGRESS,
            message_body=msg,
            progress_percentage=metrics.progress_percentage,
            metadata={
                "milestone": milestone_pct,
                "current_amount": goal.current_amount,
                "target_amount": goal.target_amount,
                "amount_remaining": metrics.amount_remaining,
            },
        )

    def _create_risk_alert(self, goal: FinancialGoal, metrics) -> GoalAlert:
        """Construct deterministic risk trajectory message with zero directive advice."""
        current_contrib = goal.contribution_amount or 0.0
        target_date_str = goal.target_date.strftime("%d %b %Y") if hasattr(goal.target_date, "strftime") else str(goal.target_date)

        msg = (
            f"Goal Update: At your current pace of KSh {current_contrib:,.0f} per month, "
            f"reaching your {goal.name} target by {target_date_str} may be challenging. "
            f"Under current assumptions, saving approximately KSh {metrics.required_monthly_contribution:,.0f} per month "
            f"would be required to reach your target of KSh {goal.target_amount:,.0f}. (demo data)"
        )

        return GoalAlert(
            member_id=goal.member_id,
            goal_id=goal.id,
            goal_name=goal.name,
            alert_type=GoalAlertType.RISK_TRAJECTORY,
            notification_type=NotificationType.GOAL_RISK,
            message_body=msg,
            progress_percentage=metrics.progress_percentage,
            metadata={
                "current_contribution": current_contrib,
                "required_monthly_contribution": metrics.required_monthly_contribution,
                "months_remaining": metrics.months_remaining,
                "target_date": str(goal.target_date),
            },
        )
