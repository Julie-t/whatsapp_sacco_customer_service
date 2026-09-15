"""Unit tests for MemberRepository and InMemoryMemberRepository."""

import hashlib

import pytest

from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.database.member_repository import _hash_phone
from app.models.member import Member, MemberAccount, MemberLoan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo():
    """Pre-loaded in-memory repository for testing."""
    r = InMemoryMemberRepository()
    r.add_member(
        member=Member(id="mem_001", phone_hash="", display_name="Alice"),
        phone_number="whatsapp:+254700000001",
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
    r.add_member(
        member=Member(id="mem_002", phone_hash="", display_name="Bob", preferred_language="en"),
        phone_number="whatsapp:+254700000002",
        accounts=[
            MemberAccount(id=3, member_id="mem_002", account_type="savings", account_name="Regular Savings", balance=78200.0),
        ],
    )
    return r


# ---------------------------------------------------------------------------
# Phone hashing
# ---------------------------------------------------------------------------


def test_hash_phone_consistent():
    phone = "whatsapp:+254700000001"
    assert _hash_phone(phone) == _hash_phone(phone)


def test_hash_phone_sha256():
    phone = "whatsapp:+254700000001"
    expected = hashlib.sha256(phone.encode("utf-8")).hexdigest()
    assert _hash_phone(phone) == expected


# ---------------------------------------------------------------------------
# Phone lookup
# ---------------------------------------------------------------------------


def test_get_by_phone_known(repo):
    member = repo.get_by_phone("whatsapp:+254700000001")
    assert member is not None
    assert member.id == "mem_001"
    assert member.display_name == "Alice"


def test_get_by_phone_unknown(repo):
    assert repo.get_by_phone("whatsapp:+254799999999") is None


# ---------------------------------------------------------------------------
# ID lookup
# ---------------------------------------------------------------------------


def test_get_by_id_known(repo):
    member = repo.get_by_id("mem_001")
    assert member is not None
    assert member.display_name == "Alice"


def test_get_by_id_unknown(repo):
    assert repo.get_by_id("mem_999") is None


# ---------------------------------------------------------------------------
# Account retrieval
# ---------------------------------------------------------------------------


def test_get_accounts_returns_correct_accounts(repo):
    accounts = repo.get_accounts("mem_001")
    assert len(accounts) == 2
    types = {a.account_type for a in accounts}
    assert types == {"savings", "shares"}


def test_get_accounts_empty_for_unknown_member(repo):
    assert repo.get_accounts("mem_999") == []


# ---------------------------------------------------------------------------
# Loan retrieval
# ---------------------------------------------------------------------------


def test_get_loans_returns_correct_loans(repo):
    loans = repo.get_loans("mem_001")
    assert len(loans) == 1
    assert loans[0].loan_type == "development"
    assert loans[0].balance_remaining == 125000.0


def test_get_loans_empty_for_member_without_loans(repo):
    assert repo.get_loans("mem_002") == []


def test_get_loans_empty_for_unknown_member(repo):
    assert repo.get_loans("mem_999") == []


# ---------------------------------------------------------------------------
# Multiple members don't interfere
# ---------------------------------------------------------------------------


def test_multiple_members_isolated(repo):
    alice = repo.get_by_phone("whatsapp:+254700000001")
    bob = repo.get_by_phone("whatsapp:+254700000002")
    assert alice.id != bob.id
    assert repo.get_accounts("mem_001") != repo.get_accounts("mem_002")
