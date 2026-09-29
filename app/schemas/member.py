"""Pydantic schemas for member data API contracts."""

from pydantic import BaseModel, Field


class MemberProfile(BaseModel):
    """Public-facing member profile (no phone number or sensitive data)."""

    id: str
    display_name: str
    preferred_language: str = "en"
    knowledge_level: str = "beginner"
    sacco_id: str = "demo_sacco"


class AccountSummary(BaseModel):
    """Summary of a single member account."""

    account_type: str
    account_name: str
    balance: float
    currency: str = "KES"


class LoanSummary(BaseModel):
    """Summary of a single member loan."""

    loan_type: str
    principal: float
    balance_remaining: float
    monthly_instalment: float
    interest_rate: float
    term_months: int
    months_paid: int
    status: str
    currency: str = "KES"


class MemberDataResponse(BaseModel):
    """Combined member snapshot returned by the member data service."""

    profile: MemberProfile
    accounts: list[AccountSummary] = Field(default_factory=list)
    loans: list[LoanSummary] = Field(default_factory=list)


class MemberNotFoundResponse(BaseModel):
    """Structured fallback when a member cannot be resolved."""

    recognized: bool = False
    message: str = (
        "I couldn't verify your member information. "
        "Please contact a SACCO representative for help with personal account queries."
    )
