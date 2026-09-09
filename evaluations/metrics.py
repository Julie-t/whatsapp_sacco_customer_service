"""Deterministic metrics for offline RAG evaluation."""

import re

from .grounding import GroundingVerifier

from .models import ClaimResult, MetricResult


def recall_at(ranked_ids: list[str], expected_source: str | None, rank: int) -> bool:
    return bool(expected_source and expected_source in ranked_ids[:rank])


def recall_metrics(ranked_ids: list[str], expected_source: str | None) -> dict[str, bool]:
    return {f"recall_at_{rank}": recall_at(ranked_ids, expected_source, rank) for rank in (1, 3, 5)}


def groundedness(answer: str, evidence: str, expected_claims: list[str] | None = None) -> MetricResult:
    verification = GroundingVerifier().verify(answer, evidence, expected_claims)
    results = [
        ClaimResult(
            claim=claim["claim"],
            supported=claim["status"] == "supported",
            evidence=claim.get("evidence", []),
        )
        for claim in verification.claims
    ]
    return MetricResult(
        passed=verification.supported,
        score=verification.score,
        reason=verification.reason,
        details={
            "claims": [result.model_dump() for result in results],
            "unsupported_claims": verification.unsupported_claims,
            "contradictions": verification.contradictions,
            "risk": verification.risk,
            "expected_claims": expected_claims or [],
        },
    )


def relevance(question: str, answer: str) -> MetricResult:
    question_terms = _keywords(question)
    answer_terms = _keywords(answer)
    overlap = question_terms & answer_terms
    score = len(overlap) / len(question_terms) if question_terms else 1.0
    return MetricResult(passed=score >= 0.4, score=min(score, 1.0), reason="The answer addresses the question's main terms." if score >= 0.4 else "The answer does not address enough of the question's main terms.", details={"overlap": sorted(overlap)})


def language_correctness(answer: str, expected: str) -> MetricResult:
    if expected == "mixed":
        return MetricResult(passed=True, score=1.0, reason="Mixed-language responses are allowed.")
    swahili_markers = {"na", "wa", "ya", "ni", "kwa", "kuhusu", "nini", "jinsi"}
    tokens = set(re.findall(r"[a-zA-Z]+", answer.lower()))
    swahili_score = len(tokens & swahili_markers) / max(len(tokens), 1)
    looks_swahili = swahili_score >= 0.08
    correct = not looks_swahili if expected == "en" else looks_swahili
    return MetricResult(passed=correct, score=1.0 if correct else 0.0, reason=f"Response is consistent with requested language: {expected}." if correct else f"Response may not match requested language: {expected}.", details={"swahili_marker_ratio": swahili_score})


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"[.!?]+", text) if sentence.strip()]


def _keywords(text: str) -> set[str]:
    stopwords = {"what", "is", "the", "a", "an", "for", "do", "i", "to", "and", "of", "how", "can", "my", "are"}
    aliases = {
        "documents": "document",
        "shares": "share",
        "savings": "saving",
        "withdraw": "withdrawal",
        "payments": "repayment",
        "payment": "repayment",
        "repayments": "repayment",
        "repaying": "repayment",
        "defer": "deferral",
        "deferring": "deferral",
        "regulated": "regulation",
        "regulatory": "regulation",
        "requirements": "requirement",
    }
    keywords = set()
    for token in re.findall(r"[a-zA-Z]+", text.lower()):
        if token in stopwords or len(token) <= 2:
            continue
        token = aliases.get(token, token)
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        keywords.add(token)
    return keywords


def _claim_supported(claim: str, evidence_lower: str) -> bool:
    claim_lower = claim.lower()
    if "not " in evidence_lower and "not " not in claim_lower:
        return False
    claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim_lower))
    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", evidence_lower))
    if claim_numbers and not claim_numbers.issubset(evidence_numbers):
        return False
    terms = _keywords(claim)
    return bool(terms) and len(terms & _keywords(evidence_lower)) / len(terms) >= 0.5
