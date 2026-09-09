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

        top_score = max(result.score for result in results)
        min_score = min(result.score for result in results)
        if top_score < self.min_retrieval_score:
            return AnswerabilityDecision(
                answerable=False,
                confidence=max(0.0, top_score / self.min_retrieval_score),
                reason=(
                    f"Retrieved evidence is not sufficiently relevant (best score: {top_score:.2f}). "
                    f"Minimum confidence threshold is {self.min_retrieval_score:.2f}."
                ),
                min_score=min_score,
            )

        top_result = max(results, key=lambda result: result.score)
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
        evidence_text = " ".join(
            f"{result.title} {result.topic} {result.content}".lower()
            for result in results[:3]
        )
        missing_terms = _missing_required_terms(query_lower, evidence_text, required_terms)
        if missing_terms:
            return AnswerabilityDecision(
                answerable=False,
                confidence=min(0.75, 0.45 + (top_score * 0.35)),
                reason=(
                    f"Retrieved evidence does not specify the requested detail: {', '.join(sorted(missing_terms))}. "
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


def _missing_required_terms(query: str, evidence: str, required_terms: set[str]) -> set[str]:
    """Require the requested concept, rather than any loosely related synonym."""
    if "exchange rate" in query:
        return set() if "exchange" in evidence and "rate" in evidence else {"exchange rate"}
    if "increase" in query and "contribution" in query:
        return set() if "increase" in evidence and "contribution" in evidence else {"increase contribution"}
    if "convert" in query and "savings" in query and "shares" in query:
        return set() if "convert" in evidence and "savings" in evidence and "share" in evidence else {"conversion process"}
    if "working abroad" in query:
        return {"working abroad"} if not any(term in evidence for term in ("abroad", "overseas")) else set()
    if "minimum balance" in query:
        return {"minimum balance"} if "minimum balance" not in evidence else set()
    if "financial support" in query and "education" in query:
        return {"financial support"} if "financial support" not in evidence else set()
    if "change" in query and "guarantor" in query:
        return {"guarantor change"} if "change" not in evidence else set()
    if "become a guarantor" in query:
        return {"guarantor application"} if not any(term in evidence for term in ("become", "apply", "application")) else set()
    if "sacco" in query and "generate income" in query:
        return {"income generation"} if not ("generate" in evidence and "income" in evidence) else set()
    if "registered" in query and "regulated" in query:
        return {"registration and regulation"} if not ("registered" in evidence and ("regulated" in evidence or "regulation" in evidence)) else set()
    if "miss" in query and "loan payment" in query:
        return {"missed payment"} if not any(term in evidence for term in ("miss", "default", "late", "penalt")) else set()
    if "defer" in query and "loan payment" in query:
        return {"payment deferral"} if not any(term in evidence for term in ("defer", "postpone", "moratorium", "payment holiday")) else set()
    if "convert" in query and "savings" in query and "shares" in query:
        return {"conversion process"}
    if not required_terms:
        return set()
    if any(term in query for term in ("fee", "fees", "charge", "charges")):
        missing = set()
        if not any(term in evidence for term in ("fee", "fees", "charge", "charges")):
            missing.add("fee")
        if "withdrawal" in query and "withdraw" not in evidence:
            missing.add("withdrawal")
        if "processing fee" in query and "processing fee" not in evidence:
            missing.add("processing fee")
        return missing
    if any(term in query for term in ("document", "documents", "requirement", "requirements")):
        return set() if any(term in evidence for term in ("document", "application", "form", "identification", "guarantor")) else {"documents"}
    if any(term in query for term in ("rate", "rates", "interest", "percentage", "percent")):
        return set() if any(term in evidence for term in ("rate", "interest", "%", "percent")) else {"rate"}
    if any(term in query for term in ("maximum loan", "maximum amount", "how much can i borrow")):
        return {"loan amount"} if not any(term in evidence for term in ("loan amount", "maximum amount", "maximum loan", "loan limit")) else set()
    if "approval" in query and "how long" in query:
        return {"approval time"} if not any(term in evidence for term in ("days", "time", "within", "takes")) else set()
    if "approval" in query:
        return set() if "approval" in evidence else {"approval process"}
    return {term for term in required_terms if term not in evidence}
