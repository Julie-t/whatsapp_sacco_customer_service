"""Data models and enums for System 11 SACCO Admin & Operations."""

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class AdminRole(str, Enum):
    ADMIN = "admin"
    STAFF = "staff"
    COMPLIANCE = "compliance"
    SUPERADMIN = "superadmin"


class EscalationCategory(str, Enum):
    DISPUTE = "dispute"
    COMPLAINT = "complaint"
    FRAUD = "fraud"
    COMPLEX_QUERY = "complex_query"
    OTHER = "other"


class EscalationStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EscalationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class KnowledgeDocumentStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class AdminUser(BaseModel):
    id: str
    username: str
    password_hash: str
    email: Optional[str] = None
    sacco_id: str = "demo_sacco"
    role: AdminRole = AdminRole.STAFF
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Escalation(BaseModel):
    id: int
    sacco_id: str = "demo_sacco"
    member_id: Optional[str] = None
    conversation_key: str
    query: str
    category: EscalationCategory = EscalationCategory.COMPLEX_QUERY
    status: EscalationStatus = EscalationStatus.OPEN
    priority: EscalationPriority = EscalationPriority.MEDIUM
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class KnowledgeDocument(BaseModel):
    id: str
    sacco_id: str = "demo_sacco"
    title: str
    category: str = "general"
    content: str
    version: int = 1
    status: KnowledgeDocumentStatus = KnowledgeDocumentStatus.DRAFT
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    effective_date: date = Field(default_factory=date.today)
    qdrant_indexed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AdminAuditLog(BaseModel):
    id: int
    sacco_id: str = "demo_sacco"
    admin_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
