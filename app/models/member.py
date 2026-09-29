"""Member domain models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Member:
    """Core member identity record."""

    id: str
    phone_hash: str
    display_name: str
    preferred_language: str = "en"
    knowledge_level: str = "beginner"
    sacco_id: str = "demo_sacco"
    is_demo: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class MemberAccount:
    """A single financial account belonging to a member."""

    id: int = 0
    member_id: str = ""
    account_type: str = ""  # savings, shares, fixed_deposit, target_savings
    account_name: str = ""
    balance: float = 0.0
    currency: str = "KES"
    is_demo: bool = True
    updated_at: datetime | None = None


@dataclass
class MemberLoan:
    """A single loan belonging to a member."""

    id: int = 0
    member_id: str = ""
    loan_type: str = ""  # development, emergency, school_fees, asset_finance
    principal: float = 0.0
    balance_remaining: float = 0.0
    monthly_instalment: float = 0.0
    interest_rate: float = 0.0
    term_months: int = 0
    months_paid: int = 0
    status: str = "active"  # active, cleared, defaulted
    currency: str = "KES"
    is_demo: bool = True
    disbursed_at: datetime | None = None
    updated_at: datetime | None = None
