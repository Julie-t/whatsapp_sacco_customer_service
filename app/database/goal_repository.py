"""PostgreSQL-backed repository for financial goals."""

import logging
from typing import Optional

from app.database.connection import get_connection
from app.models.goal import FinancialGoal, GoalStatus, GoalType, ContributionFrequency

logger = logging.getLogger(__name__)


class GoalRepository:
    """Persistent financial goals storage backed by PostgreSQL."""

    @staticmethod
    def create(goal: FinancialGoal) -> FinancialGoal:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO financial_goals (
                        id, member_id, goal_type, name, target_amount, current_amount,
                        target_date, contribution_amount, contribution_frequency,
                        status, notification_frequency, notes, is_demo
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING created_at, updated_at
                    """,
                    (
                        goal.id,
                        goal.member_id,
                        goal.goal_type.value,
                        goal.name,
                        goal.target_amount,
                        goal.current_amount,
                        goal.target_date,
                        goal.contribution_amount,
                        goal.contribution_frequency.value,
                        goal.status.value,
                        goal.notification_frequency,
                        goal.notes,
                        goal.is_demo,
                    ),
                )
                row = cur.fetchone()
                if row:
                    goal.created_at = row[0]
                    goal.updated_at = row[1]
                return goal
        except Exception:
            logger.exception("Failed to create goal %s", goal.id)
            raise

    @staticmethod
    def get_by_id(goal_id: str) -> Optional[FinancialGoal]:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, member_id, goal_type, name, target_amount, current_amount,
                           target_date, contribution_amount, contribution_frequency,
                           status, notification_frequency, notes, is_demo, created_at, updated_at
                    FROM financial_goals
                    WHERE id = %s
                    """,
                    (goal_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return FinancialGoal(
                    id=row[0],
                    member_id=row[1],
                    goal_type=GoalType(row[2]),
                    name=row[3],
                    target_amount=float(row[4]),
                    current_amount=float(row[5]),
                    target_date=row[6],
                    contribution_amount=float(row[7]) if row[7] is not None else None,
                    contribution_frequency=ContributionFrequency(row[8]),
                    status=GoalStatus(row[9]),
                    notification_frequency=row[10],
                    notes=row[11],
                    is_demo=row[12],
                    created_at=row[13],
                    updated_at=row[14],
                )
        except Exception:
            logger.exception("Failed to get goal by ID %s", goal_id)
            return None

    @staticmethod
    def get_by_member(
        member_id: str,
        status: Optional[GoalStatus] = None,
    ) -> list[FinancialGoal]:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id, member_id, goal_type, name, target_amount, current_amount,
                               target_date, contribution_amount, contribution_frequency,
                               status, notification_frequency, notes, is_demo, created_at, updated_at
                        FROM financial_goals
                        WHERE member_id = %s AND status = %s
                        ORDER BY target_date ASC, updated_at DESC, created_at DESC
                        """,
                        (member_id, status.value),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, member_id, goal_type, name, target_amount, current_amount,
                               target_date, contribution_amount, contribution_frequency,
                               status, notification_frequency, notes, is_demo, created_at, updated_at
                        FROM financial_goals
                        WHERE member_id = %s
                        ORDER BY target_date ASC, updated_at DESC, created_at DESC
                        """,
                        (member_id,),
                    )
                rows = cur.fetchall()
                return [
                    FinancialGoal(
                        id=row[0],
                        member_id=row[1],
                        goal_type=GoalType(row[2]),
                        name=row[3],
                        target_amount=float(row[4]),
                        current_amount=float(row[5]),
                        target_date=row[6],
                        contribution_amount=float(row[7]) if row[7] is not None else None,
                        contribution_frequency=ContributionFrequency(row[8]),
                        status=GoalStatus(row[9]),
                        notification_frequency=row[10],
                        notes=row[11],
                        is_demo=row[12],
                        created_at=row[13],
                        updated_at=row[14],
                    )
                    for row in rows
                ]
        except Exception:
            logger.exception("Failed to get goals for member %s", member_id)
            return []

    @staticmethod
    def get_active_goal(member_id: str) -> Optional[FinancialGoal]:
        """Return the primary active goal for a member (most imminent target date)."""
        goals = GoalRepository.get_by_member(member_id, status=GoalStatus.ACTIVE)
        return goals[0] if goals else None

    @staticmethod
    def update(goal_id: str, **kwargs) -> Optional[FinancialGoal]:
        allowed_fields = {
            "name", "target_amount", "current_amount", "target_date",
            "contribution_amount", "contribution_frequency", "status",
            "notification_frequency", "notes"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}
        if not updates:
            return GoalRepository.get_by_id(goal_id)

        set_clauses = []
        values = []
        for field, value in updates.items():
            if isinstance(value, GoalType) or isinstance(value, GoalStatus) or isinstance(value, ContributionFrequency):
                value = value.value
            set_clauses.append(f"{field} = %s")
            values.append(value)
        values.append(goal_id)

        sql = f"""
            UPDATE financial_goals
            SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(sql, tuple(values))
            return GoalRepository.get_by_id(goal_id)
        except Exception:
            logger.exception("Failed to update goal %s", goal_id)
            return None

    @staticmethod
    def delete(goal_id: str) -> bool:
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM financial_goals WHERE id = %s", (goal_id,))
                return cur.rowcount > 0
        except Exception:
            logger.exception("Failed to delete goal %s", goal_id)
            return False
