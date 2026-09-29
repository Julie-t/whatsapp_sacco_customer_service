"""PostgreSQL repository for member engagement preferences, financial news, and notifications."""

import logging
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.database.connection import get_connection
from app.models.engagement import (
    MemberEngagementPreferences,
    EducationFrequency,
    NewsFrequency,
    NewsCategory,
    FinancialNewsArticle,
    ProactiveNotification,
    NotificationType,
    NotificationStatus,
    FeedbackRating,
)

logger = logging.getLogger(__name__)


class EngagementRepository:
    """PostgreSQL storage for engagement preferences, news articles, and notifications."""

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------
    def get_preferences(self, member_id: str) -> Optional[MemberEngagementPreferences]:
        """Fetch engagement preferences for a member."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT member_id, education_frequency, news_frequency, goal_alerts_enabled,
                       allowed_topics, quiet_hours_start, quiet_hours_end, preferred_language,
                       created_at, updated_at
                FROM member_engagement_preferences
                WHERE member_id = %s
                """,
                (member_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return MemberEngagementPreferences(
                member_id=row[0],
                education_frequency=EducationFrequency(row[1]),
                news_frequency=NewsFrequency(row[2]),
                goal_alerts_enabled=row[3],
                allowed_topics=list(row[4]) if row[4] else [],
                quiet_hours_start=row[5],
                quiet_hours_end=row[6],
                preferred_language=row[7],
                created_at=row[8],
                updated_at=row[9],
            )

    def upsert_preferences(self, prefs: MemberEngagementPreferences) -> MemberEngagementPreferences:
        """Create or update engagement preferences."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO member_engagement_preferences (
                    member_id, education_frequency, news_frequency, goal_alerts_enabled,
                    allowed_topics, quiet_hours_start, quiet_hours_end, preferred_language,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (member_id) DO UPDATE SET
                    education_frequency = EXCLUDED.education_frequency,
                    news_frequency = EXCLUDED.news_frequency,
                    goal_alerts_enabled = EXCLUDED.goal_alerts_enabled,
                    allowed_topics = EXCLUDED.allowed_topics,
                    quiet_hours_start = EXCLUDED.quiet_hours_start,
                    quiet_hours_end = EXCLUDED.quiet_hours_end,
                    preferred_language = EXCLUDED.preferred_language,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING member_id, education_frequency, news_frequency, goal_alerts_enabled,
                          allowed_topics, quiet_hours_start, quiet_hours_end, preferred_language,
                          created_at, updated_at
                """,
                (
                    prefs.member_id,
                    prefs.education_frequency.value,
                    prefs.news_frequency.value,
                    prefs.goal_alerts_enabled,
                    prefs.allowed_topics,
                    prefs.quiet_hours_start,
                    prefs.quiet_hours_end,
                    prefs.preferred_language,
                ),
            )
            row = cur.fetchone()
            return MemberEngagementPreferences(
                member_id=row[0],
                education_frequency=EducationFrequency(row[1]),
                news_frequency=NewsFrequency(row[2]),
                goal_alerts_enabled=row[3],
                allowed_topics=list(row[4]) if row[4] else [],
                quiet_hours_start=row[5],
                quiet_hours_end=row[6],
                preferred_language=row[7],
                created_at=row[8],
                updated_at=row[9],
            )

    # ------------------------------------------------------------------
    # Financial News Articles
    # ------------------------------------------------------------------
    def add_article(self, article: FinancialNewsArticle) -> FinancialNewsArticle:
        """Store an approved financial news article."""
        article_id = article.id or str(uuid.uuid4())
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO financial_news_articles (
                    id, source, title, content, summary, category, url,
                    published_at, retrieved_at, expiry_at, is_approved
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    summary = EXCLUDED.summary,
                    expiry_at = EXCLUDED.expiry_at,
                    is_approved = EXCLUDED.is_approved
                RETURNING id, source, title, content, summary, category, url,
                          published_at, retrieved_at, expiry_at, is_approved
                """,
                (
                    article_id,
                    article.source,
                    article.title,
                    article.content,
                    article.summary,
                    article.category.value if isinstance(article.category, NewsCategory) else str(article.category),
                    article.url,
                    article.published_at,
                    article.expiry_at,
                    article.is_approved,
                ),
            )
            row = cur.fetchone()
            return FinancialNewsArticle(
                id=row[0],
                source=row[1],
                title=row[2],
                content=row[3],
                summary=row[4],
                category=NewsCategory(row[5]),
                url=row[6],
                published_at=row[7],
                retrieved_at=row[8],
                expiry_at=row[9],
                is_approved=row[10],
            )

    def get_article(self, article_id: str) -> Optional[FinancialNewsArticle]:
        """Fetch a single news article by ID."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source, title, content, summary, category, url,
                       published_at, retrieved_at, expiry_at, is_approved
                FROM financial_news_articles
                WHERE id = %s
                """,
                (article_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return FinancialNewsArticle(
                id=row[0],
                source=row[1],
                title=row[2],
                content=row[3],
                summary=row[4],
                category=NewsCategory(row[5]),
                url=row[6],
                published_at=row[7],
                retrieved_at=row[8],
                expiry_at=row[9],
                is_approved=row[10],
            )

    def list_active_articles(self, category: Optional[str] = None) -> list[FinancialNewsArticle]:
        """List active, approved articles whose expiry_at is in the future."""
        with get_connection() as conn, conn.cursor() as cur:
            if category:
                cur.execute(
                    """
                    SELECT id, source, title, content, summary, category, url,
                           published_at, retrieved_at, expiry_at, is_approved
                    FROM financial_news_articles
                    WHERE is_approved = true AND expiry_at > CURRENT_TIMESTAMP AND category = %s
                    ORDER BY published_at DESC
                    """,
                    (category,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, source, title, content, summary, category, url,
                           published_at, retrieved_at, expiry_at, is_approved
                    FROM financial_news_articles
                    WHERE is_approved = true AND expiry_at > CURRENT_TIMESTAMP
                    ORDER BY published_at DESC
                    """,
                )
            results = []
            for row in cur.fetchall():
                results.append(
                    FinancialNewsArticle(
                        id=row[0],
                        source=row[1],
                        title=row[2],
                        content=row[3],
                        summary=row[4],
                        category=NewsCategory(row[5]),
                        url=row[6],
                        published_at=row[7],
                        retrieved_at=row[8],
                        expiry_at=row[9],
                        is_approved=row[10],
                    )
                )
            return results

    # ------------------------------------------------------------------
    # Notifications & Audit
    # ------------------------------------------------------------------
    def record_notification(self, notif: ProactiveNotification) -> ProactiveNotification:
        """Insert a proactive notification log."""
        notif_id = notif.id or str(uuid.uuid4())
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO proactive_notifications (
                    id, member_id, notification_type, content_id, message_body,
                    delivery_channel, status, sent_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, member_id, notification_type, content_id, message_body,
                          delivery_channel, status, sent_at, feedback, feedback_at, created_at
                """,
                (
                    notif_id,
                    notif.member_id,
                    notif.notification_type.value,
                    notif.content_id,
                    notif.message_body,
                    notif.delivery_channel,
                    notif.status.value,
                    notif.sent_at,
                ),
            )
            row = cur.fetchone()
            return ProactiveNotification(
                id=row[0],
                member_id=row[1],
                notification_type=NotificationType(row[2]),
                content_id=row[3],
                message_body=row[4],
                delivery_channel=row[5],
                status=NotificationStatus(row[6]),
                sent_at=row[7],
                feedback=FeedbackRating(row[8]) if row[8] else None,
                feedback_at=row[9],
                created_at=row[10],
            )

    def get_latest_notification_for_member(self, member_id: str) -> Optional[ProactiveNotification]:
        """Fetch the most recent proactive notification delivered to a member."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, member_id, notification_type, content_id, message_body,
                       delivery_channel, status, sent_at, feedback, feedback_at, created_at
                FROM proactive_notifications
                WHERE member_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (member_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ProactiveNotification(
                id=row[0],
                member_id=row[1],
                notification_type=NotificationType(row[2]),
                content_id=row[3],
                message_body=row[4],
                delivery_channel=row[5],
                status=NotificationStatus(row[6]),
                sent_at=row[7],
                feedback=FeedbackRating(row[8]) if row[8] else None,
                feedback_at=row[9],
                created_at=row[10],
            )

    def has_received_content_recently(
        self, member_id: str, content_id: str, within_days: int = 30
    ) -> bool:
        """Check if a specific content_id (e.g. topic or article ID) was sent within recent window."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM proactive_notifications
                WHERE member_id = %s
                  AND content_id = %s
                  AND status IN ('sent', 'delivered')
                  AND created_at >= CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')
                LIMIT 1
                """,
                (member_id, content_id, within_days),
            )
            return cur.fetchone() is not None

    def update_notification_status(
        self, notification_id: str, status: NotificationStatus, sent_at: Optional[datetime] = None
    ) -> bool:
        """Update notification delivery status."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE proactive_notifications
                SET status = %s, sent_at = COALESCE(%s, sent_at)
                WHERE id = %s
                """,
                (status.value, sent_at, notification_id),
            )
            return cur.rowcount > 0

    def record_feedback(
        self, notification_id: str, feedback: FeedbackRating
    ) -> bool:
        """Record member feedback on a delivered notification."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE proactive_notifications
                SET feedback = %s, feedback_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (feedback.value, notification_id),
            )
            return cur.rowcount > 0
