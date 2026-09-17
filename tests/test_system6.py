import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.routes import whatsapp as whatsapp_route
from app.main import app
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.schemas.rag_answer import RAGAnswerResponse, RAGAnswerSource
from app.services.conversations.conversation_service import (
    HUMAN_SUPPORT_PLACEHOLDER,
    MEMBER_NOT_RECOGNIZED,
    handle_message_async,
)
from app.services.conversations.conversation_history import InMemoryConversationHistory


class FakeRouter:
    def __init__(self, result):
        self.result = result
        self.messages = []

    async def classify(self, message):
        self.messages.append(message)
        return self.result


class FakeAnswerService:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def answer(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def message(body: str) -> IncomingWhatsAppMessage:
    return IncomingWhatsAppMessage(from_number="+254700000000", body=body)


def triage(**overrides) -> RequestTriageResult:
    values = {
        "language": "en",
        "needs_member_data": False,
        "likely_needs_human": False,
        "reasoning": "General SACCO information.",
    }
    values.update(overrides)
    return RequestTriageResult(**values)


def answer_response() -> RAGAnswerResponse:
    return RAGAnswerResponse(
        query="What are the requirements for a development loan?",
        answer="The demo knowledge base lists identification and application documents.",
        sources=[
            RAGAnswerSource(
                document_id="loan_documents",
                chunk_id="loan_documents_chunk_00",
                title="Required Documents for Loan Applications",
                source="synthetic test data",
                score=0.9,
            )
        ],
        grounded=True,
    )


def test_general_question_uses_rag_answer_service_once():
    router = FakeRouter(triage())
    answer_service = FakeAnswerService(answer_response())

    response = asyncio.run(
        handle_message_async(
            message("What are the requirements for a development loan?"),
            intent_router=router,
            rag_answer_service=answer_service,
        )
    )

    assert len(answer_service.calls) == 1
    assert answer_service.calls[0]["language"] == "en"
    assert "identification" in response.lower() or "documents" in response.lower()


def test_follow_up_question_receives_whatsapp_history():
    router = FakeRouter(triage())
    answer_service = FakeAnswerService(answer_response())
    history = InMemoryConversationHistory()

    asyncio.run(
        handle_message_async(
            message("What is a development loan?"),
            intent_router=router,
            rag_answer_service=answer_service,
            history_store=history,
        )
    )
    asyncio.run(
        handle_message_async(
            message("How much can I get?"),
            intent_router=router,
            rag_answer_service=answer_service,
            history_store=history,
        )
    )

    assert answer_service.calls[0]["conversation_history"] == []
    assert [turn["role"] for turn in answer_service.calls[1]["conversation_history"]] == [
        "user",
        "assistant",
    ]


def test_member_question_does_not_use_rag():
    router = FakeRouter(
        triage(
            needs_member_data=True,
            reasoning="Requires member-specific account data.",
        )
    )
    answer_service = FakeAnswerService(answer_response())

    response = asyncio.run(
        handle_message_async(
            message("What is my loan balance?"),
            intent_router=router,
            rag_answer_service=answer_service,
        )
    )

    assert answer_service.calls == []
    assert response == MEMBER_NOT_RECOGNIZED


def test_human_request_does_not_use_rag():
    router = FakeRouter(
        triage(
            needs_member_data=True,
            likely_needs_human=True,
            reasoning="Transaction complaint.",
        )
    )
    answer_service = FakeAnswerService(answer_response())

    response = asyncio.run(
        handle_message_async(
            message("I don't recognize a transaction and want to complain."),
            intent_router=router,
            rag_answer_service=answer_service,
        )
    )

    assert answer_service.calls == []
    assert response == HUMAN_SUPPORT_PLACEHOLDER


def test_whatsapp_route_returns_conversation_response_as_twiml(monkeypatch):
    conversation = AsyncMock(return_value="Grounded response\n\nSource:\n- Demo policy")
    monkeypatch.setattr(whatsapp_route, "handle_message_async", conversation)

    response = TestClient(app).post(
        "/webhooks/whatsapp",
        data={
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+254711111111",
            "Body": "What are the loan requirements?",
            "NumMedia": "0",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert "Grounded response" in response.text
    conversation.assert_awaited_once()


def test_follow_up_interest_rate_routes_to_rag_with_rewritten_query():
    class FakeRewriter:
        def __init__(self, rewritten):
            self.rewritten = rewritten
            self.calls = []

        async def rewrite(self, latest_message, conversation_history=None):
            self.calls.append((latest_message, conversation_history))
            return self.rewritten

    router = FakeRouter(triage())
    answer_service = FakeAnswerService(
        RAGAnswerResponse(
            query="What are the interest rates for the SACCO's loan products?",
            answer="Development loans are ~1% per month, emergency loans are ~2% per month.",
            sources=[
                RAGAnswerSource(
                    document_id="test_loan_rates_terms",
                    chunk_id="c1",
                    title="Loan Rates and Repayment Terms",
                    source="synthetic test data",
                    score=0.92,
                )
            ],
            grounded=True,
        )
    )
    history = InMemoryConversationHistory()
    history.append("+254700000000", "user", "What types of loans do you have?")
    history.append("+254700000000", "assistant", "We have development, emergency, and school-fees loans.")

    rewriter = FakeRewriter("What are the interest rates for the SACCO's loan products?")

    response = asyncio.run(
        handle_message_async(
            message("And what is the interest rate?"),
            intent_router=router,
            rag_answer_service=answer_service,
            history_store=history,
            query_rewriter=rewriter,
        )
    )

    # Verify query rewriter was called with original fragment and conversation history
    assert len(rewriter.calls) == 1
    assert rewriter.calls[0][0] == "And what is the interest rate?"
    assert len(rewriter.calls[0][1]) == 2

    # Verify router classified the REWRITTEN query, not the raw fragment
    assert router.messages == ["What are the interest rates for the SACCO's loan products?"]

    # Verify RAGAnswerService received the rewritten query
    assert answer_service.calls[0]["query"] == "What are the interest rates for the SACCO's loan products?"

    # Verify grounded answer is returned without human escalation
    assert "development loans are ~1%" in response.lower()
    assert HUMAN_SUPPORT_PLACEHOLDER not in response