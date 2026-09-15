"""Pydantic schemas for member authentication, sessions, and change requests."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.member_auth import ChangeRequestType, ChangeRequestStatus


class OTPRequest(BaseModel):
    phone_number: str = Field(..., description="WhatsApp phone number with country code, e.g., +254700000001")
    sacco_id: str = Field(default="demo_sacco", description="Target SACCO tenant ID")


class OTPRequestResponse(BaseModel):
    challenge_id: str
    message: str
    expires_in_seconds: int
    demo_otp: Optional[str] = None  # Populated only in demo/testing mode for convenience


class OTPVerifyRequest(BaseModel):
    phone_number: str
    otp_code: str = Field(..., min_length=4, max_length=8)
    sacco_id: str = Field(default="demo_sacco")


class MemberSessionResponse(BaseModel):
    session_id: str
    member_id: str
    phone_number: str
    sacco_id: str
    authenticated: bool
    expires_at: datetime
    ttl_seconds_remaining: int


class AccountChangeRequestCreate(BaseModel):
    member_id: str
    sacco_id: str = "demo_sacco"
    change_type: ChangeRequestType
    payload: dict[str, Any]


class AccountChangeRequestResponse(BaseModel):
    id: str
    member_id: str
    sacco_id: str
    change_type: str
    status: str
    requested_at: datetime
    message: str


class MemberAuditLogResponse(BaseModel):
    id: int
    sacco_id: str
    member_id: Optional[str]
    action: str
    resource_type: str
    accessed_fields: list[str]
    channel: str
    created_at: datetime
