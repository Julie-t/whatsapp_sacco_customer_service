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
import re
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
2. If the message depends on previous context, rewrite it to be standalone. When the user asks about an attribute (such as interest rates, terms, requirements, or fees) of items or products discussed in the history, explicitly name those specific products (e.g. development loans, emergency loans, school-fees loans) in the query for precise retrieval.
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

        # 1. Follow-up conjunction starters and elliptical phrases
        conjunction_starters = (
            "and ", "and what", "and how", "and where", "and which", "and who",
            "so ", "then ", "but ", "also ", "or ",
            "how about", "what about", "what of",
        )
        if any(normalized.startswith(s) for s in conjunction_starters):
            return False

        # 2. Pronouns or generic context references referring to antecedent topics
        context_pronouns = (
            r"\b(it|its|they|them|their|theirs|that|those|these)\b",
            r"\b(same|another|instead|again|too|more)\b",
        )
        if any(re.search(p, normalized) for p in context_pronouns):
            return False

        # 3. Definite noun phrases without an explicit product/concept qualifier
        # e.g. "what is the interest rate?", "what is the rate?", "what is the fee?"
        definite_attribute_patterns = (
            r"\b(?:what(?:\s+is|\s+are)?|how\s+much(?:\s+is)?)\s+the\s+(?:interest(?:\s+rate)?|rate|rates|fees?|charges?|requirements?|documents?|terms?|limits?|duration|process|procedure|balance)\b",
        )
        if any(re.search(p, normalized) for p in definite_attribute_patterns):
            has_explicit_subject = bool(
                re.search(
                    r"\b(development|emergency|school\s*fees|asset\s*finance|personal|business|salary|fixed\s*deposit|share\s*capital|compound\s*interest|bima|dividend)\b",
                    normalized,
                )
            )
            if not has_explicit_subject:
                return False

        # 3b. Personal member-data inquiries are always self-contained
        member_data_self_contained = (
            r"\b(?:my\s+balance|account\s+balance|savings\s+balance|share\s+balance)\b",
            r"\b(?:my\s+loan|loan\s+balance|how\s+much\s+do\s+i\s+(?:still\s+)?owe|what\s+do\s+i\s+owe)\b",
            r"\b(?:next\s+payment|next\s+instalment|next\s+installment|when\s+do\s+i\s+pay|when\s+is\s+my\s+next)\b",
            r"\b(?:my\s+statement|account\s+statement|my\s+contributions)\b",
        )
        if any(re.search(p, normalized) for p in member_data_self_contained):
            return True

        # 3c. Goal parameter and contribution statements are self-contained
        goal_param_patterns = (
            r"\b(?:saved\s+already|already\s+saved|have\s+about|currently\s+have|already\s+have)\b",
            r"\b(?:put\s+aside|can\s+afford|can\s+manage|can\s+save|save\s+each\s+month)\b",
        )
        if any(re.search(p, normalized) for p in goal_param_patterns):
            return True

        # 3d. Comprehensive financial education and saving strategy queries are self-contained
        education_strategy_patterns = (
            r"\b(?:how\s+should\s+i\s+think\s+about\s+saving|how\s+to\s+think\s+about\s+saving)\b",
            r"\b(?:income\s+changes|irregular\s+income|variable\s+income)\b.*\b(?:sav(?:e|ing|ings)|budget)\b",
            r"\b(?:how\s+(?:should|can|do)\s+i\s+budget|budgeting\s+tips|50/30/20)\b",
        )
        if any(re.search(p, normalized) for p in education_strategy_patterns):
            return True

        # 4. Standard follow-up starters that suggest context-dependence
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

        # 5. Clear self-contained starters
        self_contained_starters = [
            "what is compound interest",
            "what are the loan requirements",
            "what is a development loan",
            "what is an emergency loan",
            "who is the sacco manager",
            "explain how savings work",
            "how do i join",
            "how do sacco loans work",
            "can you tell me about",
            "i need to know about",
            "i want to learn",
        ]

        for starter in self_contained_starters:
            if normalized.startswith(starter):
                return True

        # Check self-contained patterns: starter + substantial words
        general_self_contained_starters = [
            "what is ",
            "what are ",
            "who is ",
            "explain ",
            "describe ",
            "how do ",
        ]
        if any(normalized.startswith(s) for s in general_self_contained_starters):
            words = normalized.split()
            if len(words) >= 4:
                return True

        return False
