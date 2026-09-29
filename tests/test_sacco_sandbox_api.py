"""API tests for SACCO Sandbox endpoints (System 12.24)."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_sandbox_member_profile():
    res = client.get("/api/sandbox/sacco/demo_sacco/members/mem_001")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "mem_001"
    assert data["display_name"] == "Edna Maina"


def test_sandbox_savings_balance():
    res = client.get("/api/sandbox/sacco/demo_sacco/members/mem_001/balance")
    assert res.status_code == 200
    data = res.json()
    assert data["balance"] == 32450.0
    assert data["currency"] == "KSh"


def test_sandbox_loans():
    res = client.get("/api/sandbox/sacco/demo_sacco/members/mem_001/loans")
    assert res.status_code == 200
    loans = res.json()
    assert len(loans) == 1
    assert loans[0]["balance_remaining"] == 125000.0


def test_sandbox_transactions():
    res = client.get("/api/sandbox/sacco/demo_sacco/members/mem_001/transactions?limit=2")
    assert res.status_code == 200
    txns = res.json()
    assert len(txns) == 2
    assert txns[0]["transaction_type"] == "deposit"


def test_sandbox_change_request():
    res = client.post(
        "/api/sandbox/sacco/demo_sacco/members/mem_001/change-requests",
        json={
            "change_type": "phone_number",
            "payload": {"new_phone": "+254711998877"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"
    assert "queued for review" in data["message"]


def test_sandbox_tenant_isolation_forbidden():
    res = client.get("/api/sandbox/sacco/unauthorized_sacco/members/mem_001")
    assert res.status_code == 403
