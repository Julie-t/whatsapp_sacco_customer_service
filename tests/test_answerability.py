"""Tests for answerability checking (System 6.2)."""

import pytest

from app.ai.rag.answerability import AnswerabilityChecker
from app.ai.rag.models import RAGResult


def make_result(
    document_id: str = "doc1",
    content: str = "This is test content about the topic.",
    score: float = 0.85,
) -> RAGResult:
    """Create a test RAGResult."""
    return RAGResult(
        document_id=document_id,
        chunk_id=f"{document_id}_chunk_00",
        title=f"Test: {document_id}",
        content=content,
        source="test data",
        score=score,
        sacco_id="demo_sacco",
        language="en",
        topic="test",
        content_type="general",
        metadata={},
    )


def test_no_results_not_answerable():
    """No results should always be not answerable."""
    checker = AnswerabilityChecker()
    decision = checker.check("What is X?", [])

    assert decision.answerable is False
    assert decision.confidence == 0.0
    assert decision.min_score is None


def test_low_score_results_not_answerable():
    """Results with score below threshold should be not answerable."""
    checker = AnswerabilityChecker(min_retrieval_score=0.5)
    results = [make_result(score=0.3)]

    decision = checker.check("What is X?", results)

    assert decision.answerable is False
    assert decision.min_score == 0.3


def test_high_score_results_answerable():
    """Results with high scores should be answerable."""
    checker = AnswerabilityChecker(min_retrieval_score=0.3)
    results = [make_result(score=0.85)]

    decision = checker.check("What is compound interest?", results)

    assert decision.answerable is True
    assert decision.confidence > 0.0


def test_short_content_low_confidence():
    """Very short content should have low confidence."""
    checker = AnswerabilityChecker(min_result_length=100)
    results = [make_result(content="Brief.", score=0.9)]

    decision = checker.check("What is X?", results)

    assert decision.answerable is False
    assert "brief" in decision.reason.lower() or "short" in decision.reason.lower()


def test_adequate_content_answerable():
    """Adequate length content with good score should be answerable."""
    checker = AnswerabilityChecker(min_result_length=50)
    content = "This is a detailed explanation about the topic that provides comprehensive information."
    results = [make_result(content=content, score=0.85)]

    decision = checker.check("What is X?", results)

    assert decision.answerable is True


def test_specific_query_generic_content_reduced_confidence():
    """Specific query with generic content should have reduced confidence."""
    checker = AnswerabilityChecker()
    results = [make_result(
        content="General information about the service.",
        score=0.7,
    )]

    decision = checker.check("What is the withdrawal fee?", results)

    # Should still be answerable but with caution
    assert "may not contain all specific" in decision.reason.lower()


def test_specific_query_specific_content_high_confidence():
    """Specific query with specific content should have high confidence."""
    checker = AnswerabilityChecker()
    results = [make_result(
        content="The withdrawal fee for development loans is 5% of the amount being withdrawn.",
        score=0.9,
    )]

    decision = checker.check("What is the withdrawal fee?", results)

    assert decision.answerable is True
    assert decision.confidence > 0.8


def test_multiple_results_uses_minimum_score():
    """Multiple results should check minimum score."""
    checker = AnswerabilityChecker(min_retrieval_score=0.5)
    results = [
        make_result(document_id="doc1", score=0.9),
        make_result(document_id="doc2", score=0.3),
        make_result(document_id="doc3", score=0.8),
    ]

    decision = checker.check("What is X?", results)

    assert decision.min_score == 0.3
    assert decision.answerable is False


def test_confidence_scales_with_score():
    """Confidence should scale with retrieval score."""
    checker = AnswerabilityChecker(min_retrieval_score=0.2)

    # High score
    decision_high = checker.check(
        "What is X?",
        [make_result(score=0.95)],
    )

    # Low score (but above threshold)
    decision_low = checker.check(
        "What is X?",
        [make_result(score=0.4)],
    )

    assert decision_high.confidence > decision_low.confidence


def test_reason_is_descriptive():
    """Decision reason should be descriptive."""
    checker = AnswerabilityChecker()
    decision = checker.check("What is X?", [])

    assert len(decision.reason) > 10
    assert "evidence" in decision.reason.lower() or "retrieved" in decision.reason.lower()


def test_queryability_judgment_examples():
    """Real-world answerability examples."""
    checker = AnswerabilityChecker()

    # Case 1: Clear policy question with relevant doc
    results1 = [make_result(
        content="Development loans require 5 documents: ID, proof of income, bank statement, loan application, and collateral valuation.",
        score=0.92,
    )]
    decision1 = checker.check("What documents do I need for a development loan?", results1)
    assert decision1.answerable is True

    # Case 2: Specific question with irrelevant doc
    results2 = [make_result(
        document_id="withdrawal",
        content="Withdrawal procedures are available at the SACCO office.",
        score=0.85,
    )]
    decision2 = checker.check("What is the withdrawal fee?", results2)
    assert decision2.answerable is False or decision2.confidence < 0.8


def test_empty_content_not_answerable():
    """Empty or None content should be not answerable."""
    checker = AnswerabilityChecker()
    results = [make_result(content="")]

    decision = checker.check("What is X?", results)

    assert decision.answerable is False
