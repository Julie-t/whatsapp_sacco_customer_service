"""FastAPI routes for System 11 SACCO Admin Intelligence & Operations."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.models.admin import AdminUser, EscalationStatus, KnowledgeDocumentStatus
from app.schemas.admin import (
    AdminOverviewMetrics,
    AdminUserRead,
    EvaluationHistoryPoint,
    EscalationRead,
    EscalationUpdate,
    GoalInsightItem,
    KnowledgeDocumentCreate,
    KnowledgeDocumentRead,
    LanguageDistribution,
    LoginRequest,
    LoginResponse,
    QuestionFrequencyItem,
    SystemHealthStatus,
)
from app.services.admin.admin_analytics_service import AdminAnalyticsService
from app.services.admin.admin_auth_service import AdminAuthService, get_current_admin
from app.services.admin.admin_escalation_service import AdminEscalationService
from app.services.admin.admin_knowledge_service import AdminKnowledgeService

router = APIRouter(prefix="/api/admin", tags=["SACCO Admin Operations"])


def get_auth_service() -> AdminAuthService:
    return AdminAuthService()


def get_analytics_service() -> AdminAnalyticsService:
    return AdminAnalyticsService()


def get_escalation_service() -> AdminEscalationService:
    return AdminEscalationService()


def get_knowledge_service() -> AdminKnowledgeService:
    return AdminKnowledgeService()


# ---------------------------------------------------------------------------
# 11.1 Authentication Endpoints
# ---------------------------------------------------------------------------
@router.post("/auth/login", response_model=LoginResponse, summary="Staff administrator login")
def login(req: LoginRequest, auth_svc: AdminAuthService = Depends(get_auth_service)):
    auth_res = auth_svc.authenticate(req.username, req.password)
    if not auth_res:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return auth_res


@router.get("/auth/me", response_model=AdminUserRead, summary="Get current logged-in staff profile")
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    return current_admin


# ---------------------------------------------------------------------------
# 11.4 - 11.13 Analytics Endpoints
# ---------------------------------------------------------------------------
@router.get("/analytics/overview", response_model=AdminOverviewMetrics, summary="Overview dashboard KPIs")
def get_overview_kpis(
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    return analytics_svc.get_overview_metrics(sacco_id=current_admin.sacco_id)


@router.get("/analytics/questions", response_model=list[QuestionFrequencyItem], summary="Frequently asked question topics")
def get_top_questions(
    limit: int = Query(10, ge=1, le=50),
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    return analytics_svc.get_top_questions(sacco_id=current_admin.sacco_id, limit=limit)


@router.get("/analytics/goals", response_model=list[GoalInsightItem], summary="Aggregated financial goals macro-insights")
def get_goal_insights(
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    return analytics_svc.get_goal_insights(sacco_id=current_admin.sacco_id)


@router.get("/analytics/languages", response_model=LanguageDistribution, summary="Language distribution breakdown")
def get_language_breakdown(
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    return analytics_svc.get_language_distribution(sacco_id=current_admin.sacco_id)


@router.get("/analytics/evaluations", response_model=list[EvaluationHistoryPoint], summary="Historical RAG iteration metrics")
def get_evaluation_metrics(
    limit: int = Query(15, ge=1, le=50),
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    return analytics_svc.get_evaluation_history(limit=limit)


@router.get("/analytics/health", response_model=SystemHealthStatus, summary="System operational and cluster health")
async def get_system_health(
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    return await analytics_svc.get_system_health()


# ---------------------------------------------------------------------------
# 11.7 Escalations Management
# ---------------------------------------------------------------------------
@router.get("/escalations", response_model=list[EscalationRead], summary="List member escalation tickets")
def list_escalations(
    status: Optional[EscalationStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(get_current_admin),
    esc_svc: AdminEscalationService = Depends(get_escalation_service),
):
    return esc_svc.list_escalations(sacco_id=current_admin.sacco_id, status=status, limit=limit)


@router.patch("/escalations/{id}", response_model=EscalationRead, summary="Update escalation ticket status or assignment")
def update_escalation(
    id: int,
    esc_up: EscalationUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    esc_svc: AdminEscalationService = Depends(get_escalation_service),
):
    updated = esc_svc.update_escalation(
        escalation_id=id,
        esc_up=esc_up,
        admin_id=current_admin.id,
        sacco_id=current_admin.sacco_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Escalation ticket not found")
    return updated


# ---------------------------------------------------------------------------
# 11.14 - 11.16 Knowledge Base Workflow & Ingestion
# ---------------------------------------------------------------------------
@router.get("/knowledge", response_model=list[KnowledgeDocumentRead], summary="List SACCO policy documents")
def list_knowledge(
    status: Optional[KnowledgeDocumentStatus] = Query(None),
    current_admin: AdminUser = Depends(get_current_admin),
    kb_svc: AdminKnowledgeService = Depends(get_knowledge_service),
):
    return kb_svc.list_documents(sacco_id=current_admin.sacco_id, status=status)


@router.post("/knowledge", response_model=KnowledgeDocumentRead, status_code=status.HTTP_201_CREATED, summary="Create a draft policy document")
def create_knowledge_draft(
    doc_in: KnowledgeDocumentCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    kb_svc: AdminKnowledgeService = Depends(get_knowledge_service),
):
    return kb_svc.create_draft(doc_in=doc_in, created_by=current_admin.id, sacco_id=current_admin.sacco_id)


@router.patch("/knowledge/{id}/approve", response_model=KnowledgeDocumentRead, summary="Approve and ingest policy document into Qdrant")
def approve_and_ingest_knowledge(
    id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    kb_svc: AdminKnowledgeService = Depends(get_knowledge_service),
):
    approved = kb_svc.approve_and_ingest(doc_id=id, approved_by=current_admin.id, sacco_id=current_admin.sacco_id)
    if not approved:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    return approved


# ---------------------------------------------------------------------------
# 11.20 Export / Reporting
# ---------------------------------------------------------------------------
@router.get("/reports/export", summary="Export operational summary to CSV")
def export_report(
    current_admin: AdminUser = Depends(get_current_admin),
    analytics_svc: AdminAnalyticsService = Depends(get_analytics_service),
):
    kpis = analytics_svc.get_overview_metrics(sacco_id=current_admin.sacco_id)
    csv_rows = [
        "Metric,Value",
        f"Total Members,{kpis.total_members}",
        f"Active Conversations (7d),{kpis.active_conversations_7d}",
        f"Questions Answered,{kpis.total_questions_answered}",
        f"Knowledge Gaps Detected,{kpis.knowledge_gaps_count}",
        f"Open Escalations,{kpis.open_escalations_count}",
        f"Satisfaction Rate (%),{kpis.satisfaction_rate_pct}",
        f"Approved Policies,{kpis.total_approved_policies}",
    ]
    csv_content = "\n".join(csv_rows)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sacco_ai_report.csv"},
    )
