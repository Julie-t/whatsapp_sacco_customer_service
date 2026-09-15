"""PostgreSQL repository for Member Authentication, Sessions, Audits, and Change Requests."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.database.connection import get_connection
from app.database.member_repository import _hash_phone
from app.models.member_auth import (
    ChangeRequestStatus,
    ChangeRequestType,
    MemberAuditLog,
    MemberChangeRequest,
    MemberSession,
    OTPChallenge,
)

logger = logging.getLogger(__name__)


class MemberAuthRepository:
    """PostgreSQL storage for member security and governance."""

    # ------------------------------------------------------------------
    # OTP Challenges
    # ------------------------------------------------------------------

    def save_otp_challenge(self, challenge: OTPChallenge) -> None:
        """Store a new OTP verification challenge."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO member_otp_challenges (
                    id, phone_number, phone_hash, otp_code_hash, salt, sacco_id,
                    attempts, max_attempts, verified, created_at, expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    challenge.id,
                    challenge.phone_number,
                    challenge.phone_hash,
                    challenge.otp_code_hash,
                    challenge.salt,
                    challenge.sacco_id,
                    challenge.attempts,
                    challenge.max_attempts,
                    challenge.verified,
                    challenge.created_at,
                    challenge.expires_at,
                ),
            )

    def get_latest_otp_challenge(self, phone_number: str, sacco_id: str) -> Optional[OTPChallenge]:
        """Fetch the most recent unverified OTP challenge for a phone and SACCO."""
        phone_hash = _hash_phone(phone_number)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, phone_number, phone_hash, otp_code_hash, salt, sacco_id,
                       attempts, max_attempts, verified, created_at, expires_at
                FROM member_otp_challenges
                WHERE phone_hash = %s AND sacco_id = %s AND verified = false
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (phone_hash, sacco_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return OTPChallenge(
                id=row[0],
                phone_number=row[1],
                phone_hash=row[2],
                otp_code_hash=row[3],
                salt=row[4],
                sacco_id=row[5],
                attempts=row[6],
                max_attempts=row[7],
                verified=row[8],
                created_at=row[9],
                expires_at=row[10],
            )

    def increment_otp_attempts(self, challenge_id: str) -> int:
        """Increment attempt counter and return new count."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE member_otp_challenges
                SET attempts = attempts + 1
                WHERE id = %s
                RETURNING attempts
                """,
                (challenge_id,),
            )
            row = cur.fetchone()
            return row[0] if row else 0

    def mark_otp_verified(self, challenge_id: str) -> None:
        """Mark challenge as successfully verified."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE member_otp_challenges
                SET verified = true
                WHERE id = %s
                """,
                (challenge_id,),
            )

    # ------------------------------------------------------------------
    # Member Sessions
    # ------------------------------------------------------------------

    def save_session(self, session: MemberSession) -> None:
        """Save a new active member session, deactivating any existing sessions for this phone."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE member_sessions
                SET is_active = false
                WHERE phone_hash = %s AND sacco_id = %s
                """,
                (session.phone_hash, session.sacco_id),
            )
            cur.execute(
                """
                INSERT INTO member_sessions (
                    session_id, member_id, phone_number, phone_hash, sacco_id,
                    authenticated_at, expires_at, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session.session_id,
                    session.member_id,
                    session.phone_number,
                    session.phone_hash,
                    session.sacco_id,
                    session.authenticated_at,
                    session.expires_at,
                    session.is_active,
                ),
            )

    def get_active_session(self, phone_number: str, sacco_id: str) -> Optional[MemberSession]:
        """Retrieve current active, unexpired session for phone and SACCO."""
        phone_hash = _hash_phone(phone_number)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id, member_id, phone_number, phone_hash, sacco_id,
                       authenticated_at, expires_at, is_active
                FROM member_sessions
                WHERE phone_hash = %s AND sacco_id = %s AND is_active = true AND expires_at > NOW()
                ORDER BY authenticated_at DESC
                LIMIT 1
                """,
                (phone_hash, sacco_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return MemberSession(
                session_id=row[0],
                member_id=row[1],
                phone_number=row[2],
                phone_hash=row[3],
                sacco_id=row[4],
                authenticated_at=row[5],
                expires_at=row[6],
                is_active=row[7],
            )

    def terminate_sessions_for_phone(self, phone_number: str, sacco_id: str) -> None:
        """Deactivate all sessions for phone number."""
        phone_hash = _hash_phone(phone_number)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE member_sessions
                SET is_active = false
                WHERE phone_hash = %s AND sacco_id = %s
                """,
                (phone_hash, sacco_id),
            )

    # ------------------------------------------------------------------
    # Audit Logs
    # ------------------------------------------------------------------

    def log_audit_event(self, event: MemberAuditLog) -> int:
        """Record an immutable sensitive data access or auth event."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO member_audit_logs (
                    sacco_id, member_id, phone_hash, action, resource_type,
                    accessed_fields, channel, ip_address, details, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    event.sacco_id,
                    event.member_id,
                    event.phone_hash,
                    event.action,
                    event.resource_type,
                    event.accessed_fields,
                    event.channel,
                    event.ip_address,
                    json.dumps(event.details),
                    event.created_at,
                ),
            )
            row = cur.fetchone()
            return row[0] if row else 0

    def get_audit_logs(self, sacco_id: str, member_id: Optional[str] = None, limit: int = 50) -> list[MemberAuditLog]:
        """Fetch audit log history for compliance inspection."""
        with get_connection() as conn, conn.cursor() as cur:
            if member_id:
                cur.execute(
                    """
                    SELECT id, sacco_id, member_id, phone_hash, action, resource_type,
                           accessed_fields, channel, ip_address, details, created_at
                    FROM member_audit_logs
                    WHERE sacco_id = %s AND member_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (sacco_id, member_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, sacco_id, member_id, phone_hash, action, resource_type,
                           accessed_fields, channel, ip_address, details, created_at
                    FROM member_audit_logs
                    WHERE sacco_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (sacco_id, limit),
                )
            rows = cur.fetchall()
            logs = []
            for r in rows:
                details = r[9] if isinstance(r[9], dict) else json.loads(r[9] or "{}")
                logs.append(
                    MemberAuditLog(
                        id=r[0],
                        sacco_id=r[1],
                        member_id=r[2],
                        phone_hash=r[3],
                        action=r[4],
                        resource_type=r[5],
                        accessed_fields=r[6] or [],
                        channel=r[7],
                        ip_address=r[8],
                        details=details,
                        created_at=r[10],
                    )
                )
            return logs

    # ------------------------------------------------------------------
    # Account Change Requests (Read/Write Separation)
    # ------------------------------------------------------------------

    def create_change_request(self, req: MemberChangeRequest) -> MemberChangeRequest:
        """Create a pending change request."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO member_change_requests (
                    id, sacco_id, member_id, change_type, proposed_payload,
                    status, requested_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    req.id,
                    req.sacco_id,
                    req.member_id,
                    req.change_type.value if hasattr(req.change_type, "value") else str(req.change_type),
                    json.dumps(req.proposed_payload),
                    req.status.value if hasattr(req.status, "value") else str(req.status),
                    req.requested_at,
                ),
            )
        return req

    def get_change_request(self, req_id: str) -> Optional[MemberChangeRequest]:
        """Fetch change request by ID."""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sacco_id, member_id, change_type, proposed_payload,
                       status, requested_at, reviewed_by, reviewed_at, rejection_reason
                FROM member_change_requests
                WHERE id = %s
                """,
                (req_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            payload = row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}")
            return MemberChangeRequest(
                id=row[0],
                sacco_id=row[1],
                member_id=row[2],
                change_type=ChangeRequestType(row[3]),
                proposed_payload=payload,
                status=ChangeRequestStatus(row[5]),
                requested_at=row[6],
                reviewed_by=row[7],
                reviewed_at=row[8],
                rejection_reason=row[9],
            )
