"""Answerability detection based on retrieval confidence and evidence coverage."""

import logging

from pydantic import BaseModel, Field

from app.ai.rag.models import RAGResult

logger = logging.getLogger(__name__)


class AnswerabilityDecision(BaseModel):
    """Decision about whether retrieved evidence can answer a question."""

    answerable: bool = Field(description="Whether the evidence can answer the question")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(description="Human-readable explanation of the decision")
    min_score: float | None = Field(default=None, description="Minimum retrieval score among results")


class AnswerabilityChecker:
    """Check whether the strongest retrieved evidence answers the query."""

    def __init__(self, min_retrieval_score: float = 0.5, min_result_length: int = 30):
        self.min_retrieval_score = min_retrieval_score
        self.min_result_length = min_result_length

    def check(self, query: str, results: list[RAGResult]) -> AnswerabilityDecision:
        if not results:
            logger.debug("No results retrieved - not answerable")
            return AnswerabilityDecision(
                answerable=False,
                confidence=0.0,
                reason="No relevant evidence was retrieved.",
                min_score=None,
            )

        top_score = results[0].score
        min_score = min(result.score for result in results)
        if min_score < self.min_retrieval_score:
            return AnswerabilityDecision(
                answerable=False,
                confidence=max(0.0, 1.0 - (min_score / self.min_retrieval_score)),
                reason=(
                    f"Retrieved evidence is not sufficiently relevant (score: {min_score:.2f}). "
                    f"Minimum confidence threshold is {self.min_retrieval_score:.2f}."
                ),
                min_score=min_score,
            )

        top_result = results[0]
        if len(top_result.content) < self.min_result_length:
            return AnswerabilityDecision(
                answerable=False,
                confidence=0.6,
                reason=(
                    "Retrieved evidence is too brief to provide a complete answer. "
                    f"Content length: {len(top_result.content)} characters."
                ),
                min_score=min_score,
            )

        query_lower = query.lower()
        required_terms = _required_evidence_terms(query_lower)
        if query_lower.startswith("what is ") and not _has_detail_request(query_lower):
            required_terms = set()
        evidence_text = " ".join(result.content.lower() for result in results[:3])
        if required_terms and not any(term in evidence_text for term in required_terms):
            return AnswerabilityDecision(
                answerable=False,
                confidence=min(0.75, 0.45 + (top_score * 0.35)),
                reason=(
                    "Retrieved evidence may not contain all specific details needed for this question. "
                    "The response should not fabricate missing information."
                ),
                min_score=min_score,
            )

        confidence = min(1.0, 0.75 + (min(top_score, 1.0) * 0.25))
        return AnswerabilityDecision(
            answerable=True,
            confidence=confidence,
            reason=f"Retrieved evidence appears sufficient to answer the question (confidence: {confidence:.2f}).",
            min_score=min_score,
        )


def _required_evidence_terms(query: str) -> set[str]:
    groups = (
        (("fee", "fees", "processing fee", "charge", "charges"), {"fee", "fees", "charge", "charges"}),
        (("rate", "rates", "interest rate", "interest rates", "percentage", "percent", "earn on"), {"rate", "rates", "interest", "percentage", "percent"}),
        (("document", "documents", "requirement", "requirements"), {"document", "documents", "application", "form", "identification", "guarantor"}),
        (("amount", "maximum", "max", "limit", "borrow"), {"amount", "maximum", "limit", "borrow", "loan"}),
        (("deadline", "how long", "approval", "time"), {"deadline", "approval", "days", "time", "process"}),
        (("balance",), {"balance"}),
        (("withdraw", "withdrawal"), {"withdraw", "withdrawal"}),
    )
    for query_terms, evidence_terms in groups:
        if any(term in query for term in query_terms):
            return evidence_terms
    return set()


def _has_detail_request(query: str) -> bool:
    detail_terms = (
        "fee", "fees", "rate", "rates", "percentage", "percent", "amount",
        "maximum", "limit", "document", "documents", "requirement", "requirements",
        "deadline", "approval", "balance", "withdrawal", "charge", "cost",
    )
    return any(term in query for term in detail_terms)
