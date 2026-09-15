"""In-memory engagement repository for deterministic unit tests."""

from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from app.models.engagement import (
    MemberEngagementPreferences,
    FinancialNewsArticle,
    ProactiveNotification,
    NotificationStatus,
    FeedbackRating,
)


class InMemoryEngagementRepository:
    """Mock storage for preferences, financial news, and notifications."""

    def __init__(self):
        self._preferences: dict[str, MemberEngagementPreferences] = {}
        self._articles: dict[str, FinancialNewsArticle] = {}
        self._notifications: list[ProactiveNotification] = []

    def get_preferences(self, member_id: str) -> Optional[MemberEngagementPreferences]:
        return self._preferences.get(member_id)

    def upsert_preferences(self, prefs: MemberEngagementPreferences) -> MemberEngagementPreferences:
        now = datetime.now(timezone.utc)
        if not prefs.created_at:
            prefs.created_at = now
        prefs.updated_at = now
        self._preferences[prefs.member_id] = prefs
        return prefs

    def add_article(self, article: FinancialNewsArticle) -> FinancialNewsArticle:
        if not article.id:
            article.id = str(uuid.uuid4())
        if not article.retrieved_at:
            article.retrieved_at = datetime.now(timezone.utc)
        self._articles[article.id] = article
        return article

    def get_article(self, article_id: str) -> Optional[FinancialNewsArticle]:
        return self._articles.get(article_id)

    def list_active_articles(self, category: Optional[str] = None) -> list[FinancialNewsArticle]:
        now = datetime.now(timezone.utc)
        active = []
        for a in self._articles.values():
            if not a.is_approved:
                continue
            if a.expiry_at:
                expiry = a.expiry_at if a.expiry_at.tzinfo else a.expiry_at.replace(tzinfo=timezone.utc)
                if expiry <= now:
                    continue
            if category and a.category.value != category:
                continue
            active.append(a)
        active.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return active

    def record_notification(self, notif: ProactiveNotification) -> ProactiveNotification:
        if not notif.id:
            notif.id = str(uuid.uuid4())
        if not notif.created_at:
            notif.created_at = datetime.now(timezone.utc)
        self._notifications.append(notif)
        return notif

    def get_latest_notification_for_member(self, member_id: str) -> Optional[ProactiveNotification]:
        member_notifs = [n for n in self._notifications if n.member_id == member_id]
        if not member_notifs:
            return None
        return sorted(member_notifs, key=lambda n: n.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]

    def has_received_content_recently(
        self, member_id: str, content_id: str, within_days: int = 30
    ) -> bool:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=within_days)
        for n in self._notifications:
            if n.member_id == member_id and n.content_id == content_id:
                if n.status in (NotificationStatus.SENT, NotificationStatus.DELIVERED):
                    created = n.created_at if n.created_at and n.created_at.tzinfo else (n.created_at.replace(tzinfo=timezone.utc) if n.created_at else now)
                    if created >= threshold:
                        return True
        return False

    def update_notification_status(
        self, notification_id: str, status: NotificationStatus, sent_at: Optional[datetime] = None
    ) -> bool:
        for n in self._notifications:
            if n.id == notification_id:
                n.status = status
                if sent_at:
                    n.sent_at = sent_at
                return True
        return False

    def record_feedback(
        self, notification_id: str, feedback: FeedbackRating
    ) -> bool:
        for n in self._notifications:
            if n.id == notification_id:
                n.feedback = feedback
                n.feedback_at = datetime.now(timezone.utc)
                return True
        return False
