"""Conversation orchestration — the single entry point for WhatsApp messages.

This module is intentionally thin.  It coordinates:
1. Pre-filter  (deterministic fast paths — greetings, menus, OTP, fraud)
2. Context assembly  (query rewriting, member resolution, goal state)
3. Routing  (IntentRouter — classify intent)
4. Dispatch  (Dispatcher → WorkflowHandlers → domain services)
5. Conversation persistence

All workflow logic lives in dedicated modules; this file only wires them
together.
"""

import logging
from time import perf_counter
from typing import Any

from app.ai.candidate_filter import CandidateFilter
from app.ai.intent_router import IntentRouter, classify_deterministic
from app.ai.rag.query_rewriter import QueryRewriter
from app.schemas.intent import RequestTriageResult, RoutingDecision
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_context import (
    ConversationContext,
    ConversationContextBuilder,
)
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.services.conversations.dispatcher import Dispatcher
from app.services.conversations.postgres_conversation_history import (
    get_runtime_conversation_history,
)
from app.services.conversations.service_container import ServiceContainer
from app.services.conversations.pre_filter import PreFilter, handle_message
from app.services.conversations.workflow_handlers import (
    WorkflowHandlers,
    _handle_member_query,
)

# Re-export response constants so existing imports continue to work.
# e.g. ``from app.services.conversations.conversation_service import HUMAN_SUPPORT_PLACEHOLDER``
from app.services.conversations.response import (  # noqa: F401
    ASSISTANT_CAPABILITY_RESPONSE,
    CAPABILITY_MENU,
    FALLBACK_MESSAGE,
    GENERAL_ASSISTANCE_PLACEHOLDER,
    GREETING_MESSAGE,
    HUMAN_SUPPORT_PLACEHOLDER,
    MEDIA_NOT_SUPPORTED,
    MEMBER_DATA_PLACEHOLDER,
    MEMBER_NO_ACCOUNTS,
    MEMBER_NOT_RECOGNIZED,
    WELCOME_MESSAGE,
    clean_ai_artifacts,
    format_rag_response,
)

logger = logging.getLogger(__name__)

# Process-level conversation history instance.
conversation_history = get_runtime_conversation_history()

# ---------------------------------------------------------------------------
# Backward-compat aliases so old internal references still resolve.
# ---------------------------------------------------------------------------
_clean_ai_artifacts = clean_ai_artifacts
_format_rag_response = format_rag_response


# ---------------------------------------------------------------------------
# Singleton service accessors (kept as module-level for startup warmup in
# main.py — the ServiceContainer replaces them at runtime)
# ---------------------------------------------------------------------------
def _get_rag_answer_service():
    return _default_container.rag_answer_service


def _get_query_rewriter():
    return _default_container.query_rewriter


def _get_education_service():
    return _default_container.education_service


_default_container = ServiceContainer()


# handle_message is re-exported from pre_filter above for backward compatibility.


# ---------------------------------------------------------------------------
# Main async entry point
# ---------------------------------------------------------------------------
async def handle_message_async(
    message: IncomingWhatsAppMessage,
    intent_router: IntentRouter | None = None,
    rag_answer_service: Any | None = None,
    history_store: InMemoryConversationHistory | None = None,
    member_service: Any | None = None,
    goal_service: Any | None = None,
    goal_extractor: Any | None = None,
    education_service: Any | None = None,
    feedback_service: Any | None = None,
    auth_service: Any | None = None,
    query_rewriter: QueryRewriter | None = None,
) -> str:
    """Process an incoming WhatsApp message and return a response.

    Signature preserved for backward compatibility with all callers
    (webhook, tests, evaluations).
    """
    total_started = perf_counter()
    history = history_store or conversation_history

    # Build a ServiceContainer from the injected overrides (tests pass fakes).
    services = ServiceContainer(
        rag_answer_service=rag_answer_service,
        query_rewriter=query_rewriter,
        member_service=member_service,
        goal_service=goal_service,
        goal_extractor=goal_extractor,
        education_service=education_service,
        auth_service=auth_service,
        feedback_service=feedback_service,
    )

    # ── 1. Pre-filter ─────────────────────────────────────────────────
    pre_filter = PreFilter(
        feedback_service=services._feedback_service,
        auth_service=services._auth_service,
        member_service=services._member_service,
    )
    pre_result = pre_filter.check(message)
    if pre_result.handled:
        return pre_result.response

    # ── 2. Build conversation context ──────────────────────────────────
    ctx_builder = ConversationContextBuilder(
        history_store=history,
        query_rewriter=services.query_rewriter if history.get(message.from_number) else None,
        member_service=services.member_service,
        goal_service=services.goal_service,
        auth_service=services._auth_service,
        state_store=services.state_store,
    )
    context = await ctx_builder.build(message)

    # ── 3. Deterministic fast-path routing ─────────────────────────────
    det_result = classify_deterministic(context.raw_message)
    if det_result is not None:
        if det_result.likely_needs_human:
            handlers = WorkflowHandlers(services)
            response = await handlers.handle_escalation(context, message)
            logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
            return response

        if det_result.needs_member_data:
            handlers = WorkflowHandlers(services)
            response = await handlers.handle_member_data(context, message)
            history.append(context.conversation_key, "user", message.body)
            history.append(context.conversation_key, "assistant", response)
            logger.info("Deterministic member-data lookup latency: %.3fs", perf_counter() - total_started)
            return response

    # ── 4. Candidate filtering & Decision Router ──────────────────────
    candidate_filter = CandidateFilter()
    candidates = candidate_filter.select_candidates(context)

    router = intent_router or IntentRouter()
    try:
        triage = await router.classify(
            context.effective_query,
            context=context.context_summary,
            candidate_operations=candidates,
        )
    except TypeError:
        try:
            triage = await router.classify(
                context.effective_query,
                context=context.context_summary,
            )
        except TypeError:
            triage = await router.classify(context.effective_query)
    logger.info("WhatsApp router latency: %.3fs", perf_counter() - total_started)

    # ── 5. Dispatch to workflow handler ────────────────────────────────
    handlers = WorkflowHandlers(services)
    dispatcher = Dispatcher(handlers)
    response = await dispatcher.dispatch(triage, context, message)

    # ── 6. Persist conversation ────────────────────────────────────────
    history.append(context.conversation_key, "user", message.body)
    history.append(context.conversation_key, "assistant", response)
    logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)

    return response
