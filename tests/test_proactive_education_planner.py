"""Tests for ProactiveEducationPlanner."""

import pytest
from datetime import date
from unittest.mock import MagicMock
from app.services.proactive.proactive_education_planner import ProactiveEducationPlanner, ProactiveEducationPlan
from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
from app.models.engagement import MemberEngagementPreferences, EducationFrequency
from app.models.personalization import KnowledgeLevel, PersonalizationContext
from app.models.goal import FinancialGoal, GoalType, GoalStatus


def test_planner_selects_goal_aligned_topic_and_adapts_level():
    mock_context_builder = MagicMock()
    goal = FinancialGoal(
        id="goal_ret_01",
        member_id="mem_01",
        goal_type=GoalType.RETIREMENT,
        name="Retirement Fund",
        target_amount=1000000.0,
        target_date=date(2035, 12, 31),
        current_amount=200000.0,
        status=GoalStatus.ACTIVE,
    )
    mock_context_builder.build_context.return_value = PersonalizationContext(
        member_id="mem_01",
        display_name="James Ochieng",
        knowledge_level=KnowledgeLevel.ADVANCED,
        preferred_language="en",
        active_goal=goal,
        recent_topics=[],
    )

    repo = InMemoryEngagementRepository()
    repo.upsert_preferences(MemberEngagementPreferences(
        member_id="mem_01",
        education_frequency=EducationFrequency.WEEKLY,
        allowed_topics=["compound_interest", "retirement", "sacco_shares"],
    ))

    planner = ProactiveEducationPlanner(
        context_builder=mock_context_builder,
        engagement_repo=repo,
    )

    plan = planner.plan_next_lesson("mem_01")
    assert plan.is_eligible is True
    assert plan.topic == "compound_interest"
    assert "Terminal asset accumulation" in plan.message_body or "Compound return mechanics" in plan.message_body
    assert "James" in plan.message_body
    assert "Retirement Fund" in plan.message_body


def test_planner_skips_recent_topic():
    mock_context_builder = MagicMock()
    goal = FinancialGoal(
        id="goal_em_01",
        member_id="mem_02",
        goal_type=GoalType.EMERGENCY_FUND,
        name="Emergency Buffer",
        target_amount=100000.0,
        target_date=date(2027, 6, 30),
        current_amount=50000.0,
        status=GoalStatus.ACTIVE,
    )
    # budgeting was already completed recently
    mock_context_builder.build_context.return_value = PersonalizationContext(
        member_id="mem_02",
        display_name="Edna Maina",
        knowledge_level=KnowledgeLevel.BEGINNER,
        preferred_language="mixed",
        active_goal=goal,
        recent_topics=["budgeting"],
    )

    repo = InMemoryEngagementRepository()
    repo.upsert_preferences(MemberEngagementPreferences(
        member_id="mem_02",
        education_frequency=EducationFrequency.WEEKLY,
        allowed_topics=["budgeting", "savings_discipline", "emergency_fund"],
    ))

    planner = ProactiveEducationPlanner(
        context_builder=mock_context_builder,
        engagement_repo=repo,
    )

    plan = planner.plan_next_lesson("mem_02")
    assert plan.is_eligible is True
    # Should move to savings_discipline since budgeting is in recent_topics
    assert plan.topic == "savings_discipline"
    assert "Habari Edna" in plan.message_body


def test_planner_paused_preferences():
    repo = InMemoryEngagementRepository()
    repo.upsert_preferences(MemberEngagementPreferences(
        member_id="mem_03",
        education_frequency=EducationFrequency.PAUSED,
    ))

    planner = ProactiveEducationPlanner(
        context_builder=MagicMock(),
        engagement_repo=repo,
    )

    plan = planner.plan_next_lesson("mem_03")
    assert plan.is_eligible is False
    assert "paused" in plan.ineligibility_reason.lower()
