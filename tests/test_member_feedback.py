"""Tests for MemberFeedbackService (feedback ratings and MORE elaborations)."""

from datetime import datetime, timezone
import pytest

from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
from app.models.engagement import (
    ProactiveNotification,
    NotificationType,
    NotificationStatus,
    FeedbackRating,
)
from app.services.proactive.member_feedback_service import MemberFeedbackService


def test_handle_helpful_feedback():
    repo = InMemoryEngagementRepository()
    notif = ProactiveNotification(
        id="notif_101",
        member_id="mem_01",
        notification_type=NotificationType.SCHEDULED_EDUCATION,
        content_id="budgeting",
        message_body="Tip on budgeting...",
        status=NotificationStatus.SENT,
    )
    repo.record_notification(notif)

    service = MemberFeedbackService(engagement_repo=repo)
    handled, msg = service.handle_incoming_feedback("mem_01", "asante")

    assert handled is True
    assert "Asante sana" in msg

    updated = repo.get_latest_notification_for_member("mem_01")
    assert updated.feedback == FeedbackRating.HELPFUL


def test_handle_not_helpful_feedback():
    repo = InMemoryEngagementRepository()
    notif = ProactiveNotification(
        id="notif_102",
        member_id="mem_02",
        notification_type=NotificationType.FINANCIAL_NEWS,
        content_id="art_rates",
        message_body="News update...",
        status=NotificationStatus.SENT,
    )
    repo.record_notification(notif)

    service = MemberFeedbackService(engagement_repo=repo)
    handled, msg = service.handle_incoming_feedback("mem_02", "not helpful")

    assert handled is True
    assert "noted your preference" in msg

    updated = repo.get_latest_notification_for_member("mem_02")
    assert updated.feedback == FeedbackRating.NOT_HELPFUL


def test_handle_more_elaboration():
    repo = InMemoryEngagementRepository()
    notif = ProactiveNotification(
        id="notif_103",
        member_id="mem_03",
        notification_type=NotificationType.SCHEDULED_EDUCATION,
        content_id="compound_interest",
        message_body="Compound interest explanation...",
        status=NotificationStatus.SENT,
    )
    repo.record_notification(notif)

    service = MemberFeedbackService(engagement_repo=repo)
    handled, msg = service.handle_incoming_feedback("mem_03", "MORE")

    assert handled is True
    assert "KSh 5,000 monthly" in msg
    assert "Year 2" in msg


def test_unrelated_message_not_handled():
    service = MemberFeedbackService(engagement_repo=InMemoryEngagementRepository())
    handled, msg = service.handle_incoming_feedback("mem_04", "What is my loan balance?")
    assert handled is False
    assert msg is None
