"""API integration tests for the member data endpoints and WhatsApp member routing."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database.in_memory_member_repository import InMemoryMemberRepository
from app.main import app
from app.models.member import Member, MemberAccount, MemberLoan
from app.schemas.message import IncomingWhatsAppMessage
from app.services.members.member_service import MemberDataService
from app.services.conversations.conversation_service import (
    _handle_member_query,
    MEMBER_NOT_RECOGNIZED,
    MEMBER_NO_ACCOUNTS,
)


client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KNOWN_PHONE = "whatsapp:+254700000001"
UNKNOWN_PHONE = "whatsapp:+254799999999"


@pytest.fixture
def member_service():
    """A MemberDataService backed by in-memory test data."""
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
    return MemberDataService(repository=repo)


@pytest.fixture
def member_service_no_accounts():
    """A MemberDataService where the member exists but has no accounts/loans."""
    repo = InMemoryMemberRepository()
    repo.add_member(
        member=Member(id="mem_empty", phone_hash="", display_name="Ghost"),
        phone_number=KNOWN_PHONE,
    )
    return MemberDataService(repository=repo)


# ---------------------------------------------------------------------------
# _handle_member_query unit tests (synchronous fast-path)
# ---------------------------------------------------------------------------


def test_handle_member_query_known_balance(member_service):
    response = _handle_member_query(KNOWN_PHONE, "What is my savings balance?", member_service)
    assert "KSh 32,450" in response
    assert "(demo data)" in response


def test_handle_member_query_unknown_phone(member_service):
    response = _handle_member_query(UNKNOWN_PHONE, "What is my balance?", member_service)
    assert response == MEMBER_NOT_RECOGNIZED


def test_handle_member_query_no_accounts(member_service_no_accounts):
    response = _handle_member_query(KNOWN_PHONE, "What is my balance?", member_service_no_accounts)
    assert response == MEMBER_NO_ACCOUNTS


def test_handle_member_query_loan(member_service):
    response = _handle_member_query(KNOWN_PHONE, "What is my loan status?", member_service)
    assert "KSh 125,000" in response


def test_handle_member_query_full_snapshot(member_service):
    response = _handle_member_query(KNOWN_PHONE, "Tell me about my SACCO info", member_service)
    assert "Alice" in response
    assert "KSh 32,450" in response
    assert "KSh 125,000" in response


# ---------------------------------------------------------------------------
# WhatsApp webhook endpoint tests
# ---------------------------------------------------------------------------


def _post_whatsapp(body: str, from_number: str = "whatsapp:+254700000000"):
    return client.post(
        "/webhooks/whatsapp",
        data={
            "From": from_number,
            "To": "whatsapp:+254711111111",
            "Body": body,
            "NumMedia": "0",
        },
    )


def test_webhook_returns_twiml_xml():
    """Any message should still return valid TwiML XML."""
    response = _post_whatsapp("Hello")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert "<?xml" in response.text
    assert "<Response>" in response.text


def test_webhook_greeting_still_works():
    """Greetings should still return the welcome menu, unaffected by member changes."""
    response = _post_whatsapp("Hello")
    assert "Karibu" in response.text


def test_no_source_citations_in_member_responses(member_service):
    """Member-data responses must never contain source citations."""
    response = _handle_member_query(KNOWN_PHONE, "What is my balance?", member_service)
    assert "Source:" not in response
    assert "source:" not in response
