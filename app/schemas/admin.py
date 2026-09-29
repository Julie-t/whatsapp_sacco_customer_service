"""Request and response schemas for System 11 Admin APIs."""

from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.admin import (
    AdminRole,
    EscalationCategory,
    EscalationPriority,
    EscalationStatus,
    KnowledgeDocumentStatus,
)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: AdminRole
    sacco_id: str


class AdminUserRead(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    sacco_id: str
    role: AdminRole
    is_active: bool
    created_at: datetime


class EscalationCreate(BaseModel):
    conversation_key: str
    query: str
    member_id: Optional[str] = None
    category: EscalationCategory = EscalationCategory.COMPLEX_QUERY
    priority: EscalationPriority = EscalationPriority.MEDIUM
    notes: Optional[str] = None


class EscalationUpdate(BaseModel):
    status: Optional[EscalationStatus] = None
    priority: Optional[EscalationPriority] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class EscalationRead(BaseModel):
    id: int
    sacco_id: str
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    conversation_key: str
    query: str
    category: EscalationCategory
    status: EscalationStatus
    priority: EscalationPriority
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


class KnowledgeDocumentCreate(BaseModel):
    title: str
    category: str = "general"
    content: str
    effective_date: Optional[date] = None


class KnowledgeDocumentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    effective_date: Optional[date] = None
    status: Optional[KnowledgeDocumentStatus] = None


class KnowledgeDocumentRead(BaseModel):
    id: str
    sacco_id: str
    title: str
    category: str
    content: str
    version: int
    status: KnowledgeDocumentStatus
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    effective_date: date
    qdrant_indexed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AdminOverviewMetrics(BaseModel):
    total_members: int
    active_conversations_7d: int
    total_questions_answered: int
    knowledge_gaps_count: int
    open_escalations_count: int
    satisfaction_rate_pct: float
    groundedness_score_pct: float
    total_approved_policies: int


class QuestionFrequencyItem(BaseModel):
    topic_or_query: str
    count: int
    category: str
    percentage: float


class GoalInsightItem(BaseModel):
    goal_type: str
    count: int
    percentage: float
    avg_target_amount: float
    total_target_amount: float


class LanguageDistribution(BaseModel):
    english_pct: float
    swahili_pct: float
    mixed_sheng_pct: float
    sample_size: int


class EvaluationHistoryPoint(BaseModel):
    run_id: str
    timestamp: str
    total_cases: int
    recall_1: float
    recall_3: float
    recall_5: float
    answerability_acc: float
    groundedness: float
    relevance: float
    hallucinations: int


class SystemHealthStatus(BaseModel):
    database: str
    qdrant: str
    groq_api: str
    overall: str
    uptime_seconds: float
