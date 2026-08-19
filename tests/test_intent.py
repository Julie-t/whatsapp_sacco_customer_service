import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.ai.intent_router import IntentRouter
from app.api.routes import ai as ai_route
from app.main import app
from app.schemas.intent import Intent, IntentResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversation_service import handle_message_async


class FakeLLM:
    def __init__(self, response: str):
        self.response = response

    async def generate(self, messages):
        return self.response


def classify(response: str) -> IntentResult:
    return asyncio.run(IntentRouter(FakeLLM(response)).classify("test"))


@pytest.mark.parametrize(
    ("message", "intent", "language"),
    [
        ("Hello", Intent.GREETING, "en"),
        ("What is compound interest?", Intent.FINANCIAL_EDUCATION, "en"),
        ("What loans do you offer?", Intent.SACCO_INFORMATION, "en"),
        ("I want to save for my daughter's university.", Intent.GOAL_MANAGEMENT, "en"),
        ("I want to talk to a person.", Intent.HUMAN_SUPPORT, "en"),
        ("asdfgh", Intent.UNKNOWN, "unknown"),
        ("Habari", Intent.GREETING, "sw"),
        ("Nifundishe kuhusu savings", Intent.FINANCIAL_EDUCATION, "sw"),
        ("Nataka kujua kuhusu mikopo", Intent.SACCO_INFORMATION, "sw"),
        ("Nataka kuweka akiba kwa ajili ya mtoto wangu", Intent.GOAL_MANAGEMENT, "sw"),
        ("Nataka kuongea na mtu", Intent.HUMAN_SUPPORT, "sw"),
    ],
)
def test_intent_router_validates_supported_intents(message, intent, language):
    result = classify(
        f'{{"intent":"{intent.value}","confidence":0.94,"language":"{language}"}}'
    )
    assert result.intent == intent
    assert result.confidence == 0.94
    assert result.language == language


@pytest.mark.parametrize(
    "response",
    [
        "This is financial education.",
        '{"intent":"something_not_supported","confidence":2.7}',
        '{"intent":"financial_education",',
        '{"intent":"financial_education","confidence":0.8,"language":"fr"}',
    ],
)
def test_malformed_or_unsupported_output_returns_safe_fallback(response):
    assert classify(response) == IntentResult.fallback()


def test_intent_endpoint_uses_router_and_returns_schema():
    client = TestClient(app)
    mocked_result = IntentResult(
        intent=Intent.GOAL_MANAGEMENT, confidence=0.95, language="en"
    )
    original = ai_route._intent_router.classify
    ai_route._intent_router.classify = AsyncMock(return_value=mocked_result)
    try:
        response = client.post(
            "/ai/intent", json={"message": "I want to save for university"}
        )
    finally:
        ai_route._intent_router.classify = original

    assert response.status_code == 200
    assert response.json() == mocked_result.model_dump(mode="json")


def test_conversation_routes_intent_to_placeholder():
    router = AsyncMock()
    router.classify.return_value = IntentResult(
        intent=Intent.FINANCIAL_EDUCATION, confidence=0.9, language="en"
    )
    message = IncomingWhatsAppMessage(
        from_number="+254700000000", body="What is compound interest?"
    )

    response = asyncio.run(handle_message_async(message, router))

    router.classify.assert_awaited_once_with("What is compound interest?")
    assert "coming later" in response