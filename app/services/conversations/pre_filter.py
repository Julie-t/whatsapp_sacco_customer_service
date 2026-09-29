"""Zero-LLM deterministic pre-filter for high-confidence fast paths.

Handles messages that can be fully resolved without any routing or LLM call:
greetings, menus, OTP verification, fraud/security, media, feedback/MORE,
and non-conversational fallback.

This module absorbs the former sync ``handle_message()`` function.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.config.settings import settings
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.response import (
    ASSISTANT_CAPABILITY_RESPONSE,
    CAPABILITY_MENU,
    FALLBACK_MESSAGE,
    GREETING_MESSAGE,
    GREETINGS,
    HUMAN_SUPPORT_PLACEHOLDER,
    MEDIA_NOT_SUPPORTED,
    MENU_RESPONSES,
    MENU_TRIGGERS,
    WELCOME_MESSAGE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class PreFilterResult:
    """Result of the pre-filter stage.

    If ``handled`` is True the orchestrator should return ``response``
    immediately without invoking routing or dispatch.
    """

    handled: bool
    response: str | None = None


# ---------------------------------------------------------------------------
# Helper checks (extracted from conversation_service.py)
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    return text.strip()


def _is_greeting(text: str) -> bool:
    normalized = _normalize(text).lower().strip("!?. ,;:\t\n\r")
    return normalized in GREETINGS


def _is_menu(text: str) -> bool:
    normalized = _normalize(text).lower().strip("!?. ,;:\t\n\r")
    return normalized in MENU_TRIGGERS


def _is_assistant_capability_query(text: str) -> bool:
    """Detect questions asking about WhatsApp assistant capabilities or whether it can help on WhatsApp."""
    lower = text.lower()
    patterns = (
        r"\b(?:can|could|do|will)\s+you\s+(?:help|assist)\b.*\b(?:whatsapp|here|online)\b",
        r"\b(?:help|assist)\s+me\s+(?:here|on\s+whatsapp)\b",
        r"\bwhat\s+can\s+you\s+(?:do|help(?:\s+with)?)\b",
        r"\bhow\s+can\s+you\s+help\b",
        r"\bhow\s+does\s+this\s+(?:work|service\s+work|bot\s+work)\b",
        r"\bwhat\s+(?:services|topics|things)\s+do\s+you\s+(?:provide|offer|handle)\b",
    )
    return any(re.search(p, lower) for p in patterns)


def _is_conversational_or_intent_like(body: str) -> bool:
    """Detect whether a message looks like a substantive conversational query.

    Messages that fail this check are treated as staff-assistance fallback.
    """
    normalized = body.lower()
    return bool(
        "?" in body
        or re.search(
            r"\b("
            r"what|why|how|when|where|who|which|can|could|do|does|did|is|are|am|will|would|should|"
            r"want|planning|plan|looking|aim|raise|save|saving|savings|invest|investing|investment|"
            r"deposit|deposits|withdraw|contribute|contribution|borrow|repay|repayment|pay|check|status|progress|"
            r"loan|loans|sacco|share|shares|stock|stocks|dividend|dividends|interest|member|membership|"
            r"account|accounts|salary|money|cash|fund|funds|capital|fee|fees|rate|rates|"
            r"goal|goals|target|targets|shop|business|biashara|duka|school|university|college|education|masomo|shule|"
            r"emergency|dharura|retire|retirement|pension|ustaafu|land|plot|shamba|house|nyumba|car|gari|expand|"
            r"nataka|nahitaji|ningependa|kujiunga|kufungua|kuweka|akiba|changa|nisaidie|nipatie|mkopo|mikopo|hisa|riba|"
            r"year|years|yr|yrs|month|months|mo|mos|week|weeks|mwaka|miaka|mwezi|miezi|verify|otp|code|"
            r"ksh|kes|shilling|shillings|shilingi"
            r")\b",
            normalized,
            re.IGNORECASE,
        )
        or bool(re.search(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", normalized))
    )


# ---------------------------------------------------------------------------
# PreFilter
# ---------------------------------------------------------------------------


class PreFilter:
    """Zero-LLM deterministic checks run before any routing.

    Priority order mirrors the original ``handle_message_async()`` top section.
    """

    def __init__(
        self,
        feedback_service: Any | None = None,
        auth_service: Any | None = None,
        member_service: Any | None = None,
    ):
        self._feedback_service = feedback_service
        self._auth_service = auth_service
        self._member_service = member_service

    def check(self, message: IncomingWhatsAppMessage) -> PreFilterResult:
        """Run all deterministic checks in priority order.

        Returns a ``PreFilterResult``.  If ``handled`` is True the
        orchestrator returns the response immediately.
        """
        body = _normalize(message.body)

        # 1. Empty body / media
        if not body:
            if message.num_media and message.num_media != "0":
                return PreFilterResult(handled=True, response=MEDIA_NOT_SUPPORTED)
            return PreFilterResult(handled=True, response=FALLBACK_MESSAGE)

        # 2. Greetings
        if _is_greeting(body):
            return PreFilterResult(handled=True, response=GREETING_MESSAGE)

        # 3. Menu / HELP
        if _is_menu(body):
            return PreFilterResult(handled=True, response=CAPABILITY_MENU)

        # 4. Assistant capability query
        if _is_assistant_capability_query(body):
            return PreFilterResult(handled=True, response=ASSISTANT_CAPABILITY_RESPONSE)

        # 5. Menu number responses ("1", "2", "3", "4")
        menu_response = MENU_RESPONSES.get(body.strip())
        if menu_response:
            return PreFilterResult(handled=True, response=menu_response)

        # 6. OTP verification
        otp_match = re.match(r"^(?:VERIFY\s+)?(\d{6})$", body.strip(), re.IGNORECASE)
        if otp_match:
            from app.services.members.member_auth_service import MemberAuthService

            code = otp_match.group(1)
            a_svc = self._auth_service or MemberAuthService()
            _success, _sess, auth_msg = a_svc.verify_otp(
                message.from_number, code, sacco_id=settings.DEFAULT_SACCO_ID
            )
            return PreFilterResult(handled=True, response=auth_msg)

        # 7. Feedback & MORE for proactive notifications
        if self._feedback_service is not None:
            feedback_svc = self._feedback_service
        else:
            from app.services.proactive.member_feedback_service import MemberFeedbackService

            feedback_svc = MemberFeedbackService()

        if feedback_svc.is_feedback_or_more_query(body):
            if self._member_service is not None:
                m_svc = self._member_service
            else:
                from app.services.members.member_service import MemberDataService

                m_svc = MemberDataService()
            profile = m_svc.resolve_member(message.from_number)
            member_id = profile.id if profile else ""
            handled, reply = feedback_svc.handle_incoming_feedback(member_id, body)
            if handled and reply:
                return PreFilterResult(handled=True, response=reply)

        # 8. Fraud / security keywords — urgent escalation
        normalized = body.lower()
        if re.search(
            r"\b(unrecognized|didn't authorize|did not authorize|fraud|stolen|scam|wrong deduction|reversed? money)\b",
            normalized,
        ):
            try:
                from app.services.admin.admin_escalation_service import AdminEscalationService
                from app.services.members.member_service import MemberDataService

                m_svc = self._member_service or MemberDataService()
                prof = m_svc.resolve_member(message.from_number)
                esc = AdminEscalationService().record_from_conversation(
                    conversation_key=message.from_number,
                    query=body,
                    member_id=prof.id if prof else None,
                    sacco_id=settings.DEFAULT_SACCO_ID,
                    category="fraud",
                    priority="urgent",
                )
                return PreFilterResult(
                    handled=True,
                    response=(
                        f"Your report regarding an unrecognized transaction or security dispute has been escalated with urgent priority (Ticket #{esc.id}). "
                        "A SACCO security and member accounts officer will contact you immediately."
                    ),
                )
            except Exception as err:
                logger.warning("Failed to record fraud escalation: %s", err)
                return PreFilterResult(handled=True, response=HUMAN_SUPPORT_PLACEHOLDER)

        # 9. Non-conversational message fallback
        if not _is_conversational_or_intent_like(body):
            logger.info("Non-intent WhatsApp message treated as staff assistance fallback")
            return PreFilterResult(handled=True, response=HUMAN_SUPPORT_PLACEHOLDER)

        # Message requires full routing
        return PreFilterResult(handled=False)


# ---------------------------------------------------------------------------
# Sync fallback handler (absorbed from conversation_service.py)
# ---------------------------------------------------------------------------
def handle_message(message: IncomingWhatsAppMessage) -> str:
    """Synchronous fallback handler — resolves only deterministic fast paths.

    Preserves the original sync contract: empty body/media, greetings/menu,
    menu options, or fallback.
    """
    body = _normalize(message.body)

    if not body:
        if message.num_media and message.num_media != "0":
            return MEDIA_NOT_SUPPORTED
        return FALLBACK_MESSAGE

    if _is_greeting(body):
        return GREETING_MESSAGE

    if _is_menu(body):
        return CAPABILITY_MENU

    menu_response = MENU_RESPONSES.get(body.strip())
    if menu_response:
        return menu_response

    return FALLBACK_MESSAGE

