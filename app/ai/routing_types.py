"""Routing types and operation definitions.

Defines the explicit workflow and operation taxonomy inspired by the
BBVA Routing Agent architecture.
"""

from enum import Enum


class WorkflowType(str, Enum):
    """High-level target workflow."""

    MEMBER_DATA = "member_data"
    GOAL = "goal"
    EDUCATION = "education"
    SACCO_INFORMATION = "sacco_information"
    HUMAN_ESCALATION = "human_escalation"
    CLARIFICATION = "clarification"


class OperationType(str, Enum):
    """Specific operation to execute within a workflow."""

    # Member data operations
    MEMBER_BALANCE = "member.balance"
    MEMBER_LOAN_BALANCE = "member.loan_balance"
    MEMBER_NEXT_PAYMENT = "member.next_payment"
    MEMBER_STATEMENT = "member.statement"

    # Goal operations
    GOAL_CREATE = "goal.create"
    GOAL_UPDATE = "goal.update"
    GOAL_PROGRESS = "goal.progress"
    GOAL_SCENARIO = "goal.scenario"

    # Education operations
    EDUCATION_CONCEPT = "education.concept"
    EDUCATION_CURRICULUM = "education.curriculum"
    EDUCATION_SAVING_STRATEGY = "education.saving_strategy"

    # SACCO information (RAG) operations
    SACCO_PRODUCT_INQUIRY = "sacco.product_inquiry"
    SACCO_POLICY_INQUIRY = "sacco.policy_inquiry"
    SACCO_FAQ = "sacco.faq"

    # Escalation operations
    ESCALATION_COMPLAINT = "escalation.complaint"
    ESCALATION_SUPPORT = "escalation.support"

    # Clarification operations
    CLARIFY_DISAMBIGUATE = "clarification.disambiguate"
