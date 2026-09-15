"""API endpoint integration tests for Proactive Engagement and Intelligence."""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models.engagement import (
    MemberEngagementPreferences,
    EducationFrequency,
    NewsFrequency,
    FinancialNewsArticle,
    NewsCategory,
    ProactiveNotification,
    NotificationType,
    NotificationStatus,
)
from app.api.routes import proactive as proactive_route
from app.api.routes import intelligence as intelligence_route
from app.database.in_memory_engagement_repository import InMemoryEngagementRepository


@pytest.fixture
def test_client_and_repo():
    mock_repo = InMemoryEngagementRepository()
    now = datetime.now(timezone.utc)

    # Seed mock repo with member_001
    mock_repo.upsert_preferences(
        MemberEngagementPreferences(
            member_id="member_001",
            education_frequency=EducationFrequency.WEEKLY,
            news_frequency=NewsFrequency.WEEKLY,
            allowed_topics=["budgeting", "saving", "compound_interest"],
        )
    )
    # Seed mock article
    mock_repo.add_article(
        FinancialNewsArticle(
            id="art_api_01",
            source="Central Bank of Kenya",
            title="CBK CBR Rate Announcement",
            content="CBK announces monetary policy statement...",
            summary="Benchmark rates retained.",
            category=NewsCategory.INTEREST_RATES,
            published_at=now,
            expiry_at=now + timedelta(days=30),
            is_approved=True,
        )
    )

    # Patch dependency getters
    proactive_route.get_engagement_repo = lambda: mock_repo
    intelligence_route.get_engagement_repo = lambda: mock_repo

    client = TestClient(app)
    return client, mock_repo


def test_get_and_update_preferences(test_client_and_repo):
    client, repo = test_client_and_repo

    # GET
    res = client.get("/members/member_001/preferences")
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == "member_001"
    assert data["education_frequency"] == "weekly"

    # PUT
    res = client.put(
        "/members/member_001/preferences",
        json={"education_frequency": "monthly", "quiet_hours_start": 22},
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["education_frequency"] == "monthly"
    assert updated["quiet_hours_start"] == 22


def test_generate_proactive_education_endpoint(test_client_and_repo):
    client, repo = test_client_and_repo
    res = client.post("/proactive/education/generate/member_001")
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == "member_001"
    assert "message_body" in data
    assert data["is_eligible"] is True


def test_recommend_financial_news_endpoint(test_client_and_repo):
    client, repo = test_client_and_repo
    res = client.post("/proactive/news/recommend/member_001")
    assert res.status_code == 200
    data = res.json()
    assert data["member_id"] == "member_001"
    assert data["article_id"] == "art_api_01"
    assert "Central Bank of Kenya" in data["source"]


def test_proactive_dispatch_and_feedback_endpoint(test_client_and_repo):
    client, repo = test_client_and_repo

    # Dispatch
    res = client.post(
        "/proactive/dispatch/member_001",
        json={
            "notification_type": "scheduled_education",
            "content_id": "saving",
            "message_body": "Weekly saving reminder...",
            "send_live": False,
        },
    )
    assert res.status_code == 200
    dispatch_data = res.json()
    assert "status" in dispatch_data
    notif_id = dispatch_data.get("notification_id")

    # Feedback
    res = client.post(
        "/proactive/feedback",
        json={
            "member_id": "member_001",
            "notification_id": notif_id,
            "feedback": "helpful",
        },
    )
    assert res.status_code == 200
    fb_data = res.json()
    assert fb_data["status"] == "recorded"
    assert fb_data["feedback"] == "helpful"


def test_intelligence_endpoints(test_client_and_repo):
    client, repo = test_client_and_repo

    # GET /intelligence/news
    res = client.get("/intelligence/news")
    assert res.status_code == 200
    articles = res.json()
    assert len(articles) >= 1

    # POST /intelligence/news/ingest
    now_iso = datetime.now(timezone.utc).isoformat()
    expiry_iso = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    res = client.post(
        "/intelligence/news/ingest",
        json={
            "id": "art_new_01",
            "source": "SASRA",
            "title": "SACCO Sector Assets Grow",
            "content": "Full article content on sector asset expansion...",
            "summary": "Sector assets grow.",
            "category": "sacco_regulations",
            "published_at": now_iso,
            "expiry_at": expiry_iso,
            "is_approved": True,
        },
    )
    assert res.status_code == 201
    created = res.json()
    assert created["id"] == "art_new_01"
    assert created["source"] == "SASRA"

    # GET /intelligence/knowledge-gaps/summary
    res = client.get("/intelligence/knowledge-gaps/summary?sacco_id=demo_sacco")
    assert res.status_code == 200
    summary = res.json()
    assert "total_unanswered_questions" in summary
    assert "top_topics" in summary
