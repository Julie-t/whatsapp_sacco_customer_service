"""Regression and acceptance tests for goal conversation state accumulation.

Verifies that follow-up messages update the existing active goal rather than
creating new goals and resetting accumulated state (such as starting savings).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.member import Member
from app.models.goal import GoalStatus, GoalType
from app.schemas.message import IncomingWhatsAppMessage
from app.schemas.intent import RequestTriageResult
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.services.conversations.conversation_service import handle_message_async
from app.services.members.member_service import MemberDataService
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.services.goals.goal_service import GoalService
from app.database.in_memory_goal_repository import InMemoryGoalRepository


@pytest.fixture
def test_setup():
    mem_repo = InMemoryMemberRepository()
    mem = Member(
        id="mem_peter",
        phone_hash="hash_peter",
        display_name="Peter Mwangi",
        preferred_language="en",
        knowledge_level="beginner",
    )
    mem_repo.add_member(mem, "+254110923440")
    member_svc = MemberDataService(repository=mem_repo)

    goal_repo = InMemoryGoalRepository()
    goal_svc = GoalService(repository=goal_repo)
    history = InMemoryConversationHistory()

    router = MagicMock()
    router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=True,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="Goal sequence message",
        )
    )

    return {
        "phone": "+254110923440",
        "member_svc": member_svc,
        "goal_svc": goal_svc,
        "goal_repo": goal_repo,
        "history": history,
        "router": router,
    }


@pytest.mark.anyio
async def test_three_turn_goal_accumulation_sequence(test_setup):
    """MANDATORY REGRESSION TEST:

    Turn 1: User says: 'I want to save KSh 300,000 for my business by September 2027.'
    Turn 2: User says: 'I have about KSh 80,000 saved already.'
    Turn 3: User says: 'I can normally put aside KSh 10,000 every month, but sometimes business is slow.'

    Final State Assertions:
    - Number of active business goals for member = 1 (NOT 2 or 3)
    - active_goal.target_amount = 300,000
    - active_goal.current_amount = 80,000 (preserved, NOT reset to 0)
    - active_goal.contribution_amount = 10,000
    - Turn 3 response confirms KSh 10,000/month, preserves KSh 80,000 savings, and uses 'Updated'
    """
    phone = test_setup["phone"]
    member_svc = test_setup["member_svc"]
    goal_svc = test_setup["goal_svc"]
    history = test_setup["history"]
    router = test_setup["router"]

    # Turn 1: Initial goal ambition
    msg1 = IncomingWhatsAppMessage(
        from_number=phone,
        body="I want to save KSh 300,000 for my business by September 2027.",
    )
    resp1 = await handle_message_async(
        msg1,
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "Goal set: Business Growth!" in resp1
    assert "300,000" in resp1

    active1 = goal_svc.get_active_goal("mem_peter")
    assert active1 is not None
    assert active1.target_amount == 300000.0
    assert active1.current_amount == 0.0
    all_goals_t1 = goal_svc.get_member_goals("mem_peter", status=GoalStatus.ACTIVE)
    assert len(all_goals_t1) == 1

    # Turn 2: Stating existing savings
    msg2 = IncomingWhatsAppMessage(
        from_number=phone,
        body="I have about KSh 80,000 saved already.",
    )
    resp2 = await handle_message_async(
        msg2,
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "Updated: Business Growth!" in resp2 or "80,000" in resp2
    assert "220,000" in resp2  # 300k - 80k remaining

    active2 = goal_svc.get_active_goal("mem_peter")
    assert active2 is not None
    assert active2.id == active1.id  # Same goal, not duplicated!
    assert active2.current_amount == 80000.0
    all_goals_t2 = goal_svc.get_member_goals("mem_peter", status=GoalStatus.ACTIVE)
    assert len(all_goals_t2) == 1

    # Turn 3: Adding monthly contribution and income variability
    msg3 = IncomingWhatsAppMessage(
        from_number=phone,
        body="I can normally put aside KSh 10,000 every month, but sometimes business is slow.",
    )
    resp3 = await handle_message_async(
        msg3,
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    # Must NOT reset to Starting savings: KSh 0
    assert "Starting savings: KSh 0" not in resp3
    assert "Goal set: Business Growth!" not in resp3
    assert "Updated: Business Growth!" in resp3

    # Must show updated contribution and preserved savings
    assert "10,000" in resp3
    assert "80,000" in resp3
    assert "220,000" in resp3

    # Must check database record
    active3 = goal_svc.get_active_goal("mem_peter")
    assert active3 is not None
    assert active3.id == active1.id  # Still exactly the same single goal record!
    assert active3.target_amount == 300000.0
    assert active3.current_amount == 80000.0  # PRESERVED!
    assert active3.contribution_amount == 10000.0
    assert active3.notes == "variable income"

    all_goals_t3 = goal_svc.get_member_goals("mem_peter", status=GoalStatus.ACTIVE)
    assert len(all_goals_t3) == 1  # Crucial: NO duplicate records!


@pytest.mark.anyio
async def test_irregular_income_variability_pattern(test_setup):
    """Test scenario where member describes fluctuating income:

    'Some months I can save 15,000 and some months only 5,000.'
    The system should update the contribution variability note, not overwrite starting savings.
    """
    phone = test_setup["phone"]
    member_svc = test_setup["member_svc"]
    goal_svc = test_setup["goal_svc"]
    history = test_setup["history"]
    router = test_setup["router"]

    # Initial setup: already has KSh 300k goal with 80k saved
    from app.schemas.goal import GoalCreate
    from datetime import date
    goal_svc.create_goal(
        GoalCreate(
            member_id="mem_peter",
            goal_type=GoalType.BUSINESS,
            name="Business Growth",
            target_amount=300000.0,
            target_date=date(2027, 9, 15),
            current_amount=80000.0,
        )
    )

    msg = IncomingWhatsAppMessage(
        from_number=phone,
        body="Some months I can save 15,000 and some months only 5,000.",
    )
    resp = await handle_message_async(
        msg,
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    assert "Updated: Business Growth!" in resp
    assert "80,000" in resp  # Preserves starting savings
    assert "220,000" in resp  # Preserves remaining amount

    active = goal_svc.get_active_goal("mem_peter")
    assert active.current_amount == 80000.0
    assert active.notes == "variable income"
    all_goals = goal_svc.get_member_goals("mem_peter", status=GoalStatus.ACTIVE)
    assert len(all_goals) == 1


@pytest.mark.anyio
async def test_four_turn_goal_scenario_comparison_sequence(test_setup):
    """MANDATORY REGRESSION TEST FOR SCENARIO COMPARISON ON ACTIVE GOAL:

    Turn 1: User says: 'I want to save KSh 300,000 for my business by September 2027.'
    Turn 2: User says: 'I have KSh 80,000 saved already.'
    Turn 3: User says: 'I normally save KSh 10,000 a month.'
    Turn 4: User says: 'Which one is better for me, saving 10,000 or 15,000?'

    Expected Behavior:
    - Existing goal reused (mem_peter, target=300000, current=80000, remaining=220000)
    - No new goal created
    - active_goal_count == 1
    - Compares 10,000 vs 15,000 deterministically:
      * 10,000/month -> 22 months
      * 15,000/month -> 15 months (7 months faster)
    - Explains cash-flow vs. speed trade-off
    - Does NOT ask 'That sounds like a great goal! How much would you like to save...'
    """
    phone = test_setup["phone"]
    member_svc = test_setup["member_svc"]
    goal_svc = test_setup["goal_svc"]
    history = test_setup["history"]
    router = test_setup["router"]

    # Turn 1: Initial goal
    resp1 = await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="I want to save KSh 300,000 for my business by September 2027."),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "Goal set: Business Growth!" in resp1

    # Turn 2: Stating starting savings
    resp2 = await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="I have KSh 80,000 saved already."),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "80,000" in resp2
    assert "220,000" in resp2

    # Turn 3: Typical contribution
    resp3 = await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="I normally save KSh 10,000 a month."),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )
    assert "10,000" in resp3

    # Turn 4: Scenario comparison inquiry
    resp4 = await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="Which one is better for me, saving 10,000 or 15,000?"),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    # Must NOT ask new goal creation questions
    assert "That sounds like a great goal!" not in resp4
    assert "How much would you like to save" not in resp4
    assert "Goal set:" not in resp4

    # Must compare 10,000 vs 15,000 deterministically
    assert "10,000" in resp4
    assert "15,000" in resp4
    assert "22 months" in resp4
    assert "15 months" in resp4
    assert "7 months faster" in resp4 or "faster" in resp4

    # Active goal count must remain exactly 1
    all_goals = goal_svc.get_member_goals("mem_peter", status=GoalStatus.ACTIVE)
    assert len(all_goals) == 1

    # State must be preserved
    active = goal_svc.get_active_goal("mem_peter")
    assert active is not None
    assert active.current_amount == 80000.0
    assert active.target_amount == 300000.0


def test_deterministic_fluctuating_income_education_routing():
    """Verify deterministic router flags irregular income savings question as education, not human escalation."""
    from app.ai.intent_router import classify_deterministic
    msg = "My income changes a lot because some months the shop is busy and other months it is slow. How should I think about saving?"
    res = classify_deterministic(msg)
    assert res is not None
    assert res.is_education_related is True
    assert res.likely_needs_human is False
    assert res.needs_member_data is False
    assert res.is_goal_related is False


def test_request_triage_fallback_does_not_escalate_to_human():
    """Verify triage fallback does not falsely claim staff assistance is required."""
    fallback = RequestTriageResult.fallback()
    assert fallback.likely_needs_human is False


@pytest.mark.anyio
async def test_five_turn_fluctuating_income_education_sequence(test_setup):
    """MANDATORY REGRESSION TEST: Turn 5 Financial education for fluctuating income.

    Turns 1-4 establish Business Growth goal (target KSh 300,000, current KSh 80,000).
    Turn 5: 'My income changes a lot because some months the shop is busy and other months it is slow. How should I think about saving?'

    Expected:
    - Routed to financial education / personalized education (not human escalation)
    - Response is NOT HUMAN_SUPPORT_PLACEHOLDER
    - No new goal created (active_goal_count == 1)
    - Goal context (target 300,000, current 80,000) preserved
    - Grounded educational advice acknowledging fluctuating/variable income
    """
    from app.services.conversations.conversation_service import HUMAN_SUPPORT_PLACEHOLDER
    from app.schemas.personalization import PersonalizedEducationResponse

    phone = test_setup["phone"]
    member_svc = test_setup["member_svc"]
    goal_svc = test_setup["goal_svc"]
    history = test_setup["history"]
    router = test_setup["router"]

    # Turn 1: Initial goal
    await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="I want to save KSh 300,000 for my business by September 2027."),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    # Turn 2: Current savings
    await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="I have KSh 80,000 saved already."),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    # Turn 3: Monthly contribution
    await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="I normally save KSh 10,000 a month."),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    # Turn 4: Scenario comparison
    await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body="Which one is better for me, saving 10,000 or 15,000?"),
        intent_router=router,
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
    )

    # Mock education service to verify it is called with member context and receives query
    mock_edu_svc = MagicMock()
    mock_edu_svc.explain = AsyncMock(
        return_value=PersonalizedEducationResponse(
            answer=(
                "Since your business income changes from month to month, a fixed amount may not always "
                "be practical. A common approach is to set a baseline savings target during slower months "
                "and save more during stronger months to stay on track for your KSh 300,000 business goal."
            ),
            topic="savings_discipline",
            knowledge_level_applied="beginner",
            goal_context_applied="Business Growth",
            language_applied="en",
            sources=["test_consistent_saving"],
            is_demo=True,
        )
    )

    # Turn 5: Fluctuating income educational question
    turn5_msg = "My income changes a lot because some months the shop is busy and other months it is slow. How should I think about saving?"
    resp5 = await handle_message_async(
        IncomingWhatsAppMessage(from_number=phone, body=turn5_msg),
        intent_router=None,  # Use real classify_deterministic fast path!
        history_store=history,
        member_service=member_svc,
        goal_service=goal_svc,
        education_service=mock_edu_svc,
    )

    # Assertions
    assert resp5 != HUMAN_SUPPORT_PLACEHOLDER
    assert "Your request may need staff assistance" not in resp5
    assert "baseline" in resp5 or "slower months" in resp5 or "saving" in resp5
    mock_edu_svc.explain.assert_called_once()
    call_kwargs = mock_edu_svc.explain.call_args.kwargs
    assert call_kwargs["member_id_or_phone"] == phone
    assert "saving" in call_kwargs["query"].lower()

    # Active goal count must remain exactly 1
    all_goals = goal_svc.get_member_goals("mem_peter", status=GoalStatus.ACTIVE)
    assert len(all_goals) == 1
    active = goal_svc.get_active_goal("mem_peter")
    assert active.current_amount == 80000.0
    assert active.target_amount == 300000.0

