"""Tests for EngagementRepository (In-Memory and Contract verification)."""

import pytest
from datetime import datetime, timezone, timedelta
from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
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


def test_preferences_upsert_and_get():
    repo = InMemoryEngagementRepository()
    prefs = MemberEngagementPreferences(
        member_id="mem_001",
        education_frequency=EducationFrequency.WEEKLY,
        news_frequency=NewsFrequency.MONTHLY,
        goal_alerts_enabled=True,
        allowed_topics=["budgeting", "saving"],
        quiet_hours_start=20,
        quiet_hours_end=8,
        preferred_language="en",
    )
    saved = repo.upsert_preferences(prefs)
    assert saved.member_id == "mem_001"
    assert saved.education_frequency == EducationFrequency.WEEKLY

    fetched = repo.get_preferences("mem_001")
    assert fetched is not None
    assert fetched.member_id == "mem_001"
    assert fetched.news_frequency == NewsFrequency.MONTHLY
    assert "budgeting" in fetched.allowed_topics


def test_article_add_and_list_active_and_expiry():
    repo = InMemoryEngagementRepository()
    now = datetime.now(timezone.utc)

    # Valid article
    active_art = FinancialNewsArticle(
        id="art_001",
        source="Central Bank of Kenya",
        title="CBK Retains Benchmark Rate at 12.75%",
        content="CBK Monetary Policy Committee decided to retain benchmark rates...",
        category=NewsCategory.INTEREST_RATES,
        published_at=now,
        expiry_at=now + timedelta(days=30),
        is_approved=True,
    )
    # Expired article
    expired_art = FinancialNewsArticle(
        id="art_002",
        source="Business Daily",
        title="Old Inflation Report 2024",
        content="Past inflation report...",
        category=NewsCategory.INFLATION,
        published_at=now - timedelta(days=60),
        expiry_at=now - timedelta(days=1),
        is_approved=True,
    )

    repo.add_article(active_art)
    repo.add_article(expired_art)

    active_list = repo.list_active_articles()
    assert len(active_list) == 1
    assert active_list[0].id == "art_001"

    # Category filter
    rates_list = repo.list_active_articles(category="interest_rates")
    assert len(rates_list) == 1
    assert rates_list[0].id == "art_001"

    saving_list = repo.list_active_articles(category="saving_tips")
    assert len(saving_list) == 0


def test_notification_delivery_deduplication_and_feedback():
    repo = InMemoryEngagementRepository()
    now = datetime.now(timezone.utc)

    notif = ProactiveNotification(
        id="notif_001",
        member_id="mem_001",
        notification_type=NotificationType.SCHEDULED_EDUCATION,
        content_id="compound_interest",
        message_body="Habari Eddy, here is why compound interest helps your savings.",
        status=NotificationStatus.SENT,
        sent_at=now,
        created_at=now,
    )
    repo.record_notification(notif)

    # Check deduplication within 30 days
    assert repo.has_received_content_recently("mem_001", "compound_interest", within_days=30) is True
    assert repo.has_received_content_recently("mem_001", "budgeting", within_days=30) is False

    # Check latest notification retrieval
    latest = repo.get_latest_notification_for_member("mem_001")
    assert latest is not None
    assert latest.id == "notif_001"

    # Record feedback
    ok = repo.record_feedback("notif_001", FeedbackRating.HELPFUL)
    assert ok is True

    updated_latest = repo.get_latest_notification_for_member("mem_001")
    assert updated_latest.feedback == FeedbackRating.HELPFUL
