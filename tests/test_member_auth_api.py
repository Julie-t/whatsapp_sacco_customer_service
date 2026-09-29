"""API tests for Member Authentication endpoints (System 12)."""

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.models.member import Member
from app.services.members.member_service import MemberDataService
import app.api.routes.member_auth as auth_routes

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_mock_member_service():
    repo = InMemoryMemberRepository()
    repo.add_member(
        Member(id="mem_001", phone_hash="", display_name="Edna Maina", sacco_id="demo_sacco"),
        phone_number="+254700000001",
    )
    auth_routes._auth_service = None  # Reset singleton
    from app.services.members.member_auth_service import MemberAuthService
    from app.database.in_memory_member_auth_repository import InMemoryMemberAuthRepository
    m_svc = MemberDataService(repository=repo)
    auth_routes._auth_service = MemberAuthService(
        auth_repo=InMemoryMemberAuthRepository(),
        member_service=m_svc,
        session_ttl_minutes=15,
    )
    yield
    auth_routes._auth_service = None


def test_request_and_verify_otp_flow():
    # 1. Request OTP
    res = client.post(
        "/api/members/auth/request-otp",
        json={"phone_number": "+254700000001", "sacco_id": "demo_sacco"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["demo_otp"] is not None
    otp_code = data["demo_otp"]

    # 2. Check session before verification (should be 404)
    res_sess = client.get("/api/members/auth/session", params={"phone_number": "+254700000001", "sacco_id": "demo_sacco"})
    assert res_sess.status_code == 404

    # 3. Verify OTP
    res_verify = client.post(
        "/api/members/auth/verify-otp",
        json={"phone_number": "+254700000001", "otp_code": otp_code, "sacco_id": "demo_sacco"},
    )
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    assert verify_data["authenticated"] is True
    assert verify_data["member_id"] == "mem_001"
    assert verify_data["ttl_seconds_remaining"] > 0

    # 4. Check session after verification
    res_sess_after = client.get("/api/members/auth/session", params={"phone_number": "+254700000001", "sacco_id": "demo_sacco"})
    assert res_sess_after.status_code == 200
    assert res_sess_after.json()["authenticated"] is True

    # 5. Logout
    res_logout = client.post("/api/members/auth/logout", params={"phone_number": "+254700000001", "sacco_id": "demo_sacco"})
    assert res_logout.status_code == 200

    # 6. Check session after logout
    res_sess_logout = client.get("/api/members/auth/session", params={"phone_number": "+254700000001", "sacco_id": "demo_sacco"})
    assert res_sess_logout.status_code == 404
