"""Structured, evidence-only verification for generated RAG answers."""

import json
import re
from dataclasses import dataclass


HIGH_RISK_TERMS = {
    "fee", "fees", "rate", "rates", "percent", "percentage", "%", "amount",
    "balance", "transaction", "limit", "eligibility", "eligible", "deadline",
    "repayment", "regulatory", "guarantor",
}


@dataclass(frozen=True)
class ClaimVerification:
    claim: str
    status: str
    evidence: list[str]


@dataclass(frozen=True)
class VerificationResult:
    supported: bool
    score: float
    unsupported_claims: list[str]
    contradictions: list[str]
    needs_escalation: bool
    reason: str
    claims: list[dict[str, object]]
    risk: str

    def model_dump(self) -> dict[str, object]:
        return {
            "supported": self.supported,
            "score": self.score,
            "unsupported_claims": self.unsupported_claims,
            "contradictions": self.contradictions,
            "needs_escalation": self.needs_escalation,
            "reason": self.reason,
            "claims": self.claims,
            "risk": self.risk,
        }


class AnswerVerifier:
    """Verify answer claims against retrieved text without expected-answer matching."""

    def verify(self, answer: str, evidence: str) -> VerificationResult:
        claims = _sentences(answer)
        evidence_parts = [part.strip() for part in re.split(r"\n+|(?<=[.!?])\s+", evidence) if part.strip()]
        checked: list[ClaimVerification] = []
        contradictions: list[str] = []
        for claim in claims:
            support = _claim_supported(claim, evidence)
            conflict = _claim_contradicted(claim, evidence)
            status = "contradicted" if conflict else "supported" if support else "unsupported"
            if conflict:
                contradictions.append(claim)
            checked.append(ClaimVerification(claim, status, evidence_parts if support else []))
        supported_count = sum(item.status == "supported" for item in checked)
        score = supported_count / len(checked) if checked else 1.0
        unsupported = [
            item.claim for item in checked if item.status in {"unsupported", "contradicted"}
        ]
        high_risk = any(_is_high_risk(claim) for claim in unsupported + contradictions)
        supported = not unsupported and not contradictions
        return VerificationResult(
            supported=supported,
            score=score,
            unsupported_claims=unsupported,
            contradictions=contradictions,
            needs_escalation=bool(contradictions),
            reason=("All factual claims are supported by retrieved evidence." if supported
                    else "One or more claims are unsupported or conflict with retrieved evidence."),
            claims=[item.__dict__ for item in checked],
            risk="HIGH" if high_risk else "MEDIUM" if not supported else "LOW",
        )

    async def verify_with_llm(self, llm, answer: str, evidence: str) -> VerificationResult:
        """Run one provider-backed structured check; fall back safely if malformed."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Verify the answer only against the evidence. Return JSON only with "
                    "supported (boolean), score (number 0 to 1), unsupported_claims "
                    "(array of strings), contradictions (array of strings), "
                    "needs_escalation (boolean), reason (string), and risk (LOW, MEDIUM, HIGH). "
                    "Do not provide reasoning traces."
                ),
            },
            {"role": "user", "content": f"ANSWER:\n{answer}\n\nEVIDENCE:\n{evidence}"},
        ]
        try:
            raw = await llm.generate(messages)
            payload = json.loads(_extract_json(raw))
            return VerificationResult(
                supported=bool(payload["supported"]),
                score=max(0.0, min(1.0, float(payload.get("score", 0.0)))),
                unsupported_claims=list(payload.get("unsupported_claims", [])),
                contradictions=list(payload.get("contradictions", [])),
                needs_escalation=bool(payload.get("needs_escalation", False)),
                reason=str(payload.get("reason", "Structured provider verification completed.")),
                claims=list(payload.get("claims", [])),
                risk=str(payload.get("risk", "HIGH" if not payload["supported"] else "LOW")).upper(),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return self.verify(answer, evidence)


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[!?])\s+|(?<=\.)\s+(?!\d)", text)
        if sentence.strip()
    ]


def _extract_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("Verifier did not return a JSON object")
    return match.group(0)


def _keywords(text: str) -> set[str]:
    stopwords = {"what", "is", "the", "a", "an", "for", "do", "i", "to", "and", "of", "how", "can", "my", "are"}
    return {
        token[:-1] if token.endswith("s") and len(token) > 3 else token
        for token in re.findall(r"[a-zA-Z]+", text.lower())
        if token not in stopwords and len(token) > 2
    }


def _claim_supported(claim: str, evidence: str) -> bool:
    claim_lower = claim.lower()
    evidence_lower = evidence.lower()
    claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim_lower))
    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", evidence_lower))
    if claim_numbers and not claim_numbers.issubset(evidence_numbers):
        return False
    terms = _keywords(claim)
    return bool(terms) and len(terms & _keywords(evidence)) / len(terms) >= 0.5


def _claim_contradicted(claim: str, evidence: str) -> bool:
    claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim.lower()))
    if not claim_numbers:
        return False
    claim_terms = _keywords(claim)
    for sentence in _sentences(evidence):
        if len(claim_terms & _keywords(sentence)) >= max(2, len(claim_terms) // 2):
            evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", sentence.lower()))
            if evidence_numbers and not claim_numbers.intersection(evidence_numbers):
                return True
    return False


def _is_high_risk(claim: str) -> bool:
    lowered = claim.lower()
    return any(term in lowered for term in HIGH_RISK_TERMS)