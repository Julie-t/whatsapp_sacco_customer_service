"""Claim-level, deterministic verification for System 6 answers."""

import re
from dataclasses import dataclass


HIGH_RISK_TERMS = {
    "amount", "balance", "charge", "cost", "deadline", "eligible", "eligibility",
    "fee", "fees", "interest", "limit", "money", "percent", "percentage",
    "rate", "rates", "regulatory", "repayment", "transaction",
}
STOPWORDS = {
    "a", "an", "and", "are", "be", "by", "for", "from", "how", "in", "is",
    "it", "of", "on", "or", "the", "this", "to", "what", "with",
}


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
        return self.__dict__.copy()


class GroundingVerifier:
    """Verify answer claims against the complete retrieved context."""

    def verify(self, answer: str, evidence: str, expected_claims: list[str] | None = None) -> VerificationResult:
        evidence_sentences = _sentences(evidence)
        checked = []
        for claim in _sentences(answer):
            status, supporting_evidence = self._classify(claim, evidence_sentences)
            checked.append({"claim": claim, "status": status, "evidence": supporting_evidence})

        unsupported = [item["claim"] for item in checked if item["status"] == "unsupported"]
        contradictions = [item["claim"] for item in checked if item["status"] == "contradicted"]
        supported_count = sum(item["status"] == "supported" for item in checked)
        score = supported_count / len(checked) if checked else 1.0
        failed_claims = unsupported + contradictions
        risk = "HIGH" if any(_is_high_risk(claim) for claim in failed_claims) else "MEDIUM" if failed_claims else "LOW"
        return VerificationResult(
            supported=not failed_claims,
            score=score,
            unsupported_claims=unsupported,
            contradictions=contradictions,
            needs_escalation=bool(contradictions),
            reason=("Claims are supported by retrieved evidence." if not failed_claims else "One or more claims are unsupported or contradicted by retrieved evidence."),
            claims=checked,
            risk=risk,
        )

    def _classify(self, claim: str, evidence_sentences: list[str]) -> tuple[str, list[str]]:
        if _is_demo_disclaimer(claim, evidence_sentences):
            return "supported", _demo_evidence(evidence_sentences)
        if _is_non_factual(claim):
            return "supported", []
        claim_numbers = _numbers(claim)
        claim_terms = _terms(claim)
        best_overlap = 0.0
        best_evidence: list[str] = []
        contradiction = False
        for sentence in evidence_sentences:
            sentence_terms = _terms(sentence)
            overlap = len(claim_terms & sentence_terms) / len(claim_terms) if claim_terms else 0.0
            if overlap > best_overlap:
                best_overlap = overlap
                best_evidence = [sentence]
            evidence_is_negative = bool(re.search(r"\b(?:not|no|never)\b", sentence.lower()))
            claim_is_negative = bool(re.search(r"\b(?:not|no|never)\b", claim.lower()))
            if overlap >= 0.5 and evidence_is_negative and not claim_is_negative:
                return "unsupported", [sentence]
                continue
            if overlap >= 0.5 and claim_numbers:
                evidence_numbers = _numbers(sentence)
                if claim_numbers <= evidence_numbers:
                    return "supported", [sentence]
                if evidence_numbers and not claim_numbers & evidence_numbers:
                    contradiction = True
        if contradiction:
            return "contradicted", best_evidence
        if claim_numbers:
            return "unsupported", []
        if best_overlap >= 0.5:
            return "supported", best_evidence
        return "unsupported", []


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _terms(text: str) -> set[str]:
    # Common financial/paraphrase synonyms to reduce false negatives
    aliases = {
        "calculated": "computed", "compute": "computed", "computing": "computed",
        "original": "principal", "principal": "principal",
        "earlier": "previous", "previous": "previous", "previou": "previous",
        "amount": "principal",
        "already": "accumulated", "accumulated": "accumulated",
        "earned": "earned", "earning": "earned",
        "require": "required", "required": "required", "requirement": "required",
        "need": "required", "needed": "required",
        "typically": "generally", "generally": "generally", "usually": "generally",
        "document": "document", "documents": "document",
        "income": "income", "proof": "evidence", "evidence": "evidence",
    }
    terms = set()
    for token in re.findall(r"[a-zA-Z]+", text.lower()):
        if token in STOPWORDS or len(token) < 3:
            continue
        if token.endswith("ies") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 4:
            token = token[:-1]
        token = aliases.get(token, token)
        terms.add(token)
    return terms


def _numbers(text: str) -> set[str]:
    return {number.rstrip("%") for number in re.findall(r"\b\d+(?:\.\d+)?%?\b", text)}


def _is_high_risk(claim: str) -> bool:
    return bool(_terms(claim) & HIGH_RISK_TERMS or _numbers(claim))


def _is_demo_disclaimer(claim: str, evidence_sentences: list[str]) -> bool:
    lowered = claim.lower()
    claims_demo = "synthetic" in lowered or "demo" in lowered
    claims_nonofficial = "not an official" in lowered or "not official" in lowered
    metadata_confirms_demo = any(
        "synthetic/demo data: true" in sentence.lower()
        or ("synthetic" in sentence.lower() and "demo" in sentence.lower())
        for sentence in evidence_sentences
    )
    return claims_demo and metadata_confirms_demo and (not claims_nonofficial or metadata_confirms_demo)


def _is_non_factual(claim: str) -> bool:
    """Detect non-factual sentences that should be exempt from grounding.

    Three categories:
    1. Introductory/transitional framing (sets up a list, restates the question)
    2. Safe disclaimers directing the member to verify with SACCO staff
    3. Meta-commentary about data provenance
    """
    lowered = claim.lower().strip().rstrip(".:")
    # Category 1: Introductory framing
    framing_patterns = (
        "you'll typically need", "you will typically need",
        "you'll need", "you will need",
        "here are", "here is", "the following",
        "for a loan application", "for loan application",
        "you may need", "you would need",
    )
    if any(pattern in lowered for pattern in framing_patterns):
        # Only exempt if this is a short introductory sentence (no substantive data)
        terms = _terms(claim)
        if len(terms) <= 8 and not _numbers(claim):
            return True
    # Category 2: Safe disclaimers
    disclaimer_patterns = (
        "please contact", "please check with", "check with your sacco",
        "verify with", "confirm with", "contact sacco staff",
        "contact your sacco", "please reach out",
        "if you need confirmation", "for the actual",
        "for the exact", "that applies to your",
    )
    if any(pattern in lowered for pattern in disclaimer_patterns):
        return True
    # Category 3: Meta-commentary about data source
    provenance_patterns = (
        "comes from the", "description comes from",
        "this is from", "based on the illustrative",
        "from the sacco\u2019s illustrative", "from the sacco's illustrative",
        "illustrative policy",
    )
    if any(pattern in lowered for pattern in provenance_patterns):
        return True
    return False


def _demo_evidence(evidence_sentences: list[str]) -> list[str]:
    return [
        sentence for sentence in evidence_sentences
        if "synthetic/demo data: true" in sentence.lower()
        or ("synthetic" in sentence.lower() and "demo" in sentence.lower())
    ][:1]