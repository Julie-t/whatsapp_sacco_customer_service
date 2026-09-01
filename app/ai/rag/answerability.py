"""Answerability detection and retrieval confidence evaluation.

Determines whether retrieved evidence contains sufficient information to
answer a question. This is different from relevance: a document can be
relevant but not contain enough specific information to answer the query.

Example:
    Query: "What is the withdrawal fee?"
    Retrieved: "Withdrawal Procedures" document
    Verdict: Not answerable (no fee information present)
"""

import logging
from pydantic import BaseModel, Field

from app.ai.rag.models import RAGResult

logger = logging.getLogger(__name__)


class AnswerabilityDecision(BaseModel):
    """Decision about whether a question can be answered with retrieved evidence."""

    answerable: bool = Field(description="Whether the evidence can answer the question")
    confidence: float = Field(
        description="Confidence score 0.0-1.0", ge=0.0, le=1.0
    )
    reason: str = Field(description="Human-readable explanation of the decision")
    min_score: float | None = Field(
        default=None,
        description="Minimum retrieval score among results used for this decision",
    )


class AnswerabilityChecker:
    """Checks if retrieved evidence can answer a question."""

    def __init__(
        self,
        min_retrieval_score: float = 0.5,
        min_result_length: int = 30,
    ):
        """Initialize answerability checker.

        Args:
            min_retrieval_score: Minimum retrieval similarity score (0.0-1.0).
                                 Results below this are considered insufficient.
            min_result_length: Minimum character length for retrieved content.
                               Very short results are often insufficient.
        """
        self.min_retrieval_score = min_retrieval_score
        self.min_result_length = min_result_length

    def check(
        self,
        query: str,
        results: list[RAGResult],
    ) -> AnswerabilityDecision:
        """Check if retrieved results can answer the query.

        Uses deterministic checks based on:
        - Retrieval score (higher is better)
        - Content length (longer is often better for factual queries)
        - Result count (at least one result is necessary)
        - Query specificity (very vague queries are harder to answer)

        Args:
            query: The original user query.
            results: Retrieved evidence.

        Returns:
            AnswerabilityDecision with verdict and confidence.
        """
        if not results:
            logger.debug("No results retrieved - not answerable")
            return AnswerabilityDecision(
                answerable=False,
                confidence=0.0,
                reason="No relevant evidence was retrieved.",
                min_score=None,
            )

        # Check minimum score threshold
        min_score = min(r.score for r in results)
        if min_score < self.min_retrieval_score:
            logger.debug(
                "Minimum score %.3f below threshold %.3f - not answerable",
                min_score,
                self.min_retrieval_score,
            )
            return AnswerabilityDecision(
                answerable=False,
                confidence=1.0 - (min_score / self.min_retrieval_score),
                reason=f"Retrieved evidence is not sufficiently relevant (score: {min_score:.2f}). "
                f"Minimum confidence threshold is {self.min_retrieval_score:.2f}.",
                min_score=min_score,
            )

        # Check if top result has meaningful content
        top_result = results[0]
        if len(top_result.content) < self.min_result_length:
            logger.debug(
                "Top result too short (%d chars) - not answerable",
                len(top_result.content),
            )
            return AnswerabilityDecision(
                answerable=False,
                confidence=0.6,
                reason=f"Retrieved evidence is too brief to provide a complete answer. "
                f"Content length: {len(top_result.content)} characters.",
                min_score=min_score,
            )

        # A simple "What is X?" definition question should remain answerable when
        # the retrieved content actually explains the concept. Only detail-heavy
        # questions like fees, requirements, deadlines, etc. should trigger the
        # stricter specificity gate.
        specificity_terms = [
            "document", "documents", "fee", "fees", "rate",
            "rates", "requirement", "requirements", "deadline",
            "amount", "cost", "charge", "charges",
        ]
        query_lower = query.lower()
        has_specific_query = any(term in query_lower for term in specificity_terms)
        is_generic_definition = query_lower.startswith("what is ") and not any(
            term in query_lower for term in specificity_terms
        )
        has_specific_query = has_specific_query and not is_generic_definition

        if has_specific_query:
            has_specific_content = any(
                any(term in r.content.lower() for term in specificity_terms)
                for r in results[:3]
            )
            if not has_specific_content:
                logger.debug("Query is specific but results are generic - not answerable")
                return AnswerabilityDecision(
                    answerable=False,
                    confidence=min(0.75, 0.45 + (min_score * 0.35)),
                    reason="Retrieved evidence may not contain all specific details needed for this question. "
                    "The response should not fabricate missing information.",
                    min_score=min_score,
                )

        # Default: answerable with confidence based on retrieval score
        # Map score range: 0.5-1.0 scales to 0.75-1.0 confidence
        confidence = 0.75 + (min(min_score, 1.0) * 0.25)
        confidence = min(confidence, 1.0)

        logger.debug(
            "Results appear answerable | score=%.3f confidence=%.3f",
            min_score,
            confidence,
        )
        return AnswerabilityDecision(
            answerable=True,
            confidence=confidence,
            reason=f"Retrieved evidence appears sufficient to answer the question "
            f"(confidence: {confidence:.2f}).",
            min_score=min_score,
        )
