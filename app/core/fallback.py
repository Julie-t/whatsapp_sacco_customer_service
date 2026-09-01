"""Intelligent fallback taxonomy for RAG system.

Defines explicit internal categories for system fallbacks instead of a single
generic fallback. These are system-outcome categories, not user-question taxonomy.

Categories:
- clarification: Question is ambiguous, needs user to be more specific
- knowledge_gap: Question is clear but knowledge base lacks evidence
- guardrail: Request is outside what the assistant should answer
- human_escalation: Request requires human staff intervention
- provider_failure: External service (NVIDIA, etc) failed
"""

import logging
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FallbackCategory(str, Enum):
    """Internal taxonomy of fallback scenarios."""

    CLARIFICATION = "clarification"
    KNOWLEDGE_GAP = "knowledge_gap"
    GUARDRAIL = "guardrail"
    HUMAN_ESCALATION = "human_escalation"
    PROVIDER_FAILURE = "provider_failure"


class FallbackResponse(BaseModel):
    """Response when a fallback is triggered."""

    category: FallbackCategory = Field(description="Internal fallback reason")
    user_message: str = Field(description="Message to show the user")
    internal_reason: str = Field(description="Internal explanation for logging")
    should_escalate: bool = Field(
        default=False,
        description="Whether this should be escalated to human staff",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context (e.g., detected intent, confidence scores)",
    )


class FallbackHandler:
    """Generates appropriate fallback responses."""

    @staticmethod
    def clarification(
        query: str,
        detected_topics: list[str] | None = None,
        metadata: dict | None = None,
    ) -> FallbackResponse:
        """Generate a clarification response.

        Used when the question is ambiguous and needs more specificity.

        Args:
            query: The ambiguous user query.
            detected_topics: Optional list of possible topics detected.
            metadata: Optional metadata to include.

        Returns:
            FallbackResponse with clarification message.
        """
        topics_hint = ""
        if detected_topics:
            topic_str = ", ".join(detected_topics[:3])
            topics_hint = (
                f"\n\nWere you asking about: {topic_str}? "
                "Feel free to be more specific."
            )

        user_message = (
            "I'd like to help, but your question could mean a few things. "
            "Could you give me more details?"
            + topics_hint
        )

        logger.info(
            "Clarification fallback | query=%r topics=%r",
            query[:80],
            detected_topics,
        )

        return FallbackResponse(
            category=FallbackCategory.CLARIFICATION,
            user_message=user_message,
            internal_reason=f"Ambiguous query: {query[:100]}. Possible topics: {detected_topics}",
            should_escalate=False,
            metadata=metadata or {"query": query, "topics": detected_topics},
        )

    @staticmethod
    def knowledge_gap(
        query: str,
        suggestion: str | None = None,
        metadata: dict | None = None,
    ) -> FallbackResponse:
        """Generate a knowledge gap response.

        Used when the question is clear but the knowledge base lacks evidence.

        Args:
            query: The clear user query.
            suggestion: Optional suggestion for what the member can do.
            metadata: Optional metadata to include.

        Returns:
            FallbackResponse with knowledge gap message.
        """
        suggestion_text = f"\n\n{suggestion}" if suggestion else ""
        user_message = (
            "I couldn't find that information in the SACCO knowledge I have access to. "
            "Would you like me to connect you with a SACCO representative who can help?"
            + suggestion_text
        )

        logger.info(
            "Knowledge gap fallback | query=%r suggestion=%r",
            query[:80],
            suggestion,
        )

        return FallbackResponse(
            category=FallbackCategory.KNOWLEDGE_GAP,
            user_message=user_message,
            internal_reason=f"Knowledge gap: {query[:100]}",
            should_escalate=True,
            metadata=metadata or {"query": query, "suggestion": suggestion},
        )

    @staticmethod
    def guardrail(
        query: str,
        reason: str,
        metadata: dict | None = None,
    ) -> FallbackResponse:
        """Generate a guardrail response.

        Used when the request is outside what the assistant should answer
        (e.g., directive investment advice, unsupported regulated content).

        Args:
            query: The out-of-scope query.
            reason: Why this is outside scope.
            metadata: Optional metadata to include.

        Returns:
            FallbackResponse with guardrail message.
        """
        user_message = (
            "I'm designed to provide information and education about SACCO services. "
            "For that particular request, I'd recommend speaking with a SACCO representative. "
            "They can give you personalized guidance."
        )

        logger.info(
            "Guardrail fallback | query=%r reason=%r",
            query[:80],
            reason,
        )

        return FallbackResponse(
            category=FallbackCategory.GUARDRAIL,
            user_message=user_message,
            internal_reason=f"Out-of-scope request: {reason}. Query: {query[:100]}",
            should_escalate=True,
            metadata=metadata or {"query": query, "reason": reason},
        )

    @staticmethod
    def human_escalation(
        query: str,
        reason: str,
        metadata: dict | None = None,
    ) -> FallbackResponse:
        """Generate a human escalation response.

        Used for fraud, disputes, complaints, account changes, explicit human
        requests, or low-confidence sensitive cases.

        Args:
            query: The user query that needs escalation.
            reason: Why this needs human intervention.
            metadata: Optional metadata to include.

        Returns:
            FallbackResponse with escalation message.
        """
        user_message = (
            "Thank you for reaching out. I'm connecting you with a SACCO representative "
            "who can assist you with this. Please hold."
        )

        logger.info(
            "Human escalation fallback | query=%r reason=%r",
            query[:80],
            reason,
        )

        return FallbackResponse(
            category=FallbackCategory.HUMAN_ESCALATION,
            user_message=user_message,
            internal_reason=f"Requires human intervention: {reason}. Query: {query[:100]}",
            should_escalate=True,
            metadata=metadata or {"query": query, "reason": reason},
        )

    @staticmethod
    def provider_failure(
        service_name: str,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> FallbackResponse:
        """Generate a provider failure response.

        Used when NVIDIA or another required service fails.
        Does not expose technical details to the member.

        Args:
            service_name: Name of the service that failed (e.g., "NVIDIA LLM").
            error: Optional technical error details (for logging, not user-facing).
            metadata: Optional metadata to include.

        Returns:
            FallbackResponse with service failure message.
        """
        user_message = (
            "I'm temporarily unable to process your request. "
            "Please try again in a moment, or contact a SACCO representative for immediate assistance."
        )

        logger.warning(
            "Provider failure fallback | service=%r error=%r",
            service_name,
            error,
        )

        return FallbackResponse(
            category=FallbackCategory.PROVIDER_FAILURE,
            user_message=user_message,
            internal_reason=f"Service failure: {service_name}. Error: {error}",
            should_escalate=True,
            metadata=metadata or {"service": service_name, "error": error},
        )
