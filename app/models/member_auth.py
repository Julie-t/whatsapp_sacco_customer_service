"""Domain models for member authentication, sessions, audits, and change requests."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ChangeRequestType(str, Enum):
    PHONE_NUMBER = "phone_number"
    NEXT_OF_KIN = "next_of_kin"
    EMAIL = "email"
    WITHDRAWAL_NOTICE = "withdrawal_notice"
    OTHER = "other"


class ChangeRequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class OTPChallenge:
    id: str
    phone_number: str
    phone_hash: str
    otp_code_hash: str
    salt: str
    sacco_id: str
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return now >= exp

    @property
    def has_exceeded_attempts(self) -> bool:
        return self.attempts >= self.max_attempts


@dataclass
class MemberSession:
    session_id: str
    member_id: str
    phone_number: str
    phone_hash: str
    sacco_id: str
    authenticated_at: datetime
    expires_at: datetime
    is_active: bool = True

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return now >= exp or not self.is_active


@dataclass
class MemberAuditLog:
    sacco_id: str
    action: str
    id: Optional[int] = None
    member_id: Optional[str] = None
    phone_hash: Optional[str] = None
    resource_type: str = "financial_data"
    accessed_fields: list[str] = field(default_factory=list)
    channel: str = "whatsapp"
    ip_address: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MemberChangeRequest:
    id: str
    sacco_id: str
    member_id: str
    change_type: ChangeRequestType
    proposed_payload: dict[str, Any]
    status: ChangeRequestStatus = ChangeRequestStatus.PENDING
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
