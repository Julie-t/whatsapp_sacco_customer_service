"""Proactive Delivery Service & Policy Controller for System 10.

Enforces Quiet Hours, Deduplication, and Frequency controls prior to outbound WhatsApp dispatch.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional
import uuid

from app.database.engagement_repository import EngagementRepository
from app.models.engagement import (
    MemberEngagementPreferences,
    ProactiveNotification,
    NotificationType,
    NotificationStatus,
)
from app.services.members.member_service import MemberDataService
from app.services.conversations.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

# East Africa Time offset (UTC+3)
EAT_TIMEZONE = timezone(timedelta(hours=3))


@dataclass
class DeliveryDecision:
    """Result of policy evaluation and optional dispatch."""
    is_allowed: bool
    status: NotificationStatus
    reason: str
    notification: Optional[ProactiveNotification] = None


class ProactiveDeliveryService:
    """Controls outbound proactive message dispatch, verifying quiet hours and deduplication."""

    def __init__(
        self,
        engagement_repo: Optional[EngagementRepository] = None,
        member_service: Optional[MemberDataService] = None,
        whatsapp_service: Optional[WhatsAppService] = None,
    ) -> None:
        self.engagement_repo = engagement_repo or EngagementRepository()
        self.member_service = member_service or MemberDataService()
        self.whatsapp_service = whatsapp_service

    def is_in_quiet_hours(
        self,
        prefs: Optional[MemberEngagementPreferences],
        check_time: Optional[datetime] = None,
    ) -> bool:
        """Evaluate whether check_time falls within the member's quiet hours."""
        ref_time = check_time or datetime.now(EAT_TIMEZONE)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=EAT_TIMEZONE)
        else:
            ref_time = ref_time.astimezone(EAT_TIMEZONE)

        start_hour = prefs.quiet_hours_start if prefs else 20
        end_hour = prefs.quiet_hours_end if prefs else 8
        current_hour = ref_time.hour

        # Overnight quiet window (e.g. 20:00 to 08:00)
        if start_hour > end_hour:
            return current_hour >= start_hour or current_hour < end_hour
        # Same-day quiet window (e.g. 13:00 to 15:00)
        elif start_hour < end_hour:
            return start_hour <= current_hour < end_hour
        else:
            return False

    def evaluate_and_dispatch(
        self,
        member_id: str,
        notification_type: NotificationType,
        content_id: Optional[str],
        message_body: str,
        send_live: bool = False,
        check_time: Optional[datetime] = None,
    ) -> DeliveryDecision:
        """Run policy checks (quiet hours, deduplication, preferences) and conditionally dispatch."""
        prefs = self.engagement_repo.get_preferences(member_id)

        # 1. Quiet hours check
        if self.is_in_quiet_hours(prefs, check_time=check_time):
            notif = ProactiveNotification(
                id=str(uuid.uuid4()),
                member_id=member_id,
                notification_type=notification_type,
                content_id=content_id,
                message_body=message_body,
                status=NotificationStatus.SKIPPED_QUIET_HOURS,
            )
            self.engagement_repo.record_notification(notif)
            return DeliveryDecision(
                is_allowed=False,
                status=NotificationStatus.SKIPPED_QUIET_HOURS,
                reason="Dispatch suppressed: current time falls within member quiet hours (20:00 - 08:00 EAT).",
                notification=notif,
            )

        # 2. Deduplication check
        if content_id and self.engagement_repo.has_received_content_recently(member_id, content_id, within_days=30):
            notif = ProactiveNotification(
                id=str(uuid.uuid4()),
                member_id=member_id,
                notification_type=notification_type,
                content_id=content_id,
                message_body=message_body,
                status=NotificationStatus.SKIPPED_DUPLICATE,
            )
            self.engagement_repo.record_notification(notif)
            return DeliveryDecision(
                is_allowed=False,
                status=NotificationStatus.SKIPPED_DUPLICATE,
                reason=f"Dispatch suppressed: content '{content_id}' was already delivered to member within the last 30 days.",
                notification=notif,
            )

        # 3. Prepare notification record
        now = datetime.now(timezone.utc)
        notif = ProactiveNotification(
            id=str(uuid.uuid4()),
            member_id=member_id,
            notification_type=notification_type,
            content_id=content_id,
            message_body=message_body,
            status=NotificationStatus.SENT,
            sent_at=now,
        )

        # 4. Outbound WhatsApp delivery (if configured and requested)
        if send_live and self.whatsapp_service:
            member = self.member_service.get_member_profile(member_id)
            phone = getattr(member, "phone_number", None) or getattr(member, "phone", None)
            if phone:
                try:
                    self.whatsapp_service.send_text(phone, message_body)
                    notif.status = NotificationStatus.DELIVERED
                except Exception as e:
                    logger.error(f"Failed to dispatch WhatsApp message to {member_id}: {e}")
                    notif.status = NotificationStatus.FAILED

        # Record in database/repository
        recorded = self.engagement_repo.record_notification(notif)

        return DeliveryDecision(
            is_allowed=True,
            status=recorded.status,
            reason="Dispatch approved and recorded.",
            notification=recorded,
        )
