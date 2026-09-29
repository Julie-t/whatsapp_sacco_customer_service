"""In-memory mock repository for Member Authentication, Sessions, Audits, and Change Requests."""

from datetime import datetime, timezone
from typing import Optional

from app.database.member_repository import _hash_phone
from app.models.member_auth import (
    ChangeRequestStatus,
    ChangeRequestType,
    MemberAuditLog,
    MemberChangeRequest,
    MemberSession,
    OTPChallenge,
)


class InMemoryMemberAuthRepository:
    """In-memory backing store for unit testing."""

    def __init__(self) -> None:
        self.otp_challenges: dict[str, OTPChallenge] = {}
        self.sessions: dict[str, MemberSession] = {}  # session_id -> MemberSession
        self.audit_logs: list[MemberAuditLog] = []
        self.change_requests: dict[str, MemberChangeRequest] = {}
        self._audit_seq = 1

    # ------------------------------------------------------------------
    # OTP Challenges
    # ------------------------------------------------------------------

    def save_otp_challenge(self, challenge: OTPChallenge) -> None:
        self.otp_challenges[challenge.id] = challenge

    def get_latest_otp_challenge(self, phone_number: str, sacco_id: str) -> Optional[OTPChallenge]:
        p_hash = _hash_phone(phone_number)
        matches = [
            c for c in self.otp_challenges.values()
            if c.phone_hash == p_hash and c.sacco_id == sacco_id and not c.verified
        ]
        if not matches:
            return None
        matches.sort(key=lambda c: c.created_at, reverse=True)
        return matches[0]

    def increment_otp_attempts(self, challenge_id: str) -> int:
        if challenge_id in self.otp_challenges:
            c = self.otp_challenges[challenge_id]
            c.attempts += 1
            return c.attempts
        return 0

    def mark_otp_verified(self, challenge_id: str) -> None:
        if challenge_id in self.otp_challenges:
            self.otp_challenges[challenge_id].verified = True

    # ------------------------------------------------------------------
    # Member Sessions
    # ------------------------------------------------------------------

    def save_session(self, session: MemberSession) -> None:
        # Deactivate existing sessions for same phone and SACCO
        for s in self.sessions.values():
            if s.phone_hash == session.phone_hash and s.sacco_id == session.sacco_id:
                s.is_active = False
        self.sessions[session.session_id] = session

    def get_active_session(self, phone_number: str, sacco_id: str) -> Optional[MemberSession]:
        p_hash = _hash_phone(phone_number)
        now = datetime.now(timezone.utc)
        for s in sorted(self.sessions.values(), key=lambda x: x.authenticated_at, reverse=True):
            if s.phone_hash == p_hash and s.sacco_id == sacco_id and s.is_active:
                exp = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=timezone.utc)
                if exp > now:
                    return s
                else:
                    s.is_active = False
        return None

    def terminate_sessions_for_phone(self, phone_number: str, sacco_id: str) -> None:
        p_hash = _hash_phone(phone_number)
        for s in self.sessions.values():
            if s.phone_hash == p_hash and s.sacco_id == sacco_id:
                s.is_active = False

    # ------------------------------------------------------------------
    # Audit Logs
    # ------------------------------------------------------------------

    def log_audit_event(self, event: MemberAuditLog) -> int:
        event.id = self._audit_seq
        self._audit_seq += 1
        self.audit_logs.append(event)
        return event.id

    def get_audit_logs(self, sacco_id: str, member_id: Optional[str] = None, limit: int = 50) -> list[MemberAuditLog]:
        res = [a for a in self.audit_logs if a.sacco_id == sacco_id]
        if member_id:
            res = [a for a in res if a.member_id == member_id]
        res.sort(key=lambda a: a.created_at, reverse=True)
        return res[:limit]

    # ------------------------------------------------------------------
    # Account Change Requests
    # ------------------------------------------------------------------

    def create_change_request(self, req: MemberChangeRequest) -> MemberChangeRequest:
        self.change_requests[req.id] = req
        return req

    def get_change_request(self, req_id: str) -> Optional[MemberChangeRequest]:
        return self.change_requests.get(req_id)
