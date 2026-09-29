"""Audit Service for member sensitive data access tracking (System 12)."""

import logging
from typing import Any, Optional

from app.database.member_auth_repository import MemberAuthRepository
from app.database.in_memory_member_auth_repository import InMemoryMemberAuthRepository
from app.database.member_repository import _hash_phone
from app.models.member_auth import MemberAuditLog

logger = logging.getLogger(__name__)


class MemberAuditService:
    """Records audit trails for compliance, fraud monitoring, and sensitive data access."""

    def __init__(self, repo: Optional[MemberAuthRepository | InMemoryMemberAuthRepository] = None) -> None:
        self._repo = repo or MemberAuthRepository()

    def log_access(
        self,
        sacco_id: str,
        action: str,
        member_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        resource_type: str = "financial_data",
        accessed_fields: Optional[list[str]] = None,
        channel: str = "whatsapp",
        ip_address: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> int:
        """Record an access log entry."""
        phone_hash = _hash_phone(phone_number) if phone_number else None
        event = MemberAuditLog(
            sacco_id=sacco_id,
            action=action,
            member_id=member_id,
            phone_hash=phone_hash,
            resource_type=resource_type,
            accessed_fields=accessed_fields or [],
            channel=channel,
            ip_address=ip_address,
            details=details or {},
        )
        return self._repo.log_audit_event(event)

    def get_logs(self, sacco_id: str, member_id: Optional[str] = None, limit: int = 50) -> list[MemberAuditLog]:
        return self._repo.get_audit_logs(sacco_id=sacco_id, member_id=member_id, limit=limit)
