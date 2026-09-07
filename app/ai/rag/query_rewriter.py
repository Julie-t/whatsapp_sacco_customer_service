"""Conversation-aware query reformulation.

Rewrites follow-up questions using conversation context to make them standalone
and self-contained for retrieval.

Example:
    User:     "What is a development loan?"
    Assistant: ...
    User:     "How much can I get?"

This module converts "How much can I get?" into something like
"How much can I get for a development loan?" using conversation history.
"""

import logging
from typing import Optional

from app.ai.llm import LLM
from app.schemas.message import ConversationTurn

logger = logging.getLogger(__name__)

# Prompt template for query reformulation
QUERY_REWRITE_PROMPT = """
You are a query reformulation assistant for a SACCO financial support system.

Given a conversation history and the user's latest message, your task is to produce
a single, standalone search query that captures the user's intent, using context
from the conversation where necessary.

Rules:
1. If the latest message is already self-contained and clear, return it as-is.
2. If the message depends on previous context, rewrite it to be standalone.
3. Do NOT answer the question or provide additional information.
4. Do NOT invent facts or financial figures.
5. Preserve important financial terminology.
6. Keep the rewritten query concise and clear.
7. Return ONLY the rewritten query, nothing else.

Conversation history:
{history}

Latest user message:
{latest_message}

Standalone search query:
"""


class QueryRewriter:
    """Rewrites queries using conversation history to improve retrieval."""

    def __init__(self, llm: Optional[LLM] = None):
        """Initialize with an LLM instance.

        Args:
            llm: Optional LLM instance. If None, uses default.
        """
        self.llm = llm or LLM()

    async def rewrite(
        self, latest_message: str, conversation_history: list[ConversationTurn] | None = None
    ) -> str:
        """Rewrite a query using conversation context.

        Args:
            latest_message: The user's latest message.
            conversation_history: Optional list of previous conversation turns.

        Returns:
            A standalone, context-aware search query.
        """
        if not conversation_history or len(conversation_history) == 0:
            # No history, return the message as-is
            return latest_message.strip()

        # Check if the message appears to be self-contained
        if self._is_self_contained(latest_message):
            logger.debug("Query appears self-contained, returning as-is")
            return latest_message.strip()

        # Build conversation history string
        history_lines = []
        for turn in conversation_history[-10:]:  # Use last 10 turns to avoid token bloat
            if turn.role == "user":
                history_lines.append(f"User: {turn.content}")
            elif turn.role == "assistant":
                # Summarize long assistant responses
                content = turn.content[:200] + "..." if len(turn.content) > 200 else turn.content
                history_lines.append(f"Assistant: {content}")

        history_text = "\n".join(history_lines)

        # Build prompt
        prompt_text = QUERY_REWRITE_PROMPT.format(
            history=history_text, latest_message=latest_message
        )

        try:
            rewritten = await self.llm.generate(
                [
                    {
                        "role": "user",
                        "content": prompt_text,
                    }
                ]
            )
            rewritten = rewritten.strip()

            if rewritten:
                logger.info(
                    "Query rewritten | original=%r rewritten=%r",
                    latest_message[:80],
                    rewritten[:80],
                )
                return rewritten

            # Fallback if LLM returns empty
            logger.warning("LLM returned empty rewrite, using original message")
            return latest_message.strip()

        except Exception as exc:
            logger.warning("Query rewrite failed: %s. Using original message.", exc)
            return latest_message.strip()

    @staticmethod
    def _is_self_contained(message: str) -> bool:
        """Heuristic check: is the message self-contained or a follow-up?

        This is a simple heuristic that checks for patterns typical of follow-up
        questions that depend on prior context.

        Args:
            message: The message to check.

        Returns:
            True if the message appears self-contained.
        """
        normalized = message.lower().strip()

        # Follow-up patterns that suggest context-dependence
        follow_up_triggers = [
            "how much",
            "how many",
            "what about",
            "does that",
            "can i",
            "can we",
            "should i",
            "tell me more",
            "explain that",
            "what do you mean",
            "why",
            "when",
            "same",
            "too",
            "also",
            "instead",
            "again",
            "once more",
        ]

        for trigger in follow_up_triggers:
            if normalized.startswith(trigger):
                return False

        # Self-contained questions usually have a noun + question word or descriptor
        self_contained_starters = [
            "what is",
            "who is",
            "explain",
            "describe",
            "how do",
            "can you tell me about",
            "i need to know about",
            "i want to learn",
            "what are the",
        ]

        for starter in self_contained_starters:
            if normalized.startswith(starter):
                return True

        # If it's a question with a clear subject, likely self-contained
        if "?" in message and (
            "what" in normalized or "who" in normalized or "when" in normalized
        ):
            return True

        return False
