import logging
import re
from time import perf_counter

from app.ai.intent_router import IntentRouter
from app.ai.llm import LLM
from app.ai.rag.pipeline import RAGPipeline
from app.schemas.message import IncomingWhatsAppMessage
from app.services.rag_answer_service import NO_CONTEXT_ANSWER, RAGAnswerService
from app.services.conversation_history import InMemoryConversationHistory
from app.services.postgres_conversation_history import get_runtime_conversation_history
from app.config.settings import settings

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

HUMAN_SUPPORT_PLACEHOLDER = (
    "Your request may need staff assistance. Human support connection is coming later. "
    "Please type HELP to see what is available now."
)
MEMBER_DATA_PLACEHOLDER = (
    "This question requires your personal SACCO information, which I don't have access "
    "to yet. A future version will connect this assistant to authorized member data."
)
GENERAL_ASSISTANCE_PLACEHOLDER = (
    "General assistance is temporarily unavailable. Please contact a SACCO representative."
)

GREETINGS = {"hello", "hi", "hey", "habari", "jambo", "sasa"}
MENU_TRIGGERS = {"menu", "help"}

_rag_answer_service: RAGAnswerService | None = None
conversation_history = get_runtime_conversation_history()


def _get_rag_answer_service() -> RAGAnswerService:
    global _rag_answer_service
    if _rag_answer_service is None:
        _rag_answer_service = RAGAnswerService(RAGPipeline(), LLM())
    return _rag_answer_service


def _format_rag_response(response) -> str:
    if not response.sources:
        return response.answer
    source_lines = "\n".join(f"- {source.title}" for source in response.sources)
    return f"{response.answer}\n\nSource:\n{source_lines}"


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
    message: IncomingWhatsAppMessage,
    intent_router: IntentRouter | None = None,
    rag_answer_service: RAGAnswerService | None = None,
    history_store: InMemoryConversationHistory | None = None,
) -> str:
    body = _normalize(message.body)
    history_store = history_store or conversation_history

    if not body:
        return handle_message(message)

    if _is_greeting(body) or _is_menu(body):
        return WELCOME_MESSAGE

    normalized = body.lower()
    is_question_like = bool(
        "?" in body
        or re.search(
            r"\b(what|why|how|when|where|can|could|do|does|is|are|loan|sacco|share|deposit|interest|member|account|salary|help|need)\b",
            normalized,
        )
    )

    if not is_question_like:
        logger.info("Non-question WhatsApp message treated as staff assistance fallback")
        return HUMAN_SUPPORT_PLACEHOLDER

    total_started = perf_counter()
    router_started = perf_counter()
    result = await (intent_router or IntentRouter()).classify(body)
    logger.info("WhatsApp router latency: %.3fs", perf_counter() - router_started)

    if result.likely_needs_human:
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return HUMAN_SUPPORT_PLACEHOLDER
    if result.needs_member_data:
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return MEMBER_DATA_PLACEHOLDER
    try:
        answer_started = perf_counter()
        conversation_key = message.from_number
        previous_turns = history_store.get(conversation_key)
        answer = await (rag_answer_service or _get_rag_answer_service()).answer(
            query=body,
            sacco_id=settings.DEFAULT_SACCO_ID,
            language=result.language,
            conversation_history=[turn.model_dump() for turn in previous_turns],
        )
        logger.info("WhatsApp answer-service latency: %.3fs", perf_counter() - answer_started)
        response = _format_rag_response(answer)
        history_store.append(conversation_key, "user", body)
        history_store.append(conversation_key, "assistant", response)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return response
    except Exception as exc:
        logger.exception("Grounded WhatsApp answer unavailable: %s", exc)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return GENERAL_ASSISTANCE_PLACEHOLDER
