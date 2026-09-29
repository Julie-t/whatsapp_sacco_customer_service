"""Escalations management service for SACCO staff and automated triage capture."""

import logging
from typing import Any, Optional

from app.database.admin_repository import AdminRepository
from app.models.admin import (
    Escalation,
    EscalationCategory,
    EscalationPriority,
    EscalationStatus,
)
from app.schemas.admin import EscalationCreate, EscalationUpdate

logger = logging.getLogger(__name__)


class AdminEscalationService:
    def __init__(self, repo: Optional[AdminRepository] = None):
        self.repo = repo or AdminRepository()

    def record_from_conversation(
        self,
        conversation_key: str,
        query: str,
        member_id: Optional[str] = None,
        sacco_id: str = "demo_sacco",
        category: Optional[EscalationCategory | str] = None,
        priority: Optional[EscalationPriority | str] = None,
    ) -> Escalation:
        """Automatically create an escalation ticket when triage flags human intervention."""
        lowered = query.lower()
        if category is None:
            category = EscalationCategory.COMPLEX_QUERY
            priority = EscalationPriority.MEDIUM

            if any(w in lowered for k in ("dispute", "uncredited", "wrong deduction", "fraud") for w in (k,)):
                category = EscalationCategory.DISPUTE
                priority = EscalationPriority.HIGH
            elif any(w in lowered for k in ("stolen", "hacked", "freeze") for w in (k,)):
                category = EscalationCategory.FRAUD
                priority = EscalationPriority.URGENT
            elif any(w in lowered for k in ("complaint", "rude", "poor service") for w in (k,)):
                category = EscalationCategory.COMPLAINT
                priority = EscalationPriority.MEDIUM
        else:
            if isinstance(category, str):
                category = EscalationCategory(category)
            if priority is None:
                priority = EscalationPriority.HIGH
            elif isinstance(priority, str):
                priority = EscalationPriority(priority)

        try:
            return self.repo.create_escalation(
                conversation_key=conversation_key,
                query=query,
                sacco_id=sacco_id,
                member_id=member_id,
                category=category,
                priority=priority,
                notes="Auto-captured from WhatsApp member triage.",
            )
        except Exception as exc:
            if member_id is not None:
                logger.debug("Retrying escalation without member_id constraint: %s", exc)
                return self.repo.create_escalation(
                    conversation_key=conversation_key,
                    query=query,
                    sacco_id=sacco_id,
                    member_id=None,
                    category=category,
                    priority=priority,
                    notes=f"Auto-captured from WhatsApp (unlinked member: {member_id}).",
                )
            raise exc

    def create_escalation(
        self,
        esc_in: EscalationCreate,
        sacco_id: str = "demo_sacco",
    ) -> Escalation:
        return self.repo.create_escalation(
            conversation_key=esc_in.conversation_key,
            query=esc_in.query,
            sacco_id=sacco_id,
            member_id=esc_in.member_id,
            category=esc_in.category,
            priority=esc_in.priority,
            notes=esc_in.notes,
        )

    def list_escalations(
        self,
        sacco_id: str = "demo_sacco",
        status: Optional[EscalationStatus] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.repo.list_escalations(sacco_id=sacco_id, status=status, limit=limit)

    def update_escalation(
        self,
        escalation_id: int,
        esc_up: EscalationUpdate,
        admin_id: str,
        sacco_id: str = "demo_sacco",
    ) -> Optional[Escalation]:
        updated = self.repo.update_escalation(
            escalation_id=escalation_id,
            sacco_id=sacco_id,
            status=esc_up.status,
            priority=esc_up.priority,
            notes=esc_up.notes,
            assigned_to=esc_up.assigned_to,
        )
        if updated:
            self.repo.record_audit(
                action="update_escalation",
                resource_type="escalation",
                resource_id=str(escalation_id),
                admin_id=admin_id,
                sacco_id=sacco_id,
                details={"status": updated.status.value, "priority": updated.priority.value},
            )
        return updated
