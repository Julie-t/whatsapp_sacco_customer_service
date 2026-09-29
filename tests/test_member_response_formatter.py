"""Unit tests for the member response formatter."""

import pytest

from app.schemas.member import (
    AccountSummary,
    LoanSummary,
    MemberDataResponse,
    MemberProfile,
)
from app.services.members.member_response_formatter import (
    detect_sub_question,
    format_balance_response,
    format_full_snapshot,
    format_loan_response,
    format_member_response,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def full_snapshot():
    return MemberDataResponse(
        profile=MemberProfile(id="mem_001", display_name="Alice"),
        accounts=[
            AccountSummary(account_type="savings", account_name="Regular Savings", balance=32450.0, currency="KES"),
            AccountSummary(account_type="shares", account_name="Share Capital", balance=15000.0, currency="KES"),
        ],
        loans=[
            LoanSummary(
                loan_type="development",
                principal=200000.0,
                balance_remaining=125000.0,
                monthly_instalment=4500.0,
                interest_rate=12.0,
                term_months=48,
                months_paid=18,
                status="active",
                currency="KES",
            ),
        ],
    )


@pytest.fixture
def no_loans_snapshot():
    return MemberDataResponse(
        profile=MemberProfile(id="mem_003", display_name="Amina"),
        accounts=[
            AccountSummary(account_type="savings", account_name="Regular Savings", balance=5800.0, currency="KES"),
        ],
        loans=[],
    )


@pytest.fixture
def no_accounts_snapshot():
    return MemberDataResponse(
        profile=MemberProfile(id="mem_004", display_name="Omar"),
        accounts=[],
        loans=[],
    )


# ---------------------------------------------------------------------------
# Full snapshot formatting
# ---------------------------------------------------------------------------


def test_full_snapshot_contains_name(full_snapshot):
    text = format_full_snapshot(full_snapshot)
    assert "Alice" in text


def test_full_snapshot_contains_balance(full_snapshot):
    text = format_full_snapshot(full_snapshot)
    assert "KSh 32,450" in text
    assert "KSh 15,000" in text


def test_full_snapshot_contains_loan(full_snapshot):
    text = format_full_snapshot(full_snapshot)
    assert "KSh 125,000" in text
    assert "KSh 4,500" in text


def test_full_snapshot_demo_label(full_snapshot):
    text = format_full_snapshot(full_snapshot, demo_label=True)
    assert "(demo data)" in text


def test_full_snapshot_no_demo_label(full_snapshot):
    text = format_full_snapshot(full_snapshot, demo_label=False)
    assert "(demo data)" not in text


def test_no_loans_says_no_loans(no_loans_snapshot):
    text = format_full_snapshot(no_loans_snapshot)
    assert "no loans on record" in text.lower()


# ---------------------------------------------------------------------------
# Balance-only formatting
# ---------------------------------------------------------------------------


def test_balance_response(full_snapshot):
    text = format_balance_response(full_snapshot)
    assert "KSh 32,450" in text


def test_balance_response_no_accounts(no_accounts_snapshot):
    text = format_balance_response(no_accounts_snapshot)
    assert "don't have account information" in text.lower()


# ---------------------------------------------------------------------------
# Loan-only formatting
# ---------------------------------------------------------------------------


def test_loan_response(full_snapshot):
    text = format_loan_response(full_snapshot)
    assert "KSh 125,000" in text
    assert "development" in text.lower()


def test_loan_response_no_loans(no_loans_snapshot):
    text = format_loan_response(no_loans_snapshot)
    assert "no loans" in text.lower()


# ---------------------------------------------------------------------------
# No asterisks or em dashes in any output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("formatter", [format_full_snapshot, format_balance_response, format_loan_response])
def test_no_asterisks(full_snapshot, formatter):
    text = formatter(full_snapshot)
    assert "*" not in text


@pytest.mark.parametrize("formatter", [format_full_snapshot, format_balance_response, format_loan_response])
def test_no_em_dashes(full_snapshot, formatter):
    text = formatter(full_snapshot)
    assert "\u2014" not in text
    assert "\u2013" not in text


# ---------------------------------------------------------------------------
# KSh formatting
# ---------------------------------------------------------------------------


def test_ksh_formatting_with_commas(full_snapshot):
    text = format_full_snapshot(full_snapshot)
    assert "KSh 32,450" in text  # thousands separator


# ---------------------------------------------------------------------------
# Sub-question detection
# ---------------------------------------------------------------------------


def test_detect_balance_question():
    assert detect_sub_question("What is my savings balance?") == "balance"


def test_detect_loan_question():
    assert detect_sub_question("How much do I owe on my loan?") == "loan"


def test_detect_full_question():
    assert detect_sub_question("Show me my account summary") == "full"


# ---------------------------------------------------------------------------
# format_member_response routing
# ---------------------------------------------------------------------------


def test_format_member_response_balance(full_snapshot):
    text = format_member_response(full_snapshot, "What is my savings balance?")
    # Should get the balance-only response (no loan info)
    assert "KSh 32,450" in text


def test_format_member_response_loan(full_snapshot):
    text = format_member_response(full_snapshot, "What is my loan status?")
    assert "KSh 125,000" in text


def test_format_member_response_full(full_snapshot):
    text = format_member_response(full_snapshot, "Tell me everything")
    assert "Alice" in text
