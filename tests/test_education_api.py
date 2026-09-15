"""Tests for the Personalized Financial Education REST API endpoints."""

from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
import pytest

from app.api.routes import education as education_route
from app.main import app
from app.schemas.personalization import PersonalizedEducationResponse


@pytest.fixture
def client():
    return TestClient(app)


def test_get_education_plan_member_001(client, monkeypatch):
    from app.models.goal import FinancialGoal, GoalStatus, GoalType
    from app.models.member import Member
    from datetime import date, timedelta

    mock_member_svc = MagicMock()
    mock_member_svc.get_member_profile.return_value = Member(
        id="member_001",
        phone_hash="hash_001",
        display_name="Edna Maina",
        preferred_language="en",
        knowledge_level="beginner",
        sacco_id="demo_sacco",
    )
    mock_goal_svc = MagicMock()
    mock_goal_svc.get_member_goals.return_value = [
        FinancialGoal(
            id="goal_001_edu",
            member_id="member_001",
            goal_type=GoalType.EDUCATION,
            name="Daughter's University",
            target_amount=300000.0,
            current_amount=60000.0,
            target_date=date.today() + timedelta(days=730),
            contribution_amount=10000.0,
            status=GoalStatus.ACTIVE,
        )
    ]
    monkeypatch.setattr(education_route, "get_member_service", lambda: mock_member_svc)
    monkeypatch.setattr(education_route, "get_goal_service", lambda: mock_goal_svc)

    response = client.get("/education/plan/member_001")
    assert response.status_code == 200
    data = response.json()
    assert data["member_id"] == "member_001"
    assert data["goal_type"] == "education"
    assert len(data["plan"]) == 4
    assert data["plan"][0]["topic"] == "budgeting"
    assert "Tuition" in data["plan"][0]["title"]


def test_get_education_plan_unknown_member(client):
    response = client.get("/education/plan/non_existent_member_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_education_history_endpoint(client, monkeypatch):
    mock_repo = MagicMock()
    mock_repo.get_history.return_value = []
    monkeypatch.setattr(education_route, "get_history_repo", lambda: mock_repo)

    response = client.get("/education/history/member_001")
    assert response.status_code == 200
    assert response.json() == []


def test_explain_endpoint(client, monkeypatch):
    mock_service = MagicMock()
    mock_service.explain = AsyncMock(
        return_value=PersonalizedEducationResponse(
            answer="Compound interest means your savings earn interest on the interest already added. (demo data)",
            topic="compound_interest",
            knowledge_level_applied="beginner",
            goal_context_applied="Daughter's University",
            language_applied="en",
            sources=["test_compound_interest"],
            is_demo=True,
        )
    )
    monkeypatch.setattr(education_route, "get_education_service", lambda: mock_service)

    payload = {
        "member_id": "member_001",
        "query": "What is compound interest?",
        "language": "en",
    }
    response = client.post("/education/explain", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "compound_interest"
    assert data["knowledge_level_applied"] == "beginner"
    assert data["goal_context_applied"] == "Daughter's University"
    assert "Compound interest means" in data["answer"]
