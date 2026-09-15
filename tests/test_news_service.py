"""Tests for NewsService (relevance matching, freshness, and WhatsApp formatting)."""

from datetime import datetime, timezone, timedelta, date
from unittest.mock import MagicMock
import pytest

from app.database.in_memory_engagement_repository import InMemoryEngagementRepository
from app.models.engagement import (
    FinancialNewsArticle,
    NewsCategory,
    MemberEngagementPreferences,
    NewsFrequency,
)
from app.models.goal import FinancialGoal, GoalType, GoalStatus
from app.services.proactive.news_service import NewsService


def test_recommend_news_matched_to_goal():
    repo = InMemoryEngagementRepository()
    now = datetime.now(timezone.utc)

    art_pension = FinancialNewsArticle(
        id="art_ret_01",
        source="Business Daily",
        title="Pension Assets Hit Record High",
        content="Cooperative retirement assets grew by 15%...",
        summary="Retirement scheme assets surge on steady contributions.",
        category=NewsCategory.RETIREMENT,
        published_at=now,
        expiry_at=now + timedelta(days=30),
        is_approved=True,
    )
    art_rates = FinancialNewsArticle(
        id="art_rates_01",
        source="Central Bank of Kenya",
        title="Central Bank Holds Rates",
        content="Rates unchanged at 12.75%...",
        summary="CBR rate unchanged.",
        category=NewsCategory.INTEREST_RATES,
        published_at=now,
        expiry_at=now + timedelta(days=30),
        is_approved=True,
    )
    repo.add_article(art_pension)
    repo.add_article(art_rates)

    mock_goal_service = MagicMock()
    goal = FinancialGoal(
        id="goal_ret",
        member_id="mem_01",
        goal_type=GoalType.RETIREMENT,
        name="Retirement Fund",
        target_amount=500000.0,
        current_amount=100000.0,
        target_date=date(2035, 1, 1),
        status=GoalStatus.ACTIVE,
    )
    mock_goal_service.get_member_goals.return_value = [goal]

    news_service = NewsService(engagement_repo=repo, goal_service=mock_goal_service)
    rec = news_service.recommend_news_for_member("mem_01")

    assert rec is not None
    assert rec.is_eligible is True
    assert rec.article.id == "art_ret_01"
    assert "Pension Assets Hit Record High" in rec.whatsapp_message
    assert "Business Daily" in rec.whatsapp_message


def test_recommend_news_skips_recent_duplicate():
    repo = InMemoryEngagementRepository()
    now = datetime.now(timezone.utc)

    art = FinancialNewsArticle(
        id="art_01",
        source="CBK",
        title="CBK Inflation Update",
        content="Inflation eases to 4.4%...",
        category=NewsCategory.INFLATION,
        published_at=now,
        expiry_at=now + timedelta(days=30),
        is_approved=True,
    )
    repo.add_article(art)

    # Record that member already received art_01
    repo.has_received_content_recently = MagicMock(return_value=True)

    mock_goal_service = MagicMock()
    mock_goal_service.get_member_goals.return_value = []

    news_service = NewsService(engagement_repo=repo, goal_service=mock_goal_service)
    rec = news_service.recommend_news_for_member("mem_02")
    assert rec is None  # No un-sent article available


def test_recommend_news_paused_preference():
    repo = InMemoryEngagementRepository()
    repo.upsert_preferences(MemberEngagementPreferences(
        member_id="mem_03",
        news_frequency=NewsFrequency.PAUSED,
    ))

    news_service = NewsService(engagement_repo=repo)
    rec = news_service.recommend_news_for_member("mem_03")
    assert rec is not None
    assert rec.is_eligible is False
    assert "paused" in rec.ineligibility_reason.lower()
