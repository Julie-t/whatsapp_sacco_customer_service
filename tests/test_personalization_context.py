"""Unit tests for PersonalizationContextBuilder."""

from datetime import date, timedelta
import pytest

from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.database.in_memory_personalization_repository import InMemoryPersonalizationHistoryRepository
from app.models.goal import ContributionFrequency, FinancialGoal, GoalStatus, GoalType
from app.models.member import Member
from app.models.personalization import CommunicationStyle, KnowledgeLevel
from app.services.goals.goal_service import GoalService
from app.services.members.member_service import MemberDataService
from app.services.education.personalization_context_builder import PersonalizationContextBuilder


@pytest.fixture
def member_repo():
    repo = InMemoryMemberRepository()
    repo.add_member(
        Member(
            id="mem_beginner",
            phone_hash="",
            display_name="Edna Maina",
            preferred_language="mixed",
            knowledge_level="beginner",
        ),
        phone_number="+254700000001",
    )
    repo.add_member(
        Member(
            id="mem_intermediate",
            phone_hash="",
            display_name="James Ochieng",
            preferred_language="en",
            knowledge_level="intermediate",
        ),
        phone_number="+254700000002",
    )
    return repo


@pytest.fixture
def goal_repo():
    repo = InMemoryGoalRepository()
    repo.create(
        FinancialGoal(
            id="goal_edu",
            member_id="mem_beginner",
            goal_type=GoalType.EDUCATION,
            name="University Fund",
            target_amount=100000.0,
            current_amount=40000.0,
            target_date=date.today() + timedelta(days=365),
            contribution_amount=5000.0,
            contribution_frequency=ContributionFrequency.MONTHLY,
            status=GoalStatus.ACTIVE,
        )
    )
    return repo


@pytest.fixture
def history_repo():
    repo = InMemoryPersonalizationHistoryRepository()
    repo.record_topic("mem_beginner", "budgeting", "50/30/20 rule")
    return repo


@pytest.fixture
def builder(member_repo, goal_repo, history_repo):
    member_service = MemberDataService(repository=member_repo)
    goal_service = GoalService(repository=goal_repo)
    return PersonalizationContextBuilder(
        member_service=member_service,
        goal_service=goal_service,
        history_repo=history_repo,
    )


def test_build_context_known_beginner_with_goal(builder):
    ctx = builder.build_context(
        member_id_or_phone="mem_beginner",
        query="How can I save faster for school?",
        retrieved_evidence=["Consistent contributions build momentum."],
    )
    assert ctx.member_id == "mem_beginner"
    assert ctx.display_name == "Edna Maina"
    assert ctx.knowledge_level == KnowledgeLevel.BEGINNER
    assert ctx.communication_style == CommunicationStyle.SIMPLE
    assert ctx.active_goal is not None
    assert ctx.active_goal.name == "University Fund"
    assert ctx.goal_progress is not None
    assert ctx.goal_progress.progress_percentage == 40.0
    assert ctx.goal_progress.amount_remaining == 60000.0
    assert "budgeting" in ctx.recent_topics
    assert ctx.retrieved_evidence == ["Consistent contributions build momentum."]


def test_build_context_intermediate_member(builder):
    ctx = builder.build_context(
        member_id_or_phone="mem_intermediate",
        query="Explain compound interest.",
    )
    assert ctx.member_id == "mem_intermediate"
    assert ctx.knowledge_level == KnowledgeLevel.INTERMEDIATE
    assert ctx.communication_style == CommunicationStyle.STANDARD
    assert ctx.active_goal is None
    assert ctx.goal_progress is None


def test_build_context_unknown_member(builder):
    ctx = builder.build_context(
        member_id_or_phone="mem_unknown",
        query="What is a SACCO?",
    )
    assert ctx.member_id == ""
    assert ctx.display_name == "Member"
    assert ctx.knowledge_level == KnowledgeLevel.BEGINNER
    assert ctx.communication_style == CommunicationStyle.SIMPLE
    assert ctx.active_goal is None
