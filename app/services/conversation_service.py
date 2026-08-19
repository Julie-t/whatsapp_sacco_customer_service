import logging

from app.ai.intent_router import IntentRouter
from app.schemas.intent import Intent, IntentResult
from app.schemas.message import IncomingWhatsAppMessage

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "👋🏾 Karibu! I'm your SACCO financial companion.\n\n"
    "I can help you with:\n\n"
    "1️⃣ Financial education\n"
    "2️⃣ SACCO information\n"
    "3️⃣ My financial goals\n"
    "4️⃣ Talk to a SACCO representative\n\n"
    "For now, this is an early MVP. You can type HELP at any time."
)

FALLBACK_MESSAGE = (
    "Thank you for your message. My AI assistant capabilities are being introduced soon. "
    "For now, you can type HELP to see what I can do."
)

MEDIA_NOT_SUPPORTED = (
    "I can't process media messages yet. Please type HELP to see how I can assist you."
)

FEATURE_NOT_AVAILABLE = {
    Intent.FINANCIAL_EDUCATION: "Financial education features are coming later. Please type HELP to see what is available now.",
    Intent.SACCO_INFORMATION: "SACCO information features are coming later. Please type HELP to see what is available now.",
    Intent.GOAL_MANAGEMENT: "Goal management features are coming later. Please type HELP to see what is available now.",
    Intent.HUMAN_SUPPORT: "Human support connection is coming later. Please type HELP to see what is available now.",
}

GREETINGS = {"hello", "hi", "hey", "habari", "jambo", "sasa"}
MENU_TRIGGERS = {"menu", "help"}


def _normalize(text: str) -> str:
    return text.strip()


def _is_greeting(text: str) -> bool:
    normalized = _normalize(text).lower()
    return normalized in GREETINGS


def _is_menu(text: str) -> bool:
    normalized = _normalize(text).lower()
    return normalized in MENU_TRIGGERS


def handle_message(message: IncomingWhatsAppMessage) -> str:
    body = _normalize(message.body)

    if not body:
        if message.num_media and message.num_media != "0":
            return MEDIA_NOT_SUPPORTED
        return FALLBACK_MESSAGE

    if _is_greeting(body) or _is_menu(body):
        return WELCOME_MESSAGE

    return FALLBACK_MESSAGE


async def handle_message_async(
    message: IncomingWhatsAppMessage, intent_router: IntentRouter | None = None
) -> str:
    body = _normalize(message.body)

    if not body:
        return handle_message(message)

    if _is_greeting(body) or _is_menu(body):
        return WELCOME_MESSAGE

    result = await (intent_router or IntentRouter()).classify(body)
    if result.intent == Intent.GREETING:
        return WELCOME_MESSAGE
    return FEATURE_NOT_AVAILABLE.get(result.intent, FALLBACK_MESSAGE)
