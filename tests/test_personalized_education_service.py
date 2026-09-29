"""Unit tests for PersonalizedEducationService."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.ai.rag.models import RAGResult
from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.database.in_memory_personalization_repository import InMemoryPersonalizationHistoryRepository
from app.models.goal import ContributionFrequency, FinancialGoal, GoalStatus, GoalType
from app.models.member import Member
from app.services.goals.goal_service import GoalService
from app.services.members.member_service import MemberDataService
from app.services.education.personalization_context_builder import PersonalizationContextBuilder
from app.services.education.personalized_education_service import (
    GUARDRAIL_EDUCATION_DISCLAIMER,
    PersonalizedEducationService,
)


@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock()
    pipeline.search.return_value = [
        RAGResult(
            document_id="test_compound_interest",
            chunk_id="test_compound_interest#0",
            title="Compound Interest",
            content="Compound interest is interest calculated on initial principal and accumulated interest.",
            score=0.92,
            metadata={"topic": "compound_interest"},
        )
    ]
    return pipeline


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value="Compound interest means earning money on your savings and also on the interest already added."
    )
    return llm


@pytest.fixture
def member_repo():
    repo = InMemoryMemberRepository()
    repo.add_member(
        Member(
            id="mem_001",
            phone_hash="",
            display_name="Edna Maina",
            preferred_language="en",
            knowledge_level="beginner",
        ),
        phone_number="+254700000001",
    )
    return repo


@pytest.fixture
def goal_repo():
    repo = InMemoryGoalRepository()
    repo.create(
        FinancialGoal(
            id="goal_edu",
            member_id="mem_001",
            goal_type=GoalType.EDUCATION,
            name="University Fund",
            target_amount=100000.0,
            current_amount=30000.0,
            target_date=date.today() + timedelta(days=365),
            contribution_amount=6000.0,
            contribution_frequency=ContributionFrequency.MONTHLY,
            status=GoalStatus.ACTIVE,
        )
    )
    return repo


@pytest.fixture
def history_repo():
    return InMemoryPersonalizationHistoryRepository()


@pytest.fixture
def service(mock_pipeline, mock_llm, member_repo, goal_repo, history_repo):
    member_service = MemberDataService(repository=member_repo)
    goal_service = GoalService(repository=goal_repo)
    context_builder = PersonalizationContextBuilder(
        member_service=member_service,
        goal_service=goal_service,
        history_repo=history_repo,
    )
    return PersonalizedEducationService(
        pipeline=mock_pipeline,
        llm=mock_llm,
        context_builder=context_builder,
        history_repo=history_repo,
    )


def test_detect_topic():
    assert PersonalizedEducationService.detect_topic("How does compound interest work?") == "compound_interest"
    assert PersonalizedEducationService.detect_topic("How to budget with 50/30/20 rule?") == "budgeting"
    assert PersonalizedEducationService.detect_topic("How much emergency fund is enough?") == "emergency_fund"
    assert PersonalizedEducationService.detect_topic("How should I clear my loan debt?") == "debt_management"
    assert PersonalizedEducationService.detect_topic("What are SACCO shares and dividends?") == "sacco_shares"


def test_is_directive_investment_query():
    assert PersonalizedEducationService.is_directive_investment_query("Which stock should I buy?") is True
    assert PersonalizedEducationService.is_directive_investment_query("Should I invest in crypto?") is True
    assert PersonalizedEducationService.is_directive_investment_query("What is compound interest?") is False


@pytest.mark.anyio
async def test_directive_investment_triggers_guardrail(service):
    resp = await service.explain(
        member_id_or_phone="mem_001",
        query="Which cryptocurrency should I buy to reach my goal faster?",
    )
    assert resp.topic == "guardrail"
    assert "cannot give specific investment advice" in resp.answer
    assert resp.sources == []


@pytest.mark.anyio
async def test_explain_valid_educational_query(service, history_repo):
    resp = await service.explain(
        member_id_or_phone="mem_001",
        query="What is compound interest?",
    )
    assert resp.topic == "compound_interest"
    assert resp.knowledge_level_applied == "beginner"
    assert resp.goal_context_applied == "University Fund"
    assert "test_compound_interest" in resp.sources
    assert "*" not in resp.answer
    assert "—" not in resp.answer
    assert "(demo data)" in resp.answer

    # Verify history was recorded
    history = history_repo.get_history("mem_001")
    assert len(history) == 1
    assert history[0].topic == "compound_interest"
    assert history[0].goal_id == "goal_edu"


@pytest.mark.anyio
async def test_explain_unanswerable_query_records_gap(service, mock_pipeline):
    mock_pipeline.search.return_value = []
    resp = await service.explain(
        member_id_or_phone="mem_001",
        query="What is the policy on extraterrestrial gold mining?",
    )
    assert "could not find that specific topic" in resp.answer
    assert resp.sources == []
