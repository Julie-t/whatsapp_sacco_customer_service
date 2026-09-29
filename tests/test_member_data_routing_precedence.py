"""Acceptance and regression tests for member-data routing precedence over goal context."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.member import Member, MemberAccount, MemberLoan
from app.schemas.intent import RequestTriageResult
from app.schemas.message import ConversationTurn, IncomingWhatsAppMessage
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.services.conversations.conversation_service import handle_message_async
from app.services.members.member_service import MemberDataService
from app.ai.intent_router import classify_deterministic, IntentRouter
from app.ai.rag.query_rewriter import QueryRewriter


@pytest.fixture
def mock_member_service():
    """Mock member data service returning a member with active loan and savings."""
    svc = MagicMock(spec=MemberDataService)
    profile = MagicMock(id="member_001", display_name="Peter Mwangi")
    svc.resolve_member.return_value = profile

    from app.schemas.member import AccountSummary, LoanSummary, MemberDataResponse, MemberProfile
    snapshot = MemberDataResponse(
        profile=MemberProfile(
            id="member_001",
            display_name="Peter Mwangi",
            preferred_language="en",
            knowledge_level="beginner",
            sacco_id="sacco_demo",
        ),
        accounts=[
            AccountSummary(account_type="savings", account_name="Regular Savings", balance=80000.0),
            AccountSummary(account_type="shares", account_name="Share Capital", balance=15000.0),
        ],
        loans=[
            LoanSummary(
                loan_type="development",
                principal=200000.0,
                balance_remaining=125000.0,
                interest_rate=12.0,
                monthly_instalment=4500.0,
                months_paid=18,
                term_months=48,
                status="active",
            )
        ],
    )
    svc.get_member_snapshot.return_value = snapshot
    return svc


@pytest.mark.parametrize(
    "query",
    [
        "What is my balance?",
        "What is my loan balance?",
        "When is my next payment?",
        "How much do I still owe?",
    ],
)
def test_deterministic_pre_router_identifies_member_data(query):
    """Deterministic pre-router must immediately recognize personal account inquiries."""
    result = classify_deterministic(query)
    assert result is not None
    assert result.needs_member_data is True
    assert result.is_goal_related is False
    assert result.likely_needs_human is False


def test_query_rewriter_treats_member_data_as_self_contained():
    """Query rewriter must treat payment and balance checks as self-contained."""
    queries = [
        "When is my next payment?",
        "What is my balance?",
        "What is my loan balance?",
        "How much do I still owe?",
        "What is my next instalment?",
    ]
    for q in queries:
        assert QueryRewriter._is_self_contained(q) is True, f"{q} should be self-contained"


@pytest.mark.anyio
async def test_member_data_takes_precedence_over_prior_goal_history(mock_member_service):
    """CRITICAL REGRESSION TEST:

    Given prior turns where a business savings goal was discussed and created,
    when the member next asks: 'When is my next payment?'
    the system MUST return member-data loan details, and NEVER the goal creation prompt.
    """
    history = InMemoryConversationHistory()
    phone = "+254712345678"

    # Prior goal context
    history.append(phone, "user", "I want to save KSh 300,000 for my business.")
    history.append(
        phone,
        "assistant",
        "Goal set: Business Expansion!\nTarget amount: KSh 300,000\nTarget date: September 2027\n(demo data)",
    )

    msg = IncomingWhatsAppMessage(from_number=phone, body="When is my next payment?")
    response = await handle_message_async(
        msg,
        history_store=history,
        member_service=mock_member_service,
    )

    # Must NOT swallow into goal creation/clarification flow
    assert "That sounds like a great goal" not in response
    assert "How much would you like to save" not in response

    # Must contain loan / payment member data
    assert "development" in response.lower()
    assert "125,000" in response
    assert "4,500" in response


@pytest.mark.anyio
async def test_acceptance_routing_matrix(mock_member_service):
    """Verify routing matrix behavior across core user inquiry types."""
    history = InMemoryConversationHistory()
    phone = "+254712345678"

    # 1. "What is my balance?" -> member-data
    msg_bal = IncomingWhatsAppMessage(from_number=phone, body="What is my balance?")
    resp_bal = await handle_message_async(msg_bal, history_store=history, member_service=mock_member_service)
    assert "regular savings: ksh 80,000" in resp_bal.lower()
    assert "That sounds like a great goal" not in resp_bal

    # 2. "What is my loan balance?" -> member-data
    msg_loan = IncomingWhatsAppMessage(from_number=phone, body="What is my loan balance?")
    resp_loan = await handle_message_async(msg_loan, history_store=history, member_service=mock_member_service)
    assert "125,000 remaining" in resp_loan
    assert "That sounds like a great goal" not in resp_loan

    # 3. "How much do I still owe?" -> member-data
    msg_owe = IncomingWhatsAppMessage(from_number=phone, body="How much do I still owe?")
    resp_owe = await handle_message_async(msg_owe, history_store=history, member_service=mock_member_service)
    assert "125,000 remaining" in resp_owe
    assert "That sounds like a great goal" not in resp_owe

    # 4. "What if I save 15,000 per month?" -> goal/scenario
    # Set active goal on mock goal service
    mock_goal_svc = MagicMock()
    mock_active_goal = MagicMock(
        id="goal_123",
        name="Business Expansion",
        target_amount=300000.0,
        current_amount=0.0,
        contribution_amount=10000.0,
    )
    mock_goal_svc.get_active_goal.return_value = mock_active_goal
    from datetime import date
    from app.schemas.goal import ScenarioAnalysisResult
    mock_goal_svc.calculate_scenario.return_value = ScenarioAnalysisResult(
        current_monthly_contribution=10000.0,
        proposed_monthly_contribution=15000.0,
        amount_remaining=300000.0,
        current_projected_months=30,
        proposed_projected_months=20,
        current_projected_date=date(2028, 9, 1),
        proposed_projected_date=date(2027, 11, 1),
        months_difference=10,
        narrative_summary="Saving KSh 15,000 per month will help you reach your goal 10 months earlier.",
    )

    msg_scen = IncomingWhatsAppMessage(from_number=phone, body="What if I save 15,000 per month?")
    resp_scen = await handle_message_async(
        msg_scen,
        history_store=history,
        member_service=mock_member_service,
        goal_service=mock_goal_svc,
    )
    assert "Scenario analysis" in resp_scen or "15,000" in resp_scen

    # 5. "Help me save 300,000 for my business." -> goal creation/clarification
    msg_goal = IncomingWhatsAppMessage(from_number=phone, body="Help me save 300,000 for my business.")
    mock_goal_extractor = MagicMock()
    from app.schemas.goal import GoalExtractionResult
    mock_goal_extractor.extract_async = AsyncMock(
        return_value=GoalExtractionResult(
            target_amount=300000.0,
            target_date=None,
            needs_clarification=True,
            missing_fields=["target_date"],
        )
    )
    resp_goal = await handle_message_async(
        msg_goal,
        history_store=history,
        member_service=mock_member_service,
        goal_service=mock_goal_svc,
        goal_extractor=mock_goal_extractor,
    )
    assert "When would you like to reach this goal" in resp_goal or "goal" in resp_goal.lower()
