import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_service import handle_message


client = TestClient(app)


def _post_whatsapp(body: str, num_media: str = "0"):
    return client.post(
        "/webhooks/whatsapp",
        data={
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+254711111111",
            "Body": body,
            "NumMedia": num_media,
        },
    )


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_greeting_hello_returns_welcome():
    response = _post_whatsapp("Hello")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    body = response.text
    assert "Karibu" in body
    assert "How can I help you today?" in body
    assert "Financial education" not in body
    assert "1️⃣" not in body


def test_greeting_habari_returns_welcome():
    response = _post_whatsapp("Habari")
    assert response.status_code == 200
    assert "Karibu" in response.text
    assert "Financial education" not in response.text


def test_greeting_good_morning_returns_welcome():
    response = _post_whatsapp("Good morning")
    assert response.status_code == 200
    assert "Karibu" in response.text
    assert "Financial education" not in response.text


def test_menu_help_returns_welcome():
    response = _post_whatsapp("HELP")
    assert response.status_code == 200
    assert "Financial education" in response.text
    assert "SACCO information" in response.text
    assert "financial goals" in response.text.lower()
    assert "SACCO" in response.text


def test_menu_help_lowercase_returns_welcome():
    response = _post_whatsapp("help")
    assert response.status_code == 200
    assert "Financial education" in response.text
    assert "SACCO information" in response.text
    assert "financial goals" in response.text.lower()
    assert "SACCO" in response.text


def test_unknown_message_returns_fallback():
    response = _post_whatsapp("Something random")
    assert response.status_code == 200
    assert "may need staff assistance" in response.text


def test_whitespace_normalization():
    response = _post_whatsapp("   hello   ")
    assert response.status_code == 200
    assert "Karibu" in response.text
    assert "Financial education" not in response.text


def test_missing_body_returns_fallback():
    response = client.post(
        "/webhooks/whatsapp",
        data={
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+254711111111",
            "NumMedia": "0",
        },
    )
    assert response.status_code == 200
    assert "AI assistant capabilities are being introduced" in response.text


def test_route_returns_twiml_xml():
    response = _post_whatsapp("Hello")
    assert response.status_code == 200
    assert '<?xml version="1.0" encoding="UTF-8"?>' in response.text
    assert "<Response>" in response.text
    assert "<Message>" in response.text


def test_conversation_service_greeting():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="Hello")
    response = handle_message(message)
    assert "Karibu" in response
    assert "How can I help you today?" in response
    assert "Financial education" not in response


def test_conversation_service_menu():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="help")
    response = handle_message(message)
    assert "SACCO information" in response
    assert "Financial education" in response
    assert "financial goals" in response.lower()


def test_conversation_service_unknown():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="random")
    response = handle_message(message)
    assert "AI assistant capabilities are being introduced" in response


def test_conversation_service_empty_body_without_media():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="")
    response = handle_message(message)
    assert "AI assistant capabilities are being introduced" in response


def test_conversation_service_empty_body_with_media():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="", num_media="1")
    response = handle_message(message)
    assert "media messages" in response.lower()


@pytest.mark.anyio
async def test_goal_query_not_interpreted_as_greeting():
    from unittest.mock import AsyncMock, MagicMock
    from app.schemas.intent import RequestTriageResult
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async

    msg = IncomingWhatsAppMessage(from_number="+254799000001", body="I want to save for my business")
    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=True,
            likely_needs_human=False,
            reasoning="Goal coaching query",
        )
    )
    history = InMemoryConversationHistory()
    resp = await handle_message_async(msg, intent_router=router, history_store=history)
    assert "Karibu! I'm your SACCO financial companion" not in resp
    assert "Financial education" not in resp
    assert "save" in resp.lower() or "amount" in resp.lower() or "goal" in resp.lower()


@pytest.mark.anyio
async def test_rag_query_not_greeting_or_menu():
    from unittest.mock import AsyncMock, MagicMock
    from app.schemas.intent import RequestTriageResult
    from app.schemas.rag_answer import RAGAnswerResponse, RAGAnswerSource
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async

    msg = IncomingWhatsAppMessage(from_number="+254799000002", body="What documents do I need for a loan?")
    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=False,
            likely_needs_human=False,
            reasoning="RAG inquiry",
        )
    )
    rag_service = MagicMock()
    rag_service.answer = AsyncMock(
        return_value=RAGAnswerResponse(
            query="What documents do I need for a loan?",
            answer="You need your national ID, payslips, and a completed loan application form.",
            sources=[RAGAnswerSource(document_id="loan_docs", chunk_id="c1", title="Loan Docs", source="kb", score=0.95)],
            grounded=True,
        )
    )
    history = InMemoryConversationHistory()
    resp = await handle_message_async(msg, intent_router=router, rag_answer_service=rag_service, history_store=history)
    assert "Karibu! I'm your SACCO financial companion" not in resp
    assert "Financial education" not in resp
    assert "payslips" in resp.lower() or "loan application" in resp.lower()


@pytest.mark.anyio
async def test_member_data_query_not_greeting_or_menu():
    from unittest.mock import AsyncMock, MagicMock
    from app.schemas.intent import RequestTriageResult
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async

    msg = IncomingWhatsAppMessage(from_number="+254799000003", body="What is my balance?")
    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=True,
            is_goal_related=False,
            likely_needs_human=False,
            reasoning="Account balance inquiry",
        )
    )
    member_service = MagicMock()
    member_service.get_member_snapshot.return_value = None
    history = InMemoryConversationHistory()
    resp = await handle_message_async(msg, intent_router=router, member_service=member_service, history_store=history)
    assert "Karibu! I'm your SACCO financial companion" not in resp
    assert "Financial education" not in resp
    assert "member" in resp.lower() or "verify" in resp.lower()


