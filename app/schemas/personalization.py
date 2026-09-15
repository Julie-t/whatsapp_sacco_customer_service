"""Pydantic schemas for personalized financial education."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonalizedEducationRequest(BaseModel):
    """Request payload for generating personalized financial education."""
    member_id: str = Field(description="Unique member identifier")
    query: str = Field(min_length=1, description="Financial question or topic inquiry")
    language: Optional[str] = Field(default=None, description="Optional override language ('en', 'sw')")


class PersonalizedEducationResponse(BaseModel):
    """Response payload containing tailored education and metadata."""
    answer: str
    topic: Optional[str] = None
    knowledge_level_applied: str = "beginner"
    goal_context_applied: Optional[str] = None
    language_applied: str = "en"
    sources: list[str] = Field(default_factory=list)
    is_demo: bool = True


class EducationHistoryItem(BaseModel):
    """Record of an educational topic delivered to a member."""
    id: int
    member_id: str
    topic: str
    summary: Optional[str] = None
    goal_id: Optional[str] = None
    created_at: Optional[datetime] = None


class EducationPlanItem(BaseModel):
    """A single scheduled lesson in an educational roadmap."""
    week: int
    topic: str
    title: str
    description: str
    relevance_reason: str


class EducationPlanResponse(BaseModel):
    """Personalized educational curriculum roadmap for a member's goals."""
    member_id: str
    goal_type: Optional[str] = None
    plan: list[EducationPlanItem] = Field(default_factory=list)
