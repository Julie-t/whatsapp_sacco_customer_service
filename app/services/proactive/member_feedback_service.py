"""Member Feedback & 'MORE' Elaboration Service for System 10.

Captures inbound feedback on proactive notifications and provides interactive expansions
when members reply 'MORE' or 'ENDELEA'.
"""

from typing import Optional, Tuple
import logging

from app.database.engagement_repository import EngagementRepository
from app.models.engagement import (
    FeedbackRating,
    NotificationType,
    ProactiveNotification,
)

logger = logging.getLogger(__name__)


class MemberFeedbackService:
    """Processes feedback ratings and proactive message elaborations."""

    HELPFUL_TERMS = ("helpful", "useful", "good", "asante", "yes", "ndio", "msaada")
    NOT_HELPFUL_TERMS = ("not helpful", "not useful", "bad", "no", "hapana", "si msaada")
    MORE_TERMS = ("more", "endelea", "example", "mfano", "tell me more")

    TOPIC_EXAMPLES = {
        "compound_interest": (
            "Here is a practical compounding example with our SACCO:\n\n"
            "If you deposit KSh 5,000 monthly at an estimated 10% annual dividend:\n"
            "- Year 1 deposits: KSh 60,000 plus approx KSh 3,250 in dividends.\n"
            "- Year 2: Dividends are calculated on the full KSh 63,250 balance plus new savings.\n"
            "By leaving dividends in your account, compounding accelerates your balance significantly over time."
        ),
        "budgeting": (
            "Here is a practical 50/30/20 budgeting example:\n\n"
            "On a monthly income of KSh 50,000:\n"
            "- Essentials (50%): KSh 25,000 for rent, food, and utilities.\n"
            "- Personal (30%): KSh 15,000 for discretionary spending.\n"
            "- Savings & Goals (20%): KSh 10,000 directly to your SACCO deposit account.\n\n"
            "Automating your SACCO deposit on payday ensures you save before spending."
        ),
        "emergency_fund": (
            "Here is a practical emergency buffer example:\n\n"
            "If your basic monthly living expenses are KSh 30,000, a starter 3-month safety reserve is KSh 90,000.\n"
            "Saving KSh 7,500 per month builds this full buffer in 12 months, protecting you from taking high-interest loans for unexpected emergencies."
        ),
        "debt_management": (
            "Here is a practical debt prioritization example:\n\n"
            "If you have a digital emergency loan at 15% monthly and a SACCO loan at 1% monthly on reducing balance, "
            "direct all extra funds to clear the digital loan first. Once cleared, redirect those repayments to your SACCO savings."
        ),
        "savings_discipline": (
            "Here is how automated discipline works in practice:\n\n"
            "Set up a check-off deduction or bank standing order on the 1st of every month. "
            "When savings are deducted before you receive disposable cash, reaching your target becomes effortless."
        ),
        "sacco_shares": (
            "Here is how share capital works:\n\n"
            "Share capital represents your equity ownership in the SACCO. While non-withdrawable, "
            "it qualifies you for annual dividend distributions approved by the AGM. Retained shares can be transferred upon exit."
        ),
    }

    def __init__(self, engagement_repo: Optional[EngagementRepository] = None) -> None:
        self.engagement_repo = engagement_repo or EngagementRepository()

    def is_feedback_or_more_query(self, message: str) -> bool:
        """Determine if an incoming message is a feedback confirmation or elaboration request."""
        clean = message.strip().lower()
        if clean in self.MORE_TERMS:
            return True
        for term in self.NOT_HELPFUL_TERMS:
            if clean == term or clean.startswith(term):
                return True
        for term in self.HELPFUL_TERMS:
            if clean == term:
                return True
        return False

    def handle_incoming_feedback(
        self, member_id: str, message: str
    ) -> Tuple[bool, Optional[str]]:
        """Process inbound feedback or MORE requests linked to latest notification.
        
        Returns (is_handled, response_message).
        """
        clean = message.strip().lower()

        # 1. Handle "MORE" request
        if clean in self.MORE_TERMS:
            latest_notif = self.engagement_repo.get_latest_notification_for_member(member_id)
            if latest_notif and latest_notif.content_id:
                topic = latest_notif.content_id
                example = self.TOPIC_EXAMPLES.get(topic)
                if example:
                    return True, f"{example}\n\nReply with any question if you want to explore further."
                else:
                    return True, "Here is an additional tip: consistency matters more than amount. Even small regular contributions build strong financial momentum over time."
            return True, "Consistency in saving every month is the single most effective way to reach your financial goals. How can I assist with your SACCO account today?"

        # 2. Handle NOT HELPFUL
        for term in self.NOT_HELPFUL_TERMS:
            if clean == term or clean.startswith(term):
                latest_notif = self.engagement_repo.get_latest_notification_for_member(member_id)
                if latest_notif:
                    self.engagement_repo.record_feedback(latest_notif.id, FeedbackRating.NOT_HELPFUL)
                return True, "Thank you for the feedback. We have noted your preference and will adjust future proactive updates to better suit your needs."

        # 3. Handle HELPFUL
        for term in self.HELPFUL_TERMS:
            if clean == term:
                latest_notif = self.engagement_repo.get_latest_notification_for_member(member_id)
                if latest_notif:
                    self.engagement_repo.record_feedback(latest_notif.id, FeedbackRating.HELPFUL)
                return True, "Asante sana for your feedback! We will continue providing practical financial tips aligned with your goals."

        return False, None
