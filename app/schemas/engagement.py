"""Pydantic schemas for engagement preferences, financial news, proactive alerts, and feedback."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.engagement import (
    EducationFrequency,
    NewsFrequency,
    NewsCategory,
    NotificationType,
    NotificationStatus,
    FeedbackRating,
)


class EngagementPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member_id: str
    education_frequency: EducationFrequency
    news_frequency: NewsFrequency
    goal_alerts_enabled: bool
    allowed_topics: list[str]
    quiet_hours_start: int = Field(ge=0, le=23)
    quiet_hours_end: int = Field(ge=0, le=23)
    preferred_language: str
    updated_at: Optional[datetime] = None


class EngagementPreferencesUpdate(BaseModel):
    education_frequency: Optional[EducationFrequency] = None
    news_frequency: Optional[NewsFrequency] = None
    goal_alerts_enabled: Optional[bool] = None
    allowed_topics: Optional[list[str]] = None
    quiet_hours_start: Optional[int] = Field(None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(None, ge=0, le=23)
    preferred_language: Optional[str] = None


class NewsArticleCreate(BaseModel):
    id: Optional[str] = None
    source: str
    title: str
    content: str
    summary: Optional[str] = None
    category: NewsCategory
    url: Optional[str] = None
    published_at: datetime
    expiry_at: datetime
    is_approved: bool = True


class NewsArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    title: str
    content: str
    summary: Optional[str] = None
    category: NewsCategory
    url: Optional[str] = None
    published_at: datetime
    expiry_at: datetime
    is_approved: bool


class ProactiveNotificationCreate(BaseModel):
    id: Optional[str] = None
    member_id: str
    notification_type: NotificationType
    content_id: Optional[str] = None
    message_body: str
    delivery_channel: str = "whatsapp"
    status: NotificationStatus = NotificationStatus.PENDING


class ProactiveNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    member_id: str
    notification_type: NotificationType
    content_id: Optional[str] = None
    message_body: str
    delivery_channel: str
    status: NotificationStatus
    sent_at: Optional[datetime] = None
    feedback: Optional[FeedbackRating] = None
    feedback_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class MemberFeedbackRequest(BaseModel):
    member_id: str
    notification_id: Optional[str] = None
    feedback: FeedbackRating
    channel: str = "whatsapp"


class MemberFeedbackResponse(BaseModel):
    status: str
    message: str
    member_id: str
    notification_id: Optional[str] = None
    feedback: FeedbackRating


class TopicConfusionMetric(BaseModel):
    topic: str
    question_count: int
    unanswered_queries: list[str]
    suggested_action: str


class KnowledgeGapIntelligenceSummary(BaseModel):
    total_unanswered_questions: int
    top_topics: list[TopicConfusionMetric]
    generated_at: datetime
