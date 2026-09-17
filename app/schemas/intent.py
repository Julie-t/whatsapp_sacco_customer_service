from typing import Literal, Optional
from pydantic import BaseModel, model_validator

from app.ai.routing_types import WorkflowType


class RequestTriageResult(BaseModel):
    language: Literal["en", "sw", "mixed"]
    needs_member_data: bool = False
    is_goal_related: bool = False
    is_education_related: bool = False
    likely_needs_human: bool = False
    reasoning: str

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RequestTriageResult):
            return (
                self.language == other.language
                and self.needs_member_data == other.needs_member_data
                and self.is_goal_related == other.is_goal_related
                and self.is_education_related == other.is_education_related
                and self.likely_needs_human == other.likely_needs_human
                and self.reasoning == other.reasoning
            )
        return False

    @classmethod
    def fallback(cls) -> "RequestTriageResult":
        return cls(
            language="mixed",
            needs_member_data=False,
            is_goal_related=False,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="The request could not be reliably classified by LLM; falling back safely.",
        )


class RoutingDecision(RequestTriageResult):
    """BBVA-inspired structured routing decision."""

    workflow: WorkflowType = WorkflowType.SACCO_INFORMATION
    operation: Optional[str] = None
    confidence: float = 1.0
    clarification_prompt: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_workflow_and_booleans(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values

        workflow = values.get("workflow")
        if workflow is not None:
            if isinstance(workflow, str):
                try:
                    workflow = WorkflowType(workflow)
                    values["workflow"] = workflow
                except ValueError:
                    pass

            if values.get("needs_member_data") is None:
                values["needs_member_data"] = workflow == WorkflowType.MEMBER_DATA
            if values.get("is_goal_related") is None:
                values["is_goal_related"] = workflow == WorkflowType.GOAL
            if values.get("is_education_related") is None:
                values["is_education_related"] = workflow == WorkflowType.EDUCATION
            if values.get("likely_needs_human") is None:
                values["likely_needs_human"] = workflow == WorkflowType.HUMAN_ESCALATION
        else:
            if values.get("likely_needs_human"):
                values["workflow"] = WorkflowType.HUMAN_ESCALATION
            elif values.get("needs_member_data"):
                values["workflow"] = WorkflowType.MEMBER_DATA
            elif values.get("is_goal_related"):
                values["workflow"] = WorkflowType.GOAL
            elif values.get("is_education_related"):
                values["workflow"] = WorkflowType.EDUCATION
            else:
                values["workflow"] = WorkflowType.SACCO_INFORMATION

        return values

    @classmethod
    def fallback(cls) -> "RoutingDecision":
        return cls(
            language="mixed",
            needs_member_data=False,
            is_goal_related=False,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="The request could not be reliably classified by LLM; falling back safely.",
            workflow=WorkflowType.SACCO_INFORMATION,
            confidence=0.0,
        )