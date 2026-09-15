"""REST API endpoints for personalized financial education and curriculum plans."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.database.personalization_repository import PersonalizationHistoryRepository
from app.models.goal import GoalStatus
from app.schemas.personalization import (
    EducationHistoryItem,
    EducationPlanItem,
    EducationPlanResponse,
    PersonalizedEducationRequest,
    PersonalizedEducationResponse,
)
from app.services.goals.goal_service import GoalService
from app.services.members.member_service import MemberDataService
from app.services.education.personalized_education_service import PersonalizedEducationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/education", tags=["Personalized Financial Education"])

_education_service: Optional[PersonalizedEducationService] = None
_history_repo: Optional[PersonalizationHistoryRepository] = None
_goal_service: Optional[GoalService] = None
_member_service: Optional[MemberDataService] = None


def get_education_service() -> PersonalizedEducationService:
    global _education_service
    if _education_service is None:
        _education_service = PersonalizedEducationService()
    return _education_service


def get_history_repo() -> PersonalizationHistoryRepository:
    global _history_repo
    if _history_repo is None:
        _history_repo = PersonalizationHistoryRepository()
    return _history_repo


def get_goal_service() -> GoalService:
    global _goal_service
    if _goal_service is None:
        _goal_service = GoalService()
    return _goal_service


def get_member_service() -> MemberDataService:
    global _member_service
    if _member_service is None:
        _member_service = MemberDataService()
    return _member_service


@router.post(
    "/explain",
    response_model=PersonalizedEducationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate personalized financial explanation",
)
async def explain_topic(
    request: PersonalizedEducationRequest,
) -> PersonalizedEducationResponse:
    """Generate financial coaching tailored to member knowledge level and active goals."""
    service = get_education_service()
    try:
        response = await service.explain(
            member_id_or_phone=request.member_id,
            query=request.query,
            override_language=request.language,
        )
        return response
    except Exception as exc:
        logger.exception("Error generating personalized education: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Education generation failed: {str(exc)}",
        ) from exc


@router.get(
    "/history/{member_id}",
    response_model=list[EducationHistoryItem],
    summary="Get delivered education topics history",
)
def get_member_history(
    member_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[EducationHistoryItem]:
    """Retrieve history of financial education lessons delivered to the member."""
    repo = get_history_repo()
    try:
        records = repo.get_history(member_id=member_id, limit=limit)
        return [
            EducationHistoryItem(
                id=r.id or 0,
                member_id=r.member_id,
                topic=r.topic,
                summary=r.summary,
                goal_id=r.goal_id,
                created_at=r.created_at,
            )
            for r in records
        ]
    except Exception as exc:
        logger.exception("Error fetching education history for %s: %s", member_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(exc)}",
        ) from exc


@router.get(
    "/plan/{member_id}",
    response_model=EducationPlanResponse,
    summary="Get proactive educational roadmap",
)
def get_education_plan(member_id: str) -> EducationPlanResponse:
    """Generate a 4-week educational curriculum roadmap based on member's active goals."""
    g_service = get_goal_service()
    m_service = get_member_service()

    member = m_service.get_member_profile(member_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member '{member_id}' not found",
        )

    active_goals = g_service.get_member_goals(member_id, status=GoalStatus.ACTIVE)
    goal = active_goals[0] if active_goals else None
    goal_type = goal.goal_type.value if goal else None

    if goal_type == "education":
        plan = [
            EducationPlanItem(
                week=1,
                topic="budgeting",
                title="Budgeting for School Fees & Tuition",
                description="How to categorize monthly expenses and allocate consistent savings toward education.",
                relevance_reason="Establishes regular cash flow discipline for school terms.",
            ),
            EducationPlanItem(
                week=2,
                topic="savings_discipline",
                title="Automating Monthly Goal Deposits",
                description="Setting standing orders or regular contributions to avoid last-minute fee shortfalls.",
                relevance_reason="Keeps you on track for your university enrollment date.",
            ),
            EducationPlanItem(
                week=3,
                topic="compound_interest",
                title="Growing Education Savings with Compound Interest",
                description="How SACCO savings accounts earn interest over long horizons.",
                relevance_reason="Maximizes total funds available by the target date.",
            ),
            EducationPlanItem(
                week=4,
                topic="emergency_fund",
                title="Protecting Your Goal with an Emergency Reserve",
                description="Separating unexpected emergencies from tuition funds so you never have to pause.",
                relevance_reason="Prevents raiding school savings when unexpected costs arise.",
            ),
        ]
    elif goal_type == "emergency_fund":
        plan = [
            EducationPlanItem(
                week=1,
                topic="emergency_fund",
                title="Why a 3 to 6 Month Reserve Matters",
                description="Understanding emergency liquidity and protecting your peace of mind.",
                relevance_reason="Directly supports your emergency buffer goal.",
            ),
            EducationPlanItem(
                week=2,
                topic="budgeting",
                title="Finding Hidden Savings in Daily Expenses",
                description="Using the 50/30/20 rule to redirect unneeded spending toward your buffer.",
                relevance_reason="Speeds up reaching your emergency target.",
            ),
            EducationPlanItem(
                week=3,
                topic="savings_discipline",
                title="High-Yield Liquid Savings vs Fixed Deposits",
                description="Choosing account types that give easy access without forfeiting interest.",
                relevance_reason="Ensures emergency funds can be withdrawn immediately when needed.",
            ),
            EducationPlanItem(
                week=4,
                topic="debt_management",
                title="Avoiding Expensive Emergency Debt",
                description="How having your own savings buffer saves you from high-interest mobile loans.",
                relevance_reason="Demonstrates the true long-term value of your emergency fund.",
            ),
        ]
    else:
        plan = [
            EducationPlanItem(
                week=1,
                topic="budgeting",
                title="Foundational Budgeting",
                description="Tracking income, expenses, and savings potential.",
                relevance_reason="The baseline for all financial security.",
            ),
            EducationPlanItem(
                week=2,
                topic="savings_discipline",
                title="Consistent Habit Building",
                description="The psychology of paying yourself first each month.",
                relevance_reason="Helps build sustainable cooperative savings habits.",
            ),
            EducationPlanItem(
                week=3,
                topic="compound_interest",
                title="Compound Growth Mechanics",
                description="Understanding how dividends and interest compound over time.",
                relevance_reason="Shows how early savings multiply through SACCO dividends.",
            ),
            EducationPlanItem(
                week=4,
                topic="debt_management",
                title="Good Debt vs Bad Debt",
                description="Using development loans for assets while minimizing consumer debt.",
                relevance_reason="Ensures healthy leverage and borrowing capacity.",
            ),
        ]

    return EducationPlanResponse(
        member_id=member_id,
        goal_type=goal_type,
        plan=plan,
    )
