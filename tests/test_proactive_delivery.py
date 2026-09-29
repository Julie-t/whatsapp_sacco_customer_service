"""Tests for ProactiveDeliveryService (quiet hours and deduplication controls)."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
from app.models.engagement import (
    MemberEngagementPreferences,
    NotificationType,
    NotificationStatus,
)
from app.services.proactive.proactive_delivery_service import (
    ProactiveDeliveryService,
    EAT_TIMEZONE,
)


def test_quiet_hours_evaluation():
    service = ProactiveDeliveryService()
    prefs = MemberEngagementPreferences(
        member_id="mem_quiet_01",
        quiet_hours_start=20,  # 8 PM
        quiet_hours_end=8,     # 8 AM
    )

    # 21:00 (9 PM) -> in quiet hours
    night_time = datetime(2026, 9, 9, 21, 0, 0, tzinfo=EAT_TIMEZONE)
    assert service.is_in_quiet_hours(prefs, check_time=night_time) is True

    # 03:00 (3 AM) -> in quiet hours
    early_morning = datetime(2026, 9, 9, 3, 0, 0, tzinfo=EAT_TIMEZONE)
    assert service.is_in_quiet_hours(prefs, check_time=early_morning) is True

    # 10:00 (10 AM) -> daytime, not in quiet hours
    day_time = datetime(2026, 9, 9, 10, 0, 0, tzinfo=EAT_TIMEZONE)
    assert service.is_in_quiet_hours(prefs, check_time=day_time) is False


def test_evaluate_and_dispatch_suppressed_by_quiet_hours():
    repo = InMemoryEngagementRepository()
    service = ProactiveDeliveryService(engagement_repo=repo)

    night_time = datetime(2026, 9, 9, 22, 0, 0, tzinfo=EAT_TIMEZONE)
    decision = service.evaluate_and_dispatch(
        member_id="mem_01",
        notification_type=NotificationType.SCHEDULED_EDUCATION,
        content_id="compound_interest",
        message_body="Tip of the day...",
        check_time=night_time,
    )

    assert decision.is_allowed is False
    assert decision.status == NotificationStatus.SKIPPED_QUIET_HOURS
    assert "quiet hours" in decision.reason


def test_evaluate_and_dispatch_suppressed_by_deduplication():
    repo = InMemoryEngagementRepository()
    service = ProactiveDeliveryService(engagement_repo=repo)

    day_time = datetime(2026, 9, 9, 11, 0, 0, tzinfo=EAT_TIMEZONE)

    # First dispatch allowed
    first = service.evaluate_and_dispatch(
        member_id="mem_02",
        notification_type=NotificationType.SCHEDULED_EDUCATION,
        content_id="budgeting",
        message_body="Budgeting tip...",
        check_time=day_time,
    )
    assert first.is_allowed is True
    assert first.status == NotificationStatus.SENT

    # Second dispatch of the same content_id is suppressed by deduplication
    second = service.evaluate_and_dispatch(
        member_id="mem_02",
        notification_type=NotificationType.SCHEDULED_EDUCATION,
        content_id="budgeting",
        message_body="Budgeting tip...",
        check_time=day_time,
    )
    assert second.is_allowed is False
    assert second.status == NotificationStatus.SKIPPED_DUPLICATE
    assert "already delivered" in second.reason
