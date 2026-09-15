"""Unit and integration tests for System 11 Escalations Management."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.admin.admin_auth_service import create_access_token
from app.services.admin.admin_escalation_service import AdminEscalationService

client = TestClient(app)


@pytest.fixture
def admin_headers():
    token = create_access_token(
        admin_id="admin_001",
        username="admin",
        sacco_id="demo_sacco",
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


def test_escalation_lifecycle_and_api(admin_headers):
    esc_svc = AdminEscalationService()
    # 1. Record escalation from conversation
    esc = esc_svc.record_from_conversation(
        conversation_key="whatsapp:+254700999888",
        query="I have an urgent dispute with a double debit on my account",
        member_id="member_001",
        sacco_id="demo_sacco",
    )
    assert esc.id is not None
    assert esc.category.value == "dispute"
    assert esc.priority.value == "high"
    assert esc.status.value == "open"

    # 2. List escalations via API
    res = client.get("/api/admin/escalations?status=open", headers=admin_headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    target = next((item for item in items if item["id"] == esc.id), None)
    assert target is not None
    assert "dispute" in target["query"]

    # 3. Update escalation to resolved
    patch_res = client.patch(
        f"/api/admin/escalations/{esc.id}",
        headers=admin_headers,
        json={"status": "resolved", "notes": "Member contacted and transaction reversed."},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "resolved"
    assert updated["resolved_at"] is not None
    assert "Member contacted" in updated["notes"]
