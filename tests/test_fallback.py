"""Tests for fallback taxonomy (System 6.3)."""

import pytest

from app.core.fallback import (
    FallbackCategory,
    FallbackHandler,
    FallbackResponse,
)


def test_fallback_category_enum_values():
    """Fallback categories should have expected values."""
    assert FallbackCategory.CLARIFICATION == "clarification"
    assert FallbackCategory.KNOWLEDGE_GAP == "knowledge_gap"
    assert FallbackCategory.GUARDRAIL == "guardrail"
    assert FallbackCategory.HUMAN_ESCALATION == "human_escalation"
    assert FallbackCategory.PROVIDER_FAILURE == "provider_failure"


def test_clarification_fallback():
    """Clarification fallback should request more specificity."""
    response = FallbackHandler.clarification(
        query="Tell me about loans",
        detected_topics=["personal_loans", "business_loans", "development_loans"],
    )

    assert response.category == FallbackCategory.CLARIFICATION
    assert response.should_escalate is False
    assert "more details" in response.user_message.lower() or "specific" in response.user_message.lower()
    assert response.metadata["query"] == "Tell me about loans"
    assert response.metadata["topics"] == ["personal_loans", "business_loans", "development_loans"]


def test_clarification_without_topics():
    """Clarification should work without detected topics."""
    response = FallbackHandler.clarification(query="Help")

    assert response.category == FallbackCategory.CLARIFICATION
    assert len(response.user_message) > 0


def test_knowledge_gap_fallback():
    """Knowledge gap fallback should indicate missing information."""
    response = FallbackHandler.knowledge_gap(
        query="What is the current USD/KES exchange rate?",
        suggestion="You can check exchange rates at your bank or online financial services.",
    )

    assert response.category == FallbackCategory.KNOWLEDGE_GAP
    assert response.should_escalate is True
    assert "couldn't find" in response.user_message.lower() or "information" in response.user_message.lower()
    assert response.metadata["suggestion"] == "You can check exchange rates at your bank or online financial services."


def test_guardrail_fallback():
    """Guardrail fallback should redirect to staff."""
    response = FallbackHandler.guardrail(
        query="Tell me exactly which investment I should make",
        reason="Directive investment advice is outside scope",
    )

    assert response.category == FallbackCategory.GUARDRAIL
    assert response.should_escalate is True
    assert "personalized guidance" in response.user_message.lower() or "representative" in response.user_message.lower()
    assert response.metadata["reason"] == "Directive investment advice is outside scope"


def test_human_escalation_fallback():
    """Human escalation fallback should indicate handoff to staff."""
    response = FallbackHandler.human_escalation(
        query="I don't recognize a transaction",
        reason="Fraud allegation",
    )

    assert response.category == FallbackCategory.HUMAN_ESCALATION
    assert response.should_escalate is True
    assert "representative" in response.user_message.lower() or "staff" in response.user_message.lower()
    assert "connecting" in response.user_message.lower()
    assert response.metadata["reason"] == "Fraud allegation"


def test_provider_failure_fallback():
    """Provider failure fallback should not expose technical details."""
    response = FallbackHandler.provider_failure(
        service_name="Groq LLM",
        error="ConnectionError: Unable to reach API server",
    )

    assert response.category == FallbackCategory.PROVIDER_FAILURE
    assert response.should_escalate is True
    # User message should NOT contain technical details
    assert "ConnectionError" not in response.user_message
    assert "API" not in response.user_message
    # But internal reason should have them
    assert "ConnectionError" in response.internal_reason
    assert response.metadata["service"] == "Groq LLM"


def test_fallback_response_structure():
    """FallbackResponse should have required fields."""
    response = FallbackHandler.knowledge_gap("Test query")

    assert isinstance(response, FallbackResponse)
    assert response.category is not None
    assert response.user_message is not None
    assert response.internal_reason is not None
    assert isinstance(response.should_escalate, bool)
    assert isinstance(response.metadata, dict)


def test_metadata_preservation():
    """Metadata should be preserved in responses."""
    metadata = {"query_language": "sw", "confidence": 0.45}
    response = FallbackHandler.knowledge_gap(
        query="Test",
        metadata=metadata,
    )

    assert response.metadata == metadata


def test_fallback_escalation_flags():
    """Escalation flags should match category."""
    # Should NOT escalate
    clarification = FallbackHandler.clarification("Ambiguous question")
    assert clarification.should_escalate is False

    # Should escalate
    gap = FallbackHandler.knowledge_gap("Unknown question")
    assert gap.should_escalate is True

    guardrail = FallbackHandler.guardrail("Bad request", "Out of scope")
    assert guardrail.should_escalate is True

    escalation = FallbackHandler.human_escalation("Needs human", "Fraud")
    assert escalation.should_escalate is True

    failure = FallbackHandler.provider_failure("Service X", "Failed")
    assert failure.should_escalate is True


def test_user_message_is_helpful():
    """All user messages should be helpful and not confusing."""
    messages = [
        FallbackHandler.clarification("?"),
        FallbackHandler.knowledge_gap("What?"),
        FallbackHandler.guardrail("Give advice", "Out of scope"),
        FallbackHandler.human_escalation("Help", "Request"),
        FallbackHandler.provider_failure("Service", "Error"),
    ]

    for response in messages:
        # Messages should not contain internal technical jargon
        assert "answerable" not in response.user_message
        assert "fallback" not in response.user_message.lower()
        assert "error" not in response.user_message.lower()
        # Messages should be reasonably long
        assert len(response.user_message) > 20
