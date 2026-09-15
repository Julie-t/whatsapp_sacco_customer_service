"""Unit tests for Member Authentication & Session Management (System 12.1, 12.2)."""

from datetime import datetime, timedelta, timezone
import pytest

from app.database.in_memory_member_auth_repository import InMemoryMemberAuthRepository
from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.models.member import Member
from app.services.members.member_auth_service import MemberAuthService
from app.services.members.member_service import MemberDataService


@pytest.fixture
def member_repo():
    repo = InMemoryMemberRepository()
    repo.add_member(
        Member(
            id="mem_001",
            phone_hash="",
            display_name="Edna Maina",
            sacco_id="demo_sacco",
        ),
        phone_number="+254700000001",
    )
    repo.add_member(
        Member(
            id="mem_002",
            phone_hash="",
            display_name="Other Sacco Member",
            sacco_id="other_sacco",
        ),
        phone_number="+254700000002",
    )
    return repo


@pytest.fixture
def auth_repo():
    return InMemoryMemberAuthRepository()


@pytest.fixture
def auth_service(member_repo, auth_repo):
    m_svc = MemberDataService(repository=member_repo)
    return MemberAuthService(auth_repo=auth_repo, member_service=m_svc, session_ttl_minutes=15)


def test_request_otp_success(auth_service):
    success, msg, code = auth_service.request_otp("+254700000001", sacco_id="demo_sacco")
    assert success is True
    assert "verification code is" in msg
    assert code is not None
    assert len(code) == 6
    assert code.isdigit()


def test_request_otp_unregistered_phone(auth_service):
    success, msg, code = auth_service.request_otp("+254799999999", sacco_id="demo_sacco")
    assert success is False
    assert "not registered" in msg
    assert code is None


def test_request_otp_tenant_isolation(auth_service):
    # Member belongs to 'other_sacco', request sent to 'demo_sacco'
    success, msg, code = auth_service.request_otp("+254700000002", sacco_id="demo_sacco")
    assert success is False
    assert "Unauthorized" in msg


def test_verify_otp_valid_creates_session(auth_service):
    _, _, code = auth_service.request_otp("+254700000001", sacco_id="demo_sacco")
    success, session, msg = auth_service.verify_otp("+254700000001", code, sacco_id="demo_sacco")

    assert success is True
    assert session is not None
    assert session.member_id == "mem_001"
    assert session.is_active is True
    assert not session.is_expired
    assert "verified successfully" in msg
    assert auth_service.is_session_active("+254700000001", sacco_id="demo_sacco") is True


def test_verify_otp_invalid_code_decrements_attempts(auth_service):
    _, _, _ = auth_service.request_otp("+254700000001", sacco_id="demo_sacco")
    success, session, msg = auth_service.verify_otp("+254700000001", "000000", sacco_id="demo_sacco")

    assert success is False
    assert session is None
    assert "Invalid verification code" in msg
    assert "2 attempt(s) remaining" in msg
    assert auth_service.is_session_active("+254700000001", sacco_id="demo_sacco") is False


def test_verify_otp_exceeded_attempts(auth_service):
    _, _, _ = auth_service.request_otp("+254700000001", sacco_id="demo_sacco")
    auth_service.verify_otp("+254700000001", "111111", sacco_id="demo_sacco")
    auth_service.verify_otp("+254700000001", "222222", sacco_id="demo_sacco")
    auth_service.verify_otp("+254700000001", "333333", sacco_id="demo_sacco")

    # 4th attempt
    success, session, msg = auth_service.verify_otp("+254700000001", "444444", sacco_id="demo_sacco")
    assert success is False
    assert "Too many failed attempts" in msg


def test_session_expiry(auth_service, auth_repo):
    _, _, code = auth_service.request_otp("+254700000001", sacco_id="demo_sacco")
    success, session, _ = auth_service.verify_otp("+254700000001", code, sacco_id="demo_sacco")
    assert success is True

    # Manually backdate expiration in repo
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert auth_service.is_session_active("+254700000001", sacco_id="demo_sacco") is False


def test_terminate_session(auth_service):
    _, _, code = auth_service.request_otp("+254700000001", sacco_id="demo_sacco")
    auth_service.verify_otp("+254700000001", code, sacco_id="demo_sacco")
    assert auth_service.is_session_active("+254700000001", sacco_id="demo_sacco") is True

    auth_service.terminate_session("+254700000001", sacco_id="demo_sacco")
    assert auth_service.is_session_active("+254700000001", sacco_id="demo_sacco") is False
