"""Member Authentication and Session Endpoints (System 12)."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from app.schemas.member_auth import (
    MemberSessionResponse,
    OTPRequest,
    OTPRequestResponse,
    OTPVerifyRequest,
)
from app.services.members.member_auth_service import MemberAuthService

router = APIRouter(prefix="/api/members/auth", tags=["member_auth"])

_auth_service: MemberAuthService | None = None


def _get_auth_service() -> MemberAuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = MemberAuthService()
    return _auth_service


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(body: OTPRequest):
    """Request a 6-digit OTP code sent to registered WhatsApp phone number."""
    svc = _get_auth_service()
    success, msg, demo_code = svc.request_otp(body.phone_number, sacco_id=body.sacco_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return OTPRequestResponse(
        challenge_id=f"otp_{body.phone_number[-4:]}",
        message=msg,
        expires_in_seconds=300,
        demo_otp=demo_code,
    )


@router.post("/verify-otp", response_model=MemberSessionResponse)
def verify_otp(body: OTPVerifyRequest):
    """Submit 6-digit OTP code to establish an authenticated session."""
    svc = _get_auth_service()
    success, session, msg = svc.verify_otp(body.phone_number, body.otp_code, sacco_id=body.sacco_id)
    if not success or not session:
        raise HTTPException(status_code=401, detail=msg)

    now = datetime.now(timezone.utc)
    exp = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    ttl = max(0, int((exp - now).total_seconds()))

    return MemberSessionResponse(
        session_id=session.session_id,
        member_id=session.member_id,
        phone_number=session.phone_number,
        sacco_id=session.sacco_id,
        authenticated=True,
        expires_at=session.expires_at,
        ttl_seconds_remaining=ttl,
    )


@router.get("/session", response_model=MemberSessionResponse)
def get_session(phone_number: str = Query(...), sacco_id: str = Query("demo_sacco")):
    """Check whether a member session is currently active."""
    svc = _get_auth_service()
    session = svc.get_active_session(phone_number, sacco_id=sacco_id)
    if not session or session.is_expired:
        raise HTTPException(status_code=404, detail="No active session found or session has expired")

    now = datetime.now(timezone.utc)
    exp = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    ttl = max(0, int((exp - now).total_seconds()))

    return MemberSessionResponse(
        session_id=session.session_id,
        member_id=session.member_id,
        phone_number=session.phone_number,
        sacco_id=session.sacco_id,
        authenticated=True,
        expires_at=session.expires_at,
        ttl_seconds_remaining=ttl,
    )


@router.post("/logout")
def logout(phone_number: str = Query(...), sacco_id: str = Query("demo_sacco")):
    """Terminate all active sessions for phone number."""
    svc = _get_auth_service()
    svc.terminate_session(phone_number, sacco_id=sacco_id)
    return {"message": "Session terminated successfully"}
