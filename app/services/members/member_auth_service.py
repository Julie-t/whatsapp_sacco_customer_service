"""Member Authentication & Session Management Service (System 12).

Provides 6-digit OTP verification, salted hashing, and 15-minute authenticated sessions
to protect member financial records over WhatsApp and API transports.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Optional, Tuple
import uuid

from app.database.member_auth_repository import MemberAuthRepository
from app.database.in_memory_member_auth_repository import InMemoryMemberAuthRepository
from app.database.member_repository import _hash_phone
from app.models.member_auth import MemberAuditLog, MemberSession, OTPChallenge
from app.services.members.member_service import MemberDataService

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_MINUTES = 15
DEFAULT_OTP_EXPIRY_MINUTES = 5


class MemberAuthService:
    """Coordinates OTP issuance, verification, and short-lived session management."""

    def __init__(
        self,
        auth_repo: Optional[MemberAuthRepository | InMemoryMemberAuthRepository] = None,
        member_service: Optional[MemberDataService] = None,
        session_ttl_minutes: int = DEFAULT_SESSION_TTL_MINUTES,
    ) -> None:
        self._auth_repo = auth_repo or MemberAuthRepository()
        self._member_svc = member_service or MemberDataService()
        self.session_ttl_minutes = session_ttl_minutes

    @staticmethod
    def _hash_otp(code: str, salt: str) -> str:
        """Compute salted SHA-256 hash of OTP code."""
        return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()

    def request_otp(
        self,
        phone_number: str,
        sacco_id: str = "demo_sacco",
    ) -> Tuple[bool, str, Optional[str]]:
        """Generate and issue a 6-digit verification code.

        Returns (success, user_message, demo_otp_code).
        """
        # 1. Verify phone is registered with SACCO
        profile = self._member_svc.resolve_member(phone_number)
        if not profile:
            self._auth_repo.log_audit_event(
                MemberAuditLog(
                    sacco_id=sacco_id,
                    phone_hash=_hash_phone(phone_number),
                    action="AUTH_OTP_REJECTED_UNREGISTERED",
                    resource_type="auth",
                    channel="whatsapp",
                    details={"reason": "phone_not_found"},
                )
            )
            return False, "This phone number is not registered with the SACCO. Please contact your SACCO branch.", None

        # 2. Check tenant match
        if profile.sacco_id != sacco_id:
            logger.warning("Tenant mismatch for phone %s (profile=%s, target=%s)", phone_number, profile.sacco_id, sacco_id)
            return False, "Unauthorized: Membership belongs to a different SACCO tenant.", None

        # 3. Generate 6-digit numeric OTP
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        salt = secrets.token_hex(16)
        code_hash = self._hash_otp(code, salt)
        challenge_id = f"otp_{uuid.uuid4().hex[:8]}"

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=DEFAULT_OTP_EXPIRY_MINUTES)

        challenge = OTPChallenge(
            id=challenge_id,
            phone_number=phone_number,
            phone_hash=_hash_phone(phone_number),
            otp_code_hash=code_hash,
            salt=salt,
            sacco_id=sacco_id,
            expires_at=expires_at,
            created_at=now,
        )
        self._auth_repo.save_otp_challenge(challenge)

        # 4. Log audit event
        self._auth_repo.log_audit_event(
            MemberAuditLog(
                sacco_id=sacco_id,
                member_id=profile.id,
                phone_hash=_hash_phone(phone_number),
                action="AUTH_OTP_ISSUED",
                resource_type="auth",
                channel="whatsapp",
                details={"challenge_id": challenge_id, "expires_at": expires_at.isoformat()},
            )
        )

        msg = (
            f"Your verification code is {code}. It expires in {DEFAULT_OTP_EXPIRY_MINUTES} minutes. "
            "Please reply with this code to securely view your account details."
        )
        return True, msg, code

    def verify_otp(
        self,
        phone_number: str,
        otp_code: str,
        sacco_id: str = "demo_sacco",
    ) -> Tuple[bool, Optional[MemberSession], str]:
        """Validate candidate OTP code and issue a short-lived authenticated session."""
        challenge = self._auth_repo.get_latest_otp_challenge(phone_number, sacco_id)
        if not challenge:
            return False, None, "No active verification request found. Please reply VERIFY to receive a new code."

        if challenge.is_expired:
            self._auth_repo.log_audit_event(
                MemberAuditLog(
                    sacco_id=sacco_id,
                    phone_hash=_hash_phone(phone_number),
                    action="AUTH_OTP_EXPIRED",
                    resource_type="auth",
                    channel="whatsapp",
                    details={"challenge_id": challenge.id},
                )
            )
            return False, None, "This verification code has expired. Please reply VERIFY to receive a fresh code."

        if challenge.has_exceeded_attempts:
            return False, None, "Too many failed attempts. Please request a fresh verification code."

        # Check hash
        candidate_hash = self._hash_otp(otp_code.strip(), challenge.salt)
        if candidate_hash != challenge.otp_code_hash:
            attempts = self._auth_repo.increment_otp_attempts(challenge.id)
            self._auth_repo.log_audit_event(
                MemberAuditLog(
                    sacco_id=sacco_id,
                    phone_hash=_hash_phone(phone_number),
                    action="AUTH_OTP_FAILED",
                    resource_type="auth",
                    channel="whatsapp",
                    details={"challenge_id": challenge.id, "attempts": attempts},
                )
            )
            rem = max(0, challenge.max_attempts - attempts)
            return False, None, f"Invalid verification code. {rem} attempt(s) remaining."

        # Mark challenge verified
        self._auth_repo.mark_otp_verified(challenge.id)

        # Resolve member profile for session creation
        profile = self._member_svc.resolve_member(phone_number)
        member_id = profile.id if profile else "unknown"

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.session_ttl_minutes)
        session_id = f"sess_{uuid.uuid4().hex[:12]}"

        session = MemberSession(
            session_id=session_id,
            member_id=member_id,
            phone_number=phone_number,
            phone_hash=_hash_phone(phone_number),
            sacco_id=sacco_id,
            authenticated_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        self._auth_repo.save_session(session)

        self._auth_repo.log_audit_event(
            MemberAuditLog(
                sacco_id=sacco_id,
                member_id=member_id,
                phone_hash=_hash_phone(phone_number),
                action="AUTH_SESSION_ESTABLISHED",
                resource_type="auth",
                channel="whatsapp",
                details={"session_id": session_id, "ttl_minutes": self.session_ttl_minutes},
            )
        )

        return True, session, f"Identity verified successfully. You can now access your accounts for the next {self.session_ttl_minutes} minutes."

    def is_session_active(self, phone_number: str, sacco_id: str = "demo_sacco") -> bool:
        """Check if phone number currently holds an unexpired authenticated session."""
        session = self._auth_repo.get_active_session(phone_number, sacco_id)
        return bool(session and not session.is_expired)

    def get_active_session(self, phone_number: str, sacco_id: str = "demo_sacco") -> Optional[MemberSession]:
        """Fetch active session."""
        return self._auth_repo.get_active_session(phone_number, sacco_id)

    def terminate_session(self, phone_number: str, sacco_id: str = "demo_sacco") -> None:
        """Log out / clear active session."""
        self._auth_repo.terminate_sessions_for_phone(phone_number, sacco_id)
        self._auth_repo.log_audit_event(
            MemberAuditLog(
                sacco_id=sacco_id,
                phone_hash=_hash_phone(phone_number),
                action="AUTH_SESSION_TERMINATED",
                resource_type="auth",
                channel="whatsapp",
            )
        )
