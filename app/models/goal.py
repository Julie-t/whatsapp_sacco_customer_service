"""Domain models for financial goals."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional


class GoalType(str, Enum):
    EDUCATION = "education"
    EMERGENCY_FUND = "emergency_fund"
    RETIREMENT = "retirement"
    ASSET_PURCHASE = "asset_purchase"
    GENERAL_SAVINGS = "general_savings"
    BUSINESS = "business"
    CUSTOM = "custom"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class ContributionFrequency(str, Enum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    LUMP_SUM = "lump_sum"


@dataclass
class FinancialGoal:
    """Domain model for a member's financial goal."""
    id: str
    member_id: str
    goal_type: GoalType
    name: str
    target_amount: float
    target_date: date
    current_amount: float = 0.0
    contribution_amount: Optional[float] = None
    contribution_frequency: ContributionFrequency = ContributionFrequency.MONTHLY
    status: GoalStatus = GoalStatus.ACTIVE
    notification_frequency: str = "monthly"
    notes: Optional[str] = None
    is_demo: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
