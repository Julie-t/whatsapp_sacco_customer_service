"""End-to-End WhatsApp Authentication & Security Flow Tests (System 12.1, 12.2, 12.22, 12.27)."""

import pytest
from unittest.mock import MagicMock, patch

from app.config.settings import settings
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.database.in_memory_member_auth_repository import InMemoryMemberAuthRepository
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.models.member import Member, MemberAccount, MemberLoan
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_service import handle_message_async
from app.services.members.member_auth_service import MemberAuthService
from app.services.members.member_service import MemberDataService


@pytest.fixture
def auth_components():
    member_repo = InMemoryMemberRepository()
    member_repo.add_member(
        Member(id="mem_001", phone_hash="", display_name="Edna Maina", sacco_id="demo_sacco"),
        phone_number="+254700000001",
        accounts=[
            MemberAccount(id=1, member_id="mem_001", account_type="savings", account_name="Savings", balance=32450.0),
        ],
        loans=[
            MemberLoan(
                id=1,
                member_id="mem_001",
                loan_type="development",
                principal=200000.0,
                balance_remaining=125000.0,
                monthly_instalment=4500.0,
                interest_rate=12.0,
                term_months=48,
                months_paid=18,
            ),
        ],
    )
    auth_repo = InMemoryMemberAuthRepository()
    m_svc = MemberDataService(repository=member_repo)
    auth_svc = MemberAuthService(auth_repo=auth_repo, member_service=m_svc, session_ttl_minutes=15)
    return m_svc, auth_svc


from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.anyio
async def test_whatsapp_auth_gated_balance_flow(auth_components):
    m_svc, auth_svc = auth_components
    history = InMemoryConversationHistory()

    mock_router = MagicMock()
    mock_router.classify = AsyncMock(
        return_value=RequestTriageResult(
            likely_needs_human=False,
            needs_member_data=True,
            is_goal_related=False,
            language="en",
            reasoning="Inquiry regarding member balance.",
        )
    )

    phone = "+254700000001"

    # 1. Ask for balance with REQUIRE_MEMBER_AUTH enabled
    with patch.object(settings, "REQUIRE_MEMBER_AUTH", True):
        msg1 = IncomingWhatsAppMessage(
            from_number=phone,
            to_number="+14155238886",
            body="What is my balance?",
        )
        res1 = await handle_message_async(
            msg1,
            intent_router=mock_router,
            history_store=history,
            member_service=m_svc,
            auth_service=auth_svc,
        )

        assert "verification code is" in res1
        # Extract code from prompt in demo mode
        import re
        code_match = re.search(r"\b(\d{6})\b", res1)
        assert code_match is not None
        otp_code = code_match.group(1)

        # 2. Reply with 6-digit OTP
        msg2 = IncomingWhatsAppMessage(
            from_number=phone,
            to_number="+14155238886",
            body=otp_code,
        )
        res2 = await handle_message_async(
            msg2,
            intent_router=mock_router,
            history_store=history,
            member_service=m_svc,
            auth_service=auth_svc,
        )
        assert "verified successfully" in res2

        # 3. Ask for balance again now that session is active
        msg3 = IncomingWhatsAppMessage(
            from_number=phone,
            to_number="+14155238886",
            body="What is my balance?",
        )
        res3 = await handle_message_async(
            msg3,
            intent_router=mock_router,
            history_store=history,
            member_service=m_svc,
            auth_service=auth_svc,
        )
        assert "32,450" in res3
        assert "savings" in res3.lower()


@pytest.mark.anyio
async def test_whatsapp_fraud_escalation_flow(auth_components):
    m_svc, auth_svc = auth_components
    history = InMemoryConversationHistory()

    msg = IncomingWhatsAppMessage(
        from_number="+254700000001",
        to_number="+14155238886",
        body="I see an unrecognized transaction of 10,000 on my account, this is fraud!",
    )

    res = await handle_message_async(
        msg,
        history_store=history,
        member_service=m_svc,
        auth_service=auth_svc,
    )

    assert "unrecognized transaction or security dispute has been escalated with urgent priority" in res
    assert "Ticket #" in res