@pytest.mark.anyio
async def test_fraud_query_not_greeting_or_menu():
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async

    msg = IncomingWhatsAppMessage(
        from_number="+254799000004",
        body="I see an unrecognized transaction, someone stole my money, this is fraud!",
    )
    history = InMemoryConversationHistory()
    resp = await handle_message_async(msg, history_store=history)
    assert "Karibu! I'm your SACCO financial companion" not in resp
    assert "Financial education" not in resp
    assert "escalated" in resp.lower() or "ticket" in resp.lower() or "security" in resp.lower()


@pytest.mark.anyio
async def test_end_to_end_greeting_help_and_goal_flow():
    """Verify sequence:
    1. 'Hello' -> friendly greeting only, no menu
    2. 'HELP' -> capability menu
    3. 'I want to save KSh 300,000 for my business' -> natural goal flow, no menu
    """
    from unittest.mock import AsyncMock, MagicMock
    from app.schemas.intent import RequestTriageResult
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async
    from app.services.goals.goal_service import GoalService
    from app.services.members.member_service import MemberDataService
    from app.database.in_memory_member_repository import InMemoryMemberRepository
    from app.database.in_memory_goal_repository import InMemoryGoalRepository
    from app.models.member import Member

    mem_repo = InMemoryMemberRepository()
    mem_repo.add_member(
        Member(id="m_test", phone_hash="phash", display_name="Grace Wanjiku"),
        "+254712345678",
    )
    member_svc = MemberDataService(repository=mem_repo)
    goal_svc = GoalService(repository=InMemoryGoalRepository())
    history = InMemoryConversationHistory()

    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=True,
            likely_needs_human=False,
            reasoning="Goal coaching query",
        )
    )

    # 1. Hello
    msg_hello = IncomingWhatsAppMessage(from_number="+254712345678", body="Hello")
    resp_hello = await handle_message_async(msg_hello, history_store=history)
    assert "Karibu" in resp_hello
    assert "How can I help you today?" in resp_hello
    assert "Financial education" not in resp_hello
    assert "1️⃣" not in resp_hello

    # 2. HELP
    msg_help = IncomingWhatsAppMessage(from_number="+254712345678", body="HELP")
    resp_help = await handle_message_async(msg_help, history_store=history)
    assert "Financial education" in resp_help
    assert "SACCO information" in resp_help
    assert "financial goals" in resp_help.lower()
    assert "SACCO" in resp_help

    # 3. I want to save KSh 300,000 for my business
    msg_goal = IncomingWhatsAppMessage(
        from_number="+254712345678",
        body="I want to save KSh 300,000 for my business.",
    )
    resp_goal = await handle_message_async(
        msg_goal,
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "Financial education" not in resp_goal
    assert "1️⃣" not in resp_goal
    assert "Karibu! I'm your SACCO financial companion. How can I help you today?" not in resp_goal
    # Prompts for target timeline/date or records goal
    assert any(w in resp_goal.lower() for w in ("save", "target", "date", "month", "goal", "300,000", "300000"))


@pytest.mark.anyio
async def test_whatsapp_capability_inquiry_returns_capabilities_not_goal_or_menu():
    """Verify that asking whether the assistant can help on WhatsApp confirms capability,
    does NOT trigger a goal prompt, and does NOT force a menu.
    """
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async

    history = InMemoryConversationHistory()
    # Populate history with an existing savings goal turn to test resilience against false hijacking
    history.append("+254799887766", "user", "I want to save 200k")
    history.append("+254799887766", "assistant", "Goal set: 200k target.")

    msg = IncomingWhatsAppMessage(
        from_number="+254799887766",
        body="Habari, I have been a member for some time but I normally call customer care when I have questions. Can you help me here on WhatsApp?",
    )
    resp = await handle_message_async(msg, history_store=history)

    # Must NOT be hijacked into goal clarification
    assert "That sounds like a great goal!" not in resp
    assert "How much would you like to save" not in resp
    # Must NOT display legacy numbered menu
    assert "1. SACCO information" not in resp
    assert "1️⃣" not in resp
    # Must confirm WhatsApp capability warmly
    assert "WhatsApp" in resp or "whatsapp" in resp.lower()
    assert "Karibu" in resp or "help" in resp.lower()


@pytest.mark.anyio
async def test_words_with_no_substring_not_hijacked_as_goal():
    """Words like 'normally', 'notice', 'nothing', 'not' must not trigger substring match on 'no'."""
    from unittest.mock import AsyncMock, MagicMock
    from app.schemas.intent import RequestTriageResult
    from app.services.conversations.conversation_history import InMemoryConversationHistory
    from app.services.conversations.conversation_service import handle_message_async

    history = InMemoryConversationHistory()
    history.append("+254799112233", "user", "What is my goal progress?")
    history.append("+254799112233", "assistant", "Your goal is on track.")

    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=False,
            likely_needs_human=True,
            reasoning="Vague question needing staff assistance.",
        )
    )

    msg = IncomingWhatsAppMessage(
        from_number="+254799112233",
        body="I normally speak to someone in the office.",
    )
    resp = await handle_message_async(msg, intent_router=router, history_store=history)

    # Must NOT trigger goal clarification
    assert "That sounds like a great goal!" not in resp
    assert "How much would you like to save" not in resp


