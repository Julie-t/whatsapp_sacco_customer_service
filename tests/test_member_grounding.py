"""Unit tests for Member Data Grounding Service (System 12.15, 12.16)."""

import pytest

from app.services.members.member_grounding_service import MemberDataGroundingService


@pytest.fixture
def grounding_service():
    return MemberDataGroundingService()


def test_grounding_passes_matching_numbers(grounding_service):
    authoritative_context = {
        "savings_balance": 32450.0,
        "loan_balance": 125000.0,
        "monthly_instalment": 4500.0,
    }

    generated_text = (
        "Your savings balance is KSh 32,450.00 and your current loan balance "
        "is KSh 125,000 with a monthly instalment of KSh 4,500."
    )

    result = grounding_service.verify_response(generated_text, authoritative_context)
    assert result.is_grounded is True
    assert len(result.hallucinated_figures) == 0


def test_grounding_detects_and_blocks_hallucinated_balance(grounding_service):
    authoritative_context = {
        "savings_balance": 32450.0,
        "loan_balance": 125000.0,
    }

    # Model hallucinates 150,000 instead of 125,000
    hallucinated_text = (
        "Hello Edna, your total loan balance remaining is KSh 150,000. "
        "Your savings balance stands at KSh 32,450."
    )

    result = grounding_service.verify_response(
        hallucinated_text,
        authoritative_context,
        fallback_template="Your loan balance is KSh 125,000 and your savings balance is KSh 32,450.",
    )

    assert result.is_grounded is False
    assert 150000.0 in result.hallucinated_figures
    assert 32450.0 not in result.hallucinated_figures
    assert result.fallback_message is not None
    assert "Blocked hallucinated figures" in result.audit_notes
