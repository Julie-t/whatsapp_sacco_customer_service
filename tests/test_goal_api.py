"""API tests for financial goals REST endpoints and WhatsApp routing."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database.in_memory_goal_repository import InMemoryGoalRepository
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.main import app
from app.models.goal import GoalType
from app.models.member import Member
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_service import handle_message_async
from app.services.goals.goal_service import GoalService
from app.services.members.member_service import MemberDataService


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def in_memory_goal_service():
    repo = InMemoryGoalRepository()
    return GoalService(repository=repo)


def test_create_and_get_goal_api(client):
    target = (date.today() + timedelta(days=365)).isoformat()
    payload = {
        "member_id": "member_001",
        "goal_type": "education",
        "name": "Daughter College",
        "target_amount": 150000.0,
        "current_amount": 25000.0,
        "target_date": target,
        "contribution_amount": 11000.0,
    }
    response = client.post("/goals", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Daughter College"
    assert data["calculation"]["amount_remaining"] == 125000.0

    goal_id = data["id"]
    get_res = client.get(f"/goals/{goal_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == goal_id


def test_scenario_analysis_api(client):
    target = (date.today() + timedelta(days=730)).isoformat()
    payload = {
        "member_id": "member_001",
        "goal_type": "asset_purchase",
        "name": "Land Purchase",
        "target_amount": 240000.0,
        "current_amount": 0.0,
        "target_date": target,
        "contribution_amount": 10000.0,
    }
    create_res = client.post("/goals", json=payload)
    goal_id = create_res.json()["id"]

    scenario_res = client.post(f"/goals/{goal_id}/scenario", json={"proposed_monthly_contribution": 15000.0})
    assert scenario_res.status_code == 200
    scenario_data = scenario_res.json()
    assert scenario_data["proposed_projected_months"] == 16
    assert scenario_data["months_difference"] == 8


def test_invalid_past_date_rejected(client):
    past_date = (date.today() - timedelta(days=10)).isoformat()
    payload = {
        "member_id": "member_001",
        "goal_type": "general_savings",
        "name": "Old",
        "target_amount": 50000.0,
        "target_date": past_date,
    }
    response = client.post("/goals", json=payload)
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.anyio
async def test_handle_goal_query_whatsapp_flow():
    member_repo = InMemoryMemberRepository()
    member = Member(
        id="member_001",
        phone_hash="hash_001",
        display_name="Edna Maina",
        preferred_language="en",
        knowledge_level="beginner",
        sacco_id="demo_sacco",
    )
    member_repo.add_member(member, "whatsapp:+254110923440")
    member_service = MemberDataService(repository=member_repo)

    goal_repo = InMemoryGoalRepository()
    goal_service = GoalService(repository=goal_repo)

    mock_router = MagicMock()
    mock_router.classify = AsyncMock(
        return_value=RequestTriageResult(
            language="en",
            needs_member_data=False,
            is_goal_related=True,
            likely_needs_human=False,
            reasoning="Goal request.",
        )
    )

    # 1. Create a goal via natural language
    msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254110923440",
        body="I want to save KSh 240,000 for university fees in 2 years",
    )
    response = await handle_message_async(
        msg,
        intent_router=mock_router,
        member_service=member_service,
        goal_service=goal_service,
    )
    assert "Goal set:" in response
    assert "KSh 240,000" in response
    assert "(demo data)" in response
    assert "*" not in response

    # 2. Check progress
    progress_msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254110923440",
        body="What is my goal progress?",
    )
    progress_res = await handle_message_async(
        progress_msg,
        intent_router=mock_router,
        member_service=member_service,
        goal_service=goal_service,
    )
    assert "Progress for" in progress_res
    assert "KSh 240,000" in progress_res

    # 3. What-if scenario
    scenario_msg = IncomingWhatsAppMessage(
        from_number="whatsapp:+254110923440",
        body="What if I save 15k instead?",
    )
    scenario_res = await handle_message_async(
        scenario_msg,
        intent_router=mock_router,
        member_service=member_service,
        goal_service=goal_service,
    )
    assert "Proposed monthly savings: KSh 15,000/month" in scenario_res
    assert "sooner" in scenario_res
