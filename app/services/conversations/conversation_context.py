"""Structured conversation context assembly.

Builds a ``ConversationContext`` once per incoming message, replacing the
ad-hoc context construction that was scattered across
``handle_message_async()``.  The context is passed to both the router and
the dispatcher so that member resolution and query rewriting happen exactly
once per request.
"""

import logging
import re
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.message import ConversationTurn, IncomingWhatsAppMessage

logger = logging.getLogger(__name__)


class ConversationContext(BaseModel):
    """Structured context assembled once per request."""

    raw_message: str
    effective_query: str  # after query rewriting (same as raw if no rewriting needed)
    conversation_key: str  # phone number used as history key
    language: str  # detected language hint ("en" / "sw" / "mixed")
    previous_turns: list[ConversationTurn]
    context_summary: str | None  # formatted last-N-turns string for router prompt
    member_profile: Any | None  # MemberProfile or None
    has_active_goal: bool
    active_goal: Any | None  # Goal model or None
    has_auth_session: bool

    model_config = {"arbitrary_types_allowed": True}


class ConversationContextBuilder:
    """Assembles ``ConversationContext`` from the message and stored state.

    Replaces the context-building code previously spread across
    ``handle_message_async()`` lines 670-748.
    """

    def __init__(
        self,
        history_store: Any,
        query_rewriter: Any | None = None,
        member_service: Any | None = None,
        goal_service: Any | None = None,
        auth_service: Any | None = None,
        state_store: Any | None = None,
    ):
        self._history_store = history_store
        self._query_rewriter = query_rewriter
        self._member_service = member_service
        self._goal_service = goal_service
        self._auth_service = auth_service
        self._state_store = state_store

    async def build(self, message: IncomingWhatsAppMessage) -> ConversationContext:
        """Build the full context for a single message.

        This is called once per request.  The resulting context is
        shared with the router and dispatcher to avoid duplicate lookups.
        """
        body = message.body.strip()
        conversation_key = message.from_number

        # --- Conversation history ---
        previous_turns = self._history_store.get(conversation_key)
        context_summary: str | None = None
        if previous_turns:
            context_summary = "\n".join(
                [f"{t.role}: {t.content}" for t in previous_turns[-4:]]
            )

        # --- Language detection (lightweight heuristic) ---
        sw_words = {
            "habari", "mambo", "jambo", "sasa", "vipi", "akiba", "mkopo", "mikopo",
            "deni", "salio", "pesa", "shilingi", "nisaidie", "asante", "karibu",
        }
        words = re.sub(r"[^\w\s]", " ", body.lower()).split()
        language = "sw" if any(w in words for w in sw_words) else "en"

        # --- Query rewriting ---
        effective_query = body
        if previous_turns and self._query_rewriter is not None:
            try:
                effective_query = await self._query_rewriter.rewrite(
                    body, conversation_history=previous_turns
                )
                if effective_query != body:
                    logger.info(
                        "Contextual query rewritten: %r -> %r", body, effective_query
                    )
            except Exception as rw_err:
                logger.warning(
                    "Query rewriting failed; falling back to original query: %s", rw_err
                )
                effective_query = body

        # --- Member resolution ---
        member_profile = None
        if self._member_service is not None:
            member_profile = self._member_service.resolve_member(message.from_number)

        # --- Active goal ---
        has_active_goal = False
        active_goal = None
        if member_profile is not None and self._goal_service is not None:
            if self._state_store is not None:
                st = self._state_store.get(conversation_key)
                if st and st.active_goal_id:
                    active_goal = self._goal_service.get_goal(st.active_goal_id)
            if active_goal is None:
                active_goal = self._goal_service.get_active_goal(member_profile.id)
                if active_goal and self._state_store is not None:
                    self._state_store.update(conversation_key, active_goal_id=active_goal.id)
            has_active_goal = active_goal is not None

        # --- Auth session ---
        has_auth_session = False
        if self._auth_service is not None:
            try:
                has_auth_session = self._auth_service.is_session_active(
                    message.from_number, sacco_id=None
                )
            except Exception:
                pass

        return ConversationContext(
            raw_message=body,
            effective_query=effective_query,
            conversation_key=conversation_key,
            language=language,
            previous_turns=previous_turns,
            context_summary=context_summary,
            member_profile=member_profile,
            has_active_goal=has_active_goal,
            active_goal=active_goal,
            has_auth_session=has_auth_session,
        )
