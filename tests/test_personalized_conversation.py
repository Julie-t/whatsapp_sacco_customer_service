"""Integration test for personalized education in conversation flow."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.database.in_memory_personalization_repository import InMemoryPersonalizationHistoryRepository
from app.models.goal import ContributionFrequency, FinancialGoal, GoalStatus, GoalType
from app.models.member import Member
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.services.conversations.conversation_service import handle_message_async
from app.services.goals.goal_service import GoalService
from app.services.members.member_service import MemberDataService
from app.services.education.personalization_context_builder import PersonalizationContextBuilder
from app.services.education.personalized_education_service import (
    PersonalizedEducationResponse,
    PersonalizedEducationService,
)


@pytest.fixture
def mock_router():
    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=False,
            likely_needs_human=False,
            reasoning="Financial education inquiry.",
        )
    )
    return router


@pytest.fixture
def mock_edu_service():
    service = MagicMock(spec=PersonalizedEducationService)
    service.explain = AsyncMock(
        return_value=PersonalizedEducationResponse(
            answer="Since you are saving for your University Fund, compound interest helps you earn returns on your savings. (demo data)",
            topic="compound_interest",
            knowledge_level_applied="beginner",
            goal_context_applied="University Fund",
            language_applied="en",
            sources=["test_compound_interest"],
            is_demo=True,
        )
    )
    return service


@pytest.mark.anyio
async def test_personalized_education_whatsapp_flow(mock_router, mock_edu_service):
    history = InMemoryConversationHistory()
    msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254700000001",
        to_number="whatsapp:+14155238886",
        body="How can compound interest help my goal?",
    )

    response = await handle_message_async(
        msg,
        intent_router=mock_router,
        history_store=history,
        education_service=mock_edu_service,
    )

    assert "University Fund" in response
    assert "compound interest" in response
    assert "*" not in response
    assert "(demo data)" in response
    assert mock_edu_service.explain.called


@pytest.mark.anyio
async def test_whatsapp_feedback_flow():
    from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
    from app.models.engagement import ProactiveNotification, NotificationType, NotificationStatus, FeedbackRating
    from app.services.proactive.member_feedback_service import MemberFeedbackService

    eng_repo = InMemoryEngagementRepository()
    eng_repo.record_notification(
        ProactiveNotification(
            id="notif_flow_01",
            member_id="member_001",
            notification_type=NotificationType.SCHEDULED_EDUCATION,
            content_id="budgeting",
            message_body="Tip on budgeting...",
            status=NotificationStatus.SENT,
        )
    )
    feedback_svc = MemberFeedbackService(engagement_repo=eng_repo)

    msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254110923440",
        to_number="whatsapp:+14155238886",
        body="HELPFUL",
    )

    response = await handle_message_async(
        msg,
        feedback_service=feedback_svc,
    )

    assert "Asante sana" in response
    latest = eng_repo.get_latest_notification_for_member("member_001")
    assert latest.feedback == FeedbackRating.HELPFUL


@pytest.mark.anyio
async def test_whatsapp_more_flow():
    from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
    from app.models.engagement import ProactiveNotification, NotificationType, NotificationStatus
    from app.services.proactive.member_feedback_service import MemberFeedbackService

    eng_repo = InMemoryEngagementRepository()
    eng_repo.record_notification(
        ProactiveNotification(
            id="notif_flow_02",
            member_id="member_001",
            notification_type=NotificationType.SCHEDULED_EDUCATION,
            content_id="compound_interest",
            message_body="Tip on compound interest...",
            status=NotificationStatus.SENT,
        )
    )
    feedback_svc = MemberFeedbackService(engagement_repo=eng_repo)

    msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254110923440",
        to_number="whatsapp:+14155238886",
        body="MORE",
    )

    response = await handle_message_async(
        msg,
        feedback_service=feedback_svc,
    )

    assert "KSh 5,000 monthly" in response
    assert "Year 2" in response


@pytest.mark.anyio
async def test_goal_coaching_and_advisory_flow():
    mem_repo = InMemoryMemberRepository()
    mem = Member(
        id="mem_001",
        phone_hash="dummy",
        display_name="Wanjiku Kamau",
        preferred_language="en",
    )
    mem_repo.add_member(mem, "+254700000001")
    member_svc = MemberDataService(repository=mem_repo)
    goal_repo = InMemoryGoalRepository()
    goal_svc = GoalService(repository=goal_repo)
    history = InMemoryConversationHistory()

    mock_router = MagicMock()
    async def mock_classify(text):
        lower = text.lower()
        if "what savings account" in lower:
            return RequestTriageResult(
                language="en",
                needs_member_data=False,
                is_goal_related=True,
                is_education_related=True,
                likely_needs_human=False,
                reasoning="Account inquiry for goal",
            )
        elif "500000" in lower or "500,000" in lower or "school fees" in lower:
            return RequestTriageResult(
                language="en",
                needs_member_data=False,
                is_goal_related=True,
                is_education_related=False,
                likely_needs_human=False,
                reasoning="Goal setting request",
            )
        elif "stocks or shares" in lower:
            return RequestTriageResult(
                language="en",
                needs_member_data=False,
                is_goal_related=True,
                is_education_related=True,
                likely_needs_human=False,
                reasoning="Educational product inquiry for existing goal",
            )
        return RequestTriageResult.fallback()
    mock_router.classify = AsyncMock(side_effect=mock_classify)

    mock_edu = MagicMock(spec=PersonalizedEducationService)
    async def mock_explain(member_id_or_phone, query, **kwargs):
        lower = query.lower()
        if "savings account" in lower:
            return PersonalizedEducationResponse(
                answer="SACCO savings accounts like FOSA Savings or Target Savings earn steady interest to grow your goal safely. (demo data)",
                topic="savings_accounts",
                knowledge_level_applied="beginner",
                goal_context_applied=None,
                language_applied="en",
                sources=["savings_policy"],
                is_demo=True,
            )
        elif "stocks or shares" in lower:
            return PersonalizedEducationResponse(
                answer="SACCO members own shares which pay dividends, while regular deposits fund goals like School Fees. Unlike stock trading, SACCO shares represent member equity. (demo data)",
                topic="sacco_shares",
                knowledge_level_applied="beginner",
                goal_context_applied="Education / School Fees",
                language_applied="en",
                sources=["share_capital_policy"],
                is_demo=True,
            )
    mock_edu.explain = AsyncMock(side_effect=mock_explain)

    # Turn 1: Advisory question about savings accounts for goal
    msg1 = IncomingWhatsAppMessage(
        from_number="+254700000001",
        to_number="+254711111111",
        body="what savings account is best for my goal",
    )
    resp1 = await handle_message_async(
        msg1,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
        education_service=mock_edu,
    )
    assert "savings accounts" in resp1.lower()
    assert "Goal set:" not in resp1
    assert "How much would you like to save" not in resp1

    # Turn 2: Setting goal
    msg2 = IncomingWhatsAppMessage(
        from_number="+254700000001",
        to_number="+254711111111",
        body="500000 for school fees for my daughter in 20 months",
    )
    resp2 = await handle_message_async(
        msg2,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
        education_service=mock_edu,
    )
    assert "Goal set:" in resp2
    assert "500,000" in resp2
    active_g = goal_svc.get_active_goal("mem_001")
    assert active_g is not None
    assert active_g.target_amount == 500000.0

    # Turn 3: Product question anchored to goal - must NOT trigger goal creation or repeat "Goal set:"
    msg3 = IncomingWhatsAppMessage(
        from_number="+254700000001",
        to_number="+254711111111",
        body="are there stocks or shares I can buy to supplement this goal",
    )
    resp3 = await handle_message_async(
        msg3,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
        education_service=mock_edu,
    )
    assert "Goal set:" not in resp3
    assert "dividends" in resp3.lower() or "shares" in resp3.lower()


@pytest.mark.anyio
async def test_small_business_expansion_goal_flow():
    mem_repo = InMemoryMemberRepository()
    mem = Member(
        id="mem_002",
        phone_hash="dummy",
        display_name="Juma Otieno",
        preferred_language="en",
    )
    mem_repo.add_member(mem, "+254700000002")
    member_svc = MemberDataService(repository=mem_repo)
    goal_repo = InMemoryGoalRepository()
    goal_svc = GoalService(repository=goal_repo)
    history = InMemoryConversationHistory()

    mock_router = MagicMock()
    mock_router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=True,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="Goal creation statement",
        )
    )

    # Turn 1: Vague statement asking for help to expand small business
    msg1 = IncomingWhatsAppMessage(
        from_number="+254700000002",
        to_number="+254711111111",
        body="I want to save some money to expand my small business. Can you help me?",
    )
    resp1 = await handle_message_async(
        msg1,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    # Should ask for missing amount & date
    assert "How much would you like to save" in resp1

    # Turn 2: Natural goal statement with raise and by next year
    msg2 = IncomingWhatsAppMessage(
        from_number="+254700000002",
        to_number="+254711111111",
        body="I want to raise KSh 300,000 for my shop by next year.",
    )
    resp2 = await handle_message_async(
        msg2,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "Goal set:" in resp2
    assert "300,000" in resp2
    assert "Business Growth" in resp2
    active_g = goal_svc.get_active_goal("mem_002")
    assert active_g is not None
    assert active_g.target_amount == 300000.0
    assert active_g.goal_type == GoalType.BUSINESS


@pytest.mark.anyio
async def test_goal_followup_balance_update_and_scenario_flow():
    mem_repo = InMemoryMemberRepository()
    mem = Member(
        id="mem_003",
        phone_hash="dummy3",
        display_name="Faith Muthoni",
        preferred_language="en",
    )
    mem_repo.add_member(mem, "+254700000003")
    member_svc = MemberDataService(repository=mem_repo)
    goal_repo = InMemoryGoalRepository()
    goal_svc = GoalService(repository=goal_repo)
    history = InMemoryConversationHistory()

    mock_router = MagicMock()
    async def mock_classify(text, context=None):
        lower = text.lower()
        if "human agent" in lower or "dispute" in lower:
            return RequestTriageResult(
                language="en",
                needs_member_data=False,
                is_goal_related=False,
                is_education_related=False,
                likely_needs_human=True,
                reasoning="Human agent requested",
            )
        # In real runtime, router sees context or heuristic flags goal
        return RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=True,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="Goal flow",
        )
    mock_router.classify = AsyncMock(side_effect=mock_classify)

    # Turn 1: Set goal
    msg1 = IncomingWhatsAppMessage(
        from_number="+254700000003",
        to_number="+254711111111",
        body="I want to save KSh 300,000 for school fees in 2 years.",
    )
    resp1 = await handle_message_async(
        msg1,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "Goal set:" in resp1
    assert "300,000" in resp1

    # Turn 2: User states already saved amount: "I have already saved KSh 80,000."
    msg2 = IncomingWhatsAppMessage(
        from_number="+254700000003",
        to_number="+254711111111",
        body="I have already saved KSh 80,000.",
    )
    resp2 = await handle_message_async(
        msg2,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "staff assistance" not in resp2
    assert "Updated:" in resp2 or "80,000" in resp2
    assert "220,000" in resp2  # 300k - 80k remaining
    goal = goal_svc.get_active_goal("mem_003")
    assert goal.current_amount == 80000.0

    # Turn 3: User asks scenario query: "I can manage KSh 10,000 every month. Will that be enough?"
    msg3 = IncomingWhatsAppMessage(
        from_number="+254700000003",
        to_number="+254711111111",
        body="I can manage KSh 10,000 every month. Will that be enough?",
    )
    resp3 = await handle_message_async(
        msg3,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "staff assistance" not in resp3
    assert "10,000" in resp3
    assert "look like" in resp3.lower() or "projected" in resp3.lower()

    # Turn 4: Legitimate human escalation request
    msg4 = IncomingWhatsAppMessage(
        from_number="+254700000003",
        to_number="+254711111111",
        body="I need to talk to a human agent right now about a dispute.",
    )
    resp4 = await handle_message_async(
        msg4,
        intent_router=mock_router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "staff assistance" in resp4


@pytest.mark.anyio
async def test_educational_recommendation_and_product_inquiry_flow():
    mem_repo = InMemoryMemberRepository()
    mem = Member(
        id="mem_004",
        phone_hash="dummy4",
        display_name="Kiprono Cheruiyot",
        preferred_language="en",
    )
    mem_repo.add_member(mem, "+254700000004")
    member_svc = MemberDataService(repository=mem_repo)
    goal_repo = InMemoryGoalRepository()
    goal_svc = GoalService(repository=goal_repo)
    history = InMemoryConversationHistory()

    # Turn 1: Product options inquiry after a goal discussion context
    history.append("+254700000004", "user", "I want to save KSh 100,000 for emergency fund in 1 year.")
    history.append("+254700000004", "assistant", "Goal set: Emergency Fund! Target: KSh 100,000 (demo data)")

    msg1 = IncomingWhatsAppMessage(
        from_number="+254700000004",
        to_number="+254711111111",
        body="What savings options does the SACCO have?",
    )
    resp1 = await handle_message_async(
        msg1,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    # Must answer with SACCO savings types and NOT trigger goal creation prompt
    assert "That sounds like a great goal" not in resp1
    assert "staff assistance" not in resp1
    assert "regular" in resp1.lower() or "deposit" in resp1.lower() or "savings" in resp1.lower()

    # Turn 2: Curriculum recommendation inquiry
    msg2 = IncomingWhatsAppMessage(
        from_number="+254700000004",
        to_number="+254711111111",
        body="What financial information would be useful for me to learn this week?",
    )
    resp2 = await handle_message_async(
        msg2,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "staff assistance" not in resp2
    assert "Compound interest" in resp2 or "Budgeting" in resp2

    # Turn 3: Inquiry on compound interest
    msg3 = IncomingWhatsAppMessage(
        from_number="+254700000004",
        to_number="+254711111111",
        body="I don't understand compound interest. Explain it to me simply.",
    )
    resp3 = await handle_message_async(
        msg3,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "could not find that specific topic" not in resp3
    assert "interest" in resp3.lower()



