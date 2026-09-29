"""API routes for proactive member engagement, preferences, alerts, and feedback."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.database.engagement_repository import EngagementRepository
from app.models.engagement import (
    MemberEngagementPreferences,
    NotificationType,
    NotificationStatus,
    FeedbackRating,
)
from app.schemas.engagement import (
    EngagementPreferencesRead,
    EngagementPreferencesUpdate,
    MemberFeedbackRequest,
    MemberFeedbackResponse,
)
from app.services.proactive.goal_alert_service import GoalAlertService
from app.services.proactive.news_service import NewsService
from app.services.proactive.proactive_delivery_service import ProactiveDeliveryService
from app.services.proactive.proactive_education_planner import ProactiveEducationPlanner

router = APIRouter(tags=["Proactive Engagement"])


class DispatchRequest(BaseModel):
    notification_type: NotificationType
    content_id: Optional[str] = None
    message_body: str
    send_live: bool = False


# Repositories and Services
def get_engagement_repo() -> EngagementRepository:
    return EngagementRepository()


def get_delivery_service() -> ProactiveDeliveryService:
    return ProactiveDeliveryService(engagement_repo=get_engagement_repo())


def get_planner() -> ProactiveEducationPlanner:
    return ProactiveEducationPlanner(engagement_repo=get_engagement_repo())


def get_goal_alert_service() -> GoalAlertService:
    return GoalAlertService()


def get_news_service() -> NewsService:
    return NewsService(engagement_repo=get_engagement_repo())


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------
@router.get(
    "/members/{member_id}/preferences",
    response_model=EngagementPreferencesRead,
    summary="Get member engagement preferences",
)
def get_member_preferences(member_id: str):
    repo = get_engagement_repo()
    prefs = repo.get_preferences(member_id)
    if not prefs:
        # Default preferences
        prefs = repo.upsert_preferences(MemberEngagementPreferences(member_id=member_id))
    return prefs


@router.put(
    "/members/{member_id}/preferences",
    response_model=EngagementPreferencesRead,
    summary="Update member engagement preferences",
)
def update_member_preferences(member_id: str, update: EngagementPreferencesUpdate):
    repo = get_engagement_repo()
    current = repo.get_preferences(member_id)
    if not current:
        current = MemberEngagementPreferences(member_id=member_id)

    if update.education_frequency is not None:
        current.education_frequency = update.education_frequency
    if update.news_frequency is not None:
        current.news_frequency = update.news_frequency
    if update.goal_alerts_enabled is not None:
        current.goal_alerts_enabled = update.goal_alerts_enabled
    if update.allowed_topics is not None:
        current.allowed_topics = update.allowed_topics
    if update.quiet_hours_start is not None:
        current.quiet_hours_start = update.quiet_hours_start
    if update.quiet_hours_end is not None:
        current.quiet_hours_end = update.quiet_hours_end
    if update.preferred_language is not None:
        current.preferred_language = update.preferred_language

    saved = repo.upsert_preferences(current)
    return saved


# ---------------------------------------------------------------------------
# Proactive Planning & Alerts
# ---------------------------------------------------------------------------
@router.post(
    "/proactive/education/generate/{member_id}",
    summary="Generate next scheduled educational micro-lesson for a member",
)
def generate_proactive_education(member_id: str):
    planner = get_planner()
    plan = planner.plan_next_lesson(member_id)
    return {
        "member_id": plan.member_id,
        "topic": plan.topic,
        "message_body": plan.message_body,
        "goal_id": plan.goal_id,
        "goal_type": plan.goal_type,
        "knowledge_level": plan.knowledge_level.value if hasattr(plan.knowledge_level, "value") else plan.knowledge_level,
        "is_eligible": plan.is_eligible,
        "ineligibility_reason": plan.ineligibility_reason,
    }


@router.post(
    "/proactive/goals/check-alerts/{member_id}",
    summary="Check and generate goal milestone and risk trajectory alerts",
)
def check_goal_alerts(member_id: str):
    service = get_goal_alert_service()
    alerts = service.check_goal_alerts(member_id)
    return [
        {
            "member_id": a.member_id,
            "goal_id": a.goal_id,
            "goal_name": a.goal_name,
            "alert_type": a.alert_type.value,
            "notification_type": a.notification_type.value,
            "message_body": a.message_body,
            "progress_percentage": a.progress_percentage,
            "metadata": a.metadata,
        }
        for a in alerts
    ]


@router.post(
    "/proactive/news/recommend/{member_id}",
    summary="Recommend fresh, relevant financial news for a member",
)
def recommend_financial_news(member_id: str):
    service = get_news_service()
    rec = service.recommend_news_for_member(member_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No eligible or unexpired news recommendations available for this member.",
        )
    return {
        "member_id": rec.member_id,
        "article_id": rec.article.id if rec.article else None,
        "title": rec.article.title if rec.article else None,
        "source": rec.article.source if rec.article else None,
        "match_reason": rec.match_reason,
        "whatsapp_message": rec.whatsapp_message,
        "is_eligible": rec.is_eligible,
        "ineligibility_reason": rec.ineligibility_reason,
    }


# ---------------------------------------------------------------------------
# Dispatch & Policy Verification
# ---------------------------------------------------------------------------
@router.post(
    "/proactive/dispatch/{member_id}",
    summary="Run quiet hours and deduplication policy checks and dispatch notification",
)
def dispatch_proactive_notification(member_id: str, request: DispatchRequest):
    delivery_svc = get_delivery_service()
    decision = delivery_svc.evaluate_and_dispatch(
        member_id=member_id,
        notification_type=request.notification_type,
        content_id=request.content_id,
        message_body=request.message_body,
        send_live=request.send_live,
    )
    return {
        "is_allowed": decision.is_allowed,
        "status": decision.status.value,
        "reason": decision.reason,
        "notification_id": decision.notification.id if decision.notification else None,
    }


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
@router.post(
    "/proactive/feedback",
    response_model=MemberFeedbackResponse,
    summary="Record member feedback on a proactive notification",
)
def submit_member_feedback(feedback_req: MemberFeedbackRequest):
    repo = get_engagement_repo()
    target_id = feedback_req.notification_id
    if not target_id:
        latest = repo.get_latest_notification_for_member(feedback_req.member_id)
        if latest:
            target_id = latest.id

    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No notification found to associate feedback with.",
        )

    ok = repo.record_feedback(target_id, feedback_req.feedback)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {target_id} not found.",
        )

    return MemberFeedbackResponse(
        status="recorded",
        message="Feedback successfully recorded.",
        member_id=feedback_req.member_id,
        notification_id=target_id,
        feedback=feedback_req.feedback,
    )
