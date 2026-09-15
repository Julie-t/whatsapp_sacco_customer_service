"""Pydantic schemas for financial goals API and calculations."""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from app.models.goal import GoalStatus, GoalType, ContributionFrequency


class GoalCreate(BaseModel):
    member_id: str
    goal_type: GoalType = GoalType.GENERAL_SAVINGS
    name: str = Field(..., min_length=1, max_length=100)
    target_amount: float = Field(..., gt=0, description="Target savings amount in KES")
    target_date: date
    current_amount: float = Field(default=0.0, ge=0)
    contribution_amount: Optional[float] = Field(default=None, ge=0)
    contribution_frequency: ContributionFrequency = ContributionFrequency.MONTHLY
    notification_frequency: str = "monthly"
    notes: Optional[str] = None

    @field_validator("target_date")
    @classmethod
    def validate_future_date(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("Target date must be in the future")
        return v


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    target_amount: Optional[float] = Field(default=None, gt=0)
    current_amount: Optional[float] = Field(default=None, ge=0)
    target_date: Optional[date] = None
    contribution_amount: Optional[float] = Field(default=None, ge=0)
    contribution_frequency: Optional[ContributionFrequency] = None
    status: Optional[GoalStatus] = None
    notification_frequency: Optional[str] = None
    notes: Optional[str] = None


class GoalCalculationResult(BaseModel):
    """Deterministic calculation output for a goal."""
    target_amount: float
    current_amount: float
    amount_remaining: float
    progress_percentage: float
    months_remaining: int
    required_monthly_contribution: float
    projected_completion_date: Optional[date] = None
    is_on_track: bool = True
    pace_assessment: str = ""


class ScenarioAnalysisRequest(BaseModel):
    """What-if question with alternate contribution amount."""
    proposed_monthly_contribution: float = Field(..., gt=0)


class ScenarioAnalysisResult(BaseModel):
    """Comparison between baseline and what-if scenario."""
    current_monthly_contribution: Optional[float]
    proposed_monthly_contribution: float
    amount_remaining: float
    current_projected_months: Optional[int]
    proposed_projected_months: int
    current_projected_date: Optional[date]
    proposed_projected_date: date
    months_difference: int  # positive means faster completion
    narrative_summary: str


class GoalResponse(BaseModel):
    id: str
    member_id: str
    goal_type: GoalType
    name: str
    target_amount: float
    current_amount: float
    target_date: date
    contribution_amount: Optional[float]
    contribution_frequency: ContributionFrequency
    status: GoalStatus
    notification_frequency: str
    notes: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    calculation: Optional[GoalCalculationResult] = None


class GoalExtractionResult(BaseModel):
    """Structured extraction of goal parameters from free-form text."""
    goal_type: Optional[GoalType] = None
    name: Optional[str] = None
    target_amount: Optional[float] = None
    timeline_months: Optional[int] = None
    target_date: Optional[date] = None
    current_amount: Optional[float] = None
    monthly_contribution: Optional[float] = None
    is_scenario_query: bool = False
    proposed_scenario_amount: Optional[float] = None
    is_progress_inquiry: bool = False
    is_balance_update: bool = False
    needs_clarification: bool = False
    missing_fields: list[str] = Field(default_factory=list)
