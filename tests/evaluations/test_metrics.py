from evaluations.metrics import groundedness, language_correctness, relevance
from app.ai.rag.answer_verifier import AnswerVerifier


def test_groundedness_rejects_unsupported_numeric_claim():
    result = groundedness(
        "The processing fee is 5 percent.",
        "The processing fee is not specified in the knowledge base.",
        ["The processing fee is 5 percent."],
    )

    assert result.passed is False
    assert result.details["unsupported_claims"]


def test_relevance_rejects_off_topic_answer():
    result = relevance(
        "What documents do I need for a loan?",
        "Loan interest rates are calculated monthly.",
    )

    assert result.passed is False


def test_mixed_language_is_allowed():
    assert language_correctness("Loan yangu inalipwa aje?", "mixed").passed


def test_answer_verifier_accepts_supported_claim():
    result = AnswerVerifier().verify(
        "The loan term is 36 months.",
        "Development loans may have a repayment period of up to 36 months.",
    )

    assert result.supported is True
    assert result.unsupported_claims == []


def test_answer_verifier_marks_unsupported_fee_as_high_risk():
    result = AnswerVerifier().verify(
        "The processing fee is 5 percent.",
        "The loan rate is not specified in this document.",
    )

    assert result.supported is False
    assert result.risk == "HIGH"
    assert result.unsupported_claims


def test_answer_verifier_detects_conflicting_number():
    result = AnswerVerifier().verify(
        "The interest rate is 1.0 percent.",
        "The interest rate is 1.17 percent.",
    )

    assert result.supported is False
    assert result.contradictions
    assert result.needs_escalation is True


def test_groundedness_accepts_supported_synthetic_disclaimer_metadata():
    result = groundedness(
        "This is synthetic/demo data, not an official SACCO policy.",
        "Synthetic/demo data: True\nContent: Loan terms are illustrative.",
    )

    assert result.passed is True
