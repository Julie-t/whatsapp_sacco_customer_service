"""Domain models for proactive engagement, preferences, news, and notifications."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EducationFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    PAUSED = "paused"


class NewsFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PAUSED = "paused"


class NewsCategory(str, Enum):
    RETIREMENT = "retirement"
    INTEREST_RATES = "interest_rates"
    SAVING_TIPS = "saving_tips"
    INFLATION = "inflation"
    SACCO_REGULATIONS = "sacco_regulations"
    EDUCATION_FUNDS = "education_funds"
    GENERAL_ECONOMY = "general_economy"


class NotificationType(str, Enum):
    SCHEDULED_EDUCATION = "scheduled_education"
    GOAL_PROGRESS = "goal_progress"
    GOAL_RISK = "goal_risk"
    FINANCIAL_NEWS = "financial_news"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED_QUIET_HOURS = "skipped_quiet_hours"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    SKIPPED_PAUSED = "skipped_paused"


class FeedbackRating(str, Enum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


@dataclass
class MemberEngagementPreferences:
    """Member preferences controlling outbound message categories, frequency, and quiet hours."""
    member_id: str
    education_frequency: EducationFrequency = EducationFrequency.WEEKLY
    news_frequency: NewsFrequency = NewsFrequency.WEEKLY
    goal_alerts_enabled: bool = True
    allowed_topics: list[str] = field(default_factory=lambda: [
        "budgeting", "saving", "compound_interest", "debt_management", "emergency_fund"
    ])
    quiet_hours_start: int = 20  # 8 PM (20:00)
    quiet_hours_end: int = 8     # 8 AM (08:00)
    preferred_language: str = "en"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class FinancialNewsArticle:
    """Trusted, SACCO-curated financial news article with validity window."""
    id: str
    source: str
    title: str
    content: str
    summary: Optional[str] = None
    category: NewsCategory = NewsCategory.GENERAL_ECONOMY
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    expiry_at: Optional[datetime] = None
    is_approved: bool = True


@dataclass
class ProactiveNotification:
    """Auditable log of proactive messages generated and delivered to a member."""
    id: str
    member_id: str
    notification_type: NotificationType
    content_id: Optional[str]
    message_body: str
    delivery_channel: str = "whatsapp"
    status: NotificationStatus = NotificationStatus.PENDING
    sent_at: Optional[datetime] = None
    feedback: Optional[FeedbackRating] = None
    feedback_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
