import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.ai.intent_router import IntentRouter
from app.ai.prompts import ROUTER_PROMPT
from app.api.routes import ai as ai_route
from app.main import app
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversation_service import (
    GENERAL_ASSISTANCE_PLACEHOLDER,
    HUMAN_SUPPORT_PLACEHOLDER,
    MEMBER_DATA_PLACEHOLDER,
    handle_message_async,
)


class FakeLLM:
    def __init__(self, response: str):
        self.response = response
        self.messages = None

    async def generate(self, messages):
        self.messages = messages
        return self.response


def triage(response: str) -> RequestTriageResult:
    return asyncio.run(IntentRouter(FakeLLM(response)).classify("test"))


def test_router_uses_open_ended_triage_prompt():
    llm = FakeLLM(
        '{"language":"en","needs_member_data":false,'
        '"likely_needs_human":false,"reasoning":"General education question."}'
    )

    asyncio.run(IntentRouter(llm).classify("What is compound interest?"))

    assert llm.messages[0] == {"role": "system", "content": ROUTER_PROMPT}


def test_general_financial_question():
    result = triage(
        '{"language":"en","needs_member_data":false,'
        '"likely_needs_human":false,"reasoning":"General financial education."}'
    )

    assert result.language == "en"
    assert result.needs_member_data is False
    assert result.likely_needs_human is False


def test_loan_requirements_are_general_assistance():
    result = triage(
        '{"language":"en","needs_member_data":false,'
        '"likely_needs_human":false,"reasoning":"General SACCO loan information."}'
    )

    assert result.needs_member_data is False
    assert result.likely_needs_human is False


def test_router_accepts_json_code_fence():
    result = triage(
        '```json\n{"language":"en","needs_member_data":false,'
        '"likely_needs_human":false,"reasoning":"General education."}\n```'
    )

    assert result.language == "en"
    assert result.likely_needs_human is False


def test_member_specific_question():
    result = triage(
        '{"language":"sw","needs_member_data":true,'
        '"likely_needs_human":false,"reasoning":"The member asks for loan data."}'
    )

    assert result.language == "sw"
    assert result.needs_member_data is True
    assert result.likely_needs_human is False


def test_human_escalation_in_kiswahili():
    result = triage(
        '{"language":"sw","needs_member_data":true,'
        '"likely_needs_human":true,"reasoning":"The member reports a transaction complaint."}'
    )

    assert result.language == "sw"
    assert result.needs_member_data is True
    assert result.likely_needs_human is True


def test_english_complaint():
    result = triage(
        '{"language":"en","needs_member_data":true,'
        '"likely_needs_human":true,"reasoning":"The member does not recognize a transaction."}'
    )

    assert result.language == "en"
    assert result.needs_member_data is True
    assert result.likely_needs_human is True


def test_mixed_language():
    result = triage(
        '{"language":"mixed","needs_member_data":true,'
        '"likely_needs_human":false,"reasoning":"The message mixes English and Kiswahili."}'
    )

    assert result.language == "mixed"


def test_malformed_or_unsupported_output_returns_safe_fallback():
    responses = [
        "This is a member data request.",
        '{"language":"fr","needs_member_data":false,'
        '"likely_needs_human":false,"reasoning":"Unknown language."}',
        '{"language":"en","needs_member_data":false}',
    ]

    for response in responses:
        assert triage(response) == RequestTriageResult.fallback()


def test_intent_endpoint_returns_triage_schema():
    client = TestClient(app)
    mocked_result = RequestTriageResult(
        language="sw",
        needs_member_data=True,
        likely_needs_human=False,
        reasoning="The member asks for their own loan information.",
    )
    original = ai_route._intent_router.classify
    ai_route._intent_router.classify = AsyncMock(return_value=mocked_result)
    try:
        response = client.post(
            "/ai/intent", json={"message": "Nataka kujua loan balance yangu."}
        )
    finally:
        ai_route._intent_router.classify = original

    assert response.status_code == 200
    assert response.json() == mocked_result.model_dump(mode="json")
    assert "intent" not in response.json()
    assert "confidence" not in response.json()


def test_conversation_routes_human_support_first():
    router = AsyncMock()
    router.classify.return_value = RequestTriageResult(
        language="en",
        needs_member_data=True,
        likely_needs_human=True,
        reasoning="The member reports fraud.",
    )
    message = IncomingWhatsAppMessage(
        from_number="+254700000000", body="I do not recognize a transaction."
    )

    response = asyncio.run(handle_message_async(message, router))

    assert response == HUMAN_SUPPORT_PLACEHOLDER


def test_conversation_routes_member_data_request():
    router = AsyncMock()
    router.classify.return_value = RequestTriageResult(
        language="sw",
        needs_member_data=True,
        likely_needs_human=False,
        reasoning="The member asks for a balance.",
    )
    message = IncomingWhatsAppMessage(
        from_number="+254700000000", body="Nataka kujua loan balance yangu."
    )

    response = asyncio.run(handle_message_async(message, router))

    assert response == MEMBER_DATA_PLACEHOLDER


def test_conversation_routes_general_assistance():
    router = AsyncMock()
    router.classify.return_value = RequestTriageResult(
        language="en",
        needs_member_data=False,
        likely_needs_human=False,
        reasoning="The member asks a general question.",
    )
    message = IncomingWhatsAppMessage(
        from_number="+254700000000", body="What is compound interest?"
    )

    response = asyncio.run(handle_message_async(message, router))

    assert response == GENERAL_ASSISTANCE_PLACEHOLDER