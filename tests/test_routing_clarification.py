"""Tests for first-class Clarification outcome and decision routing."""

from unittest.mock import AsyncMock

import pytest

from app.ai.routing_types import OperationType, WorkflowType
from app.schemas.intent import RoutingDecision
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.services.conversations.conversation_service import handle_message_async


@pytest.mark.anyio
async def test_ambiguous_query_triggers_clarification():
    clarification_text = "Would you like to check how much you can borrow as a loan, or calculate savings toward a goal?"
    mock_router = AsyncMock()
    mock_router.classify = AsyncMock(
        return_value=RoutingDecision(
            workflow=WorkflowType.CLARIFICATION,
            operation=OperationType.CLARIFY_DISAMBIGUATE.value,
            confidence=0.6,
            language="en",
            reasoning="Underspecified inquiry: user asked 'how much can I get' without specifying loan or savings.",
            clarification_prompt=clarification_text,
        )
    )

    msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254700000001",
        to_number="whatsapp:+14155238886",
        body="How much can I get?",
    )
    history = InMemoryConversationHistory()

    response = await handle_message_async(
        msg,
        intent_router=mock_router,
        history_store=history,
    )

    assert response == clarification_text
    # Verify history recorded the clarification turn
    history_turns = history.get("whatsapp:+254700000001")
    assert len(history_turns) == 2
    assert history_turns[0].content == "How much can I get?"
    assert history_turns[1].content == clarification_text


@pytest.mark.anyio
async def test_routing_decision_directs_to_member_data():
    mock_router = AsyncMock()
    mock_router.classify = AsyncMock(
        return_value=RoutingDecision(
            workflow=WorkflowType.MEMBER_DATA,
            operation=OperationType.MEMBER_BALANCE.value,
            confidence=0.98,
            language="en",
            reasoning="Member checks account balance.",
        )
    )

    msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254700000001",
        to_number="whatsapp:+14155238886",
        body="Check my balance please",
    )
    history = InMemoryConversationHistory()

    response = await handle_message_async(
        msg,
        intent_router=mock_router,
        history_store=history,
    )

    from app.services.conversations.response import MEMBER_NOT_RECOGNIZED

    assert response == MEMBER_NOT_RECOGNIZED or "KSh" in response
