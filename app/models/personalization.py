"""Domain models for personalization and financial education."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from app.models.goal import FinancialGoal
from app.schemas.goal import GoalCalculationResult, GoalResponse
from typing import Optional, Union


class KnowledgeLevel(str, Enum):
    """Member familiarity with financial concepts."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class CommunicationStyle(str, Enum):
    """Preferred explanation depth and tone."""
    SIMPLE = "simple"
    STANDARD = "standard"
    DETAILED = "detailed"


class EducationTopic(str, Enum):
    """Standardized financial education topics."""
    BUDGETING = "budgeting"
    COMPOUND_INTEREST = "compound_interest"
    EMERGENCY_FUND = "emergency_fund"
    DEBT_MANAGEMENT = "debt_management"
    SAVINGS_DISCIPLINE = "savings_discipline"
    ASSET_PURCHASE = "asset_purchase"
    RETIREMENT = "retirement"
    SACCO_SHARES = "sacco_shares"
    GENERAL_EDUCATION = "general_education"


@dataclass
class EducationHistoryRecord:
    """A single topic previously delivered to a member."""
    id: Optional[int] = None
    member_id: str = ""
    topic: str = ""
    summary: Optional[str] = None
    goal_id: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class PersonalizationContext:
    """Unified context object passed to personalization and education services."""
    member_id: str
    display_name: str
    preferred_language: str = "en"
    knowledge_level: KnowledgeLevel = KnowledgeLevel.BEGINNER
    communication_style: CommunicationStyle = CommunicationStyle.SIMPLE
    active_goal: Optional[Union[FinancialGoal, GoalResponse]] = None
    goal_progress: Optional[GoalCalculationResult] = None
    recent_topics: list[str] = field(default_factory=list)
    query: str = ""
    retrieved_evidence: list[str] = field(default_factory=list)
