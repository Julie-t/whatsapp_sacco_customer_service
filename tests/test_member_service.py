"""Unit tests for MemberDataService."""

import pytest

from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.models.member import Member, MemberAccount, MemberLoan
from app.services.members.member_service import MemberDataService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KNOWN_PHONE = "whatsapp:+254700000001"
UNKNOWN_PHONE = "whatsapp:+254799999999"


@pytest.fixture
def service():
    repo = InMemoryMemberRepository()
    repo.add_member(
        member=Member(id="mem_001", phone_hash="", display_name="Alice"),
        phone_number=KNOWN_PHONE,
        accounts=[
            MemberAccount(id=1, member_id="mem_001", account_type="savings", account_name="Regular Savings", balance=32450.0),
            MemberAccount(id=2, member_id="mem_001", account_type="shares", account_name="Share Capital", balance=15000.0),
        ],
        loans=[
            MemberLoan(
                id=1,
                member_id="mem_001",
                loan_type="development",
                principal=200000.0,
                balance_remaining=125000.0,
                monthly_instalment=4500.0,
                interest_rate=12.0,
                term_months=48,
                months_paid=18,
            ),
        ],
    )
    repo.add_member(
        member=Member(id="mem_002", phone_hash="", display_name="Bob"),
        phone_number="whatsapp:+254700000002",
    )
    return MemberDataService(repository=repo)


# ---------------------------------------------------------------------------
# resolve_member
# ---------------------------------------------------------------------------


def test_resolve_member_known(service):
    profile = service.resolve_member(KNOWN_PHONE)
    assert profile is not None
    assert profile.id == "mem_001"
    assert profile.display_name == "Alice"


def test_resolve_member_unknown(service):
    assert service.resolve_member(UNKNOWN_PHONE) is None


# ---------------------------------------------------------------------------
# get_account_summary
# ---------------------------------------------------------------------------


def test_get_account_summary(service):
    accounts = service.get_account_summary("mem_001")
    assert len(accounts) == 2
    assert accounts[0].balance == 32450.0


def test_get_account_summary_empty(service):
    accounts = service.get_account_summary("mem_002")
    assert accounts == []


# ---------------------------------------------------------------------------
# get_loan_summary
# ---------------------------------------------------------------------------


def test_get_loan_summary(service):
    loans = service.get_loan_summary("mem_001")
    assert len(loans) == 1
    assert loans[0].loan_type == "development"
    assert loans[0].balance_remaining == 125000.0


def test_get_loan_summary_empty(service):
    assert service.get_loan_summary("mem_002") == []


# ---------------------------------------------------------------------------
# get_member_snapshot
# ---------------------------------------------------------------------------


def test_get_member_snapshot_known(service):
    snapshot = service.get_member_snapshot(KNOWN_PHONE)
    assert snapshot is not None
    assert snapshot.profile.id == "mem_001"
    assert len(snapshot.accounts) == 2
    assert len(snapshot.loans) == 1


def test_get_member_snapshot_unknown(service):
    assert service.get_member_snapshot(UNKNOWN_PHONE) is None


def test_snapshot_profile_matches_resolve(service):
    profile = service.resolve_member(KNOWN_PHONE)
    snapshot = service.get_member_snapshot(KNOWN_PHONE)
    assert snapshot.profile == profile
