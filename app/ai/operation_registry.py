"""Dynamic operation catalog for the BBVA-inspired routing architecture.

Stores metadata, descriptions, and context requirements for all operations.
Allows the Routing Agent to be dynamically prompted with ONLY plausible
candidate operations rather than a massive static prompt.
"""

from dataclasses import dataclass, field
from typing import Sequence

from app.ai.routing_types import OperationType, WorkflowType


@dataclass(frozen=True)
class OperationDefinition:
    """Metadata describing a discrete banking/SACCO operation."""

    id: str
    workflow: WorkflowType
    name: str
    description: str
    examples: tuple[str, ...] = field(default_factory=tuple)
    requires_auth: bool = False
    requires_active_goal: bool = False


# Default operations supported by the SACCO customer service assistant
DEFAULT_OPERATIONS: tuple[OperationDefinition, ...] = (
    # --- Member Data Operations ---
    OperationDefinition(
        id=OperationType.MEMBER_BALANCE.value,
        workflow=WorkflowType.MEMBER_DATA,
        name="Check Account Balance",
        description="Check authenticated member's personal savings, shares, and deposit account balances.",
        examples=("What is my balance?", "Salio yangu ni ngapi?", "How much do I have in savings?"),
        requires_auth=True,
    ),
    OperationDefinition(
        id=OperationType.MEMBER_LOAN_BALANCE.value,
        workflow=WorkflowType.MEMBER_DATA,
        name="Check Loan Balance",
        description="Check authenticated member's personal outstanding loan balances and loan terms.",
        examples=("What is my loan balance?", "How much do I still owe on my loan?", "Salio la mkopo wangu ni kiasi gani?"),
        requires_auth=True,
    ),
    OperationDefinition(
        id=OperationType.MEMBER_NEXT_PAYMENT.value,
        workflow=WorkflowType.MEMBER_DATA,
        name="Check Next Loan Payment",
        description="Retrieve due date and instalment amount for member's upcoming scheduled loan payment.",
        examples=("When is my next payment?", "Tarehe ya malipo ya mkopo ni lini?", "How much is my next monthly instalment?"),
        requires_auth=True,
    ),
    OperationDefinition(
        id=OperationType.MEMBER_STATEMENT.value,
        workflow=WorkflowType.MEMBER_DATA,
        name="Request Statement / Transactions",
        description="Lookup recent transactions or overall SACCO account financial summary for member.",
        examples=("Send my statement", "Recent transactions", "Summary ya akaunti yangu"),
        requires_auth=True,
    ),

    # --- Goal Operations ---
    OperationDefinition(
        id=OperationType.GOAL_CREATE.value,
        workflow=WorkflowType.GOAL,
        name="Create Savings Goal",
        description="Set up a new target savings goal with a specific amount, timeframe, or purpose.",
        examples=("I want to save 50k in 6 months for a plot", "Nataka kuanzisha lengo la kununua duka", "Help me plan to save 100,000 for university fees"),
    ),
    OperationDefinition(
        id=OperationType.GOAL_UPDATE.value,
        workflow=WorkflowType.GOAL,
        name="Update Existing Goal",
        description="Adjust target amount, deadline, or monthly contribution of an active savings goal.",
        examples=("Change my target to 80,000", "I want to extend my goal to 12 months", "Update my monthly contribution"),
        requires_active_goal=True,
    ),
    OperationDefinition(
        id=OperationType.GOAL_PROGRESS.value,
        workflow=WorkflowType.GOAL,
        name="Check Goal Progress",
        description="Review accumulated savings and progress towards active target goal.",
        examples=("How am I doing on my school fees goal?", "Goal progress", "Je nimebakiza kiasi gani kufikia lengo langu?"),
        requires_active_goal=True,
    ),
    OperationDefinition(
        id=OperationType.GOAL_SCENARIO.value,
        workflow=WorkflowType.GOAL,
        name="Simulate Savings Scenario",
        description="Compare or simulate what happens if saving a different monthly amount (e.g. 10k vs 15k) toward a goal.",
        examples=("Which is better, saving 10k or 15k a month?", "What if I put in 5,000 extra?", "Nikihifadhi 10,000 kila mwezi itachukua muda gani?"),
    ),

    # --- Education Operations ---
    OperationDefinition(
        id=OperationType.EDUCATION_CONCEPT.value,
        workflow=WorkflowType.EDUCATION,
        name="Financial Education Explanation",
        description="Explain financial principles, formulas, compound interest, emergency funds, debt management, or budgeting rules.",
        examples=("Explain compound interest", "What is the 50/30/20 budgeting rule?", "Good debt vs bad debt", "How do emergency funds work?"),
    ),
    OperationDefinition(
        id=OperationType.EDUCATION_CURRICULUM.value,
        workflow=WorkflowType.EDUCATION,
        name="Curriculum / Learning Recommendations",
        description="Recommend learning topics and educational guidance tailored to the member's financial stage.",
        examples=("What should I learn next?", "Financial education topics", "Give me advice on managing fluctuating income"),
    ),
    OperationDefinition(
        id=OperationType.EDUCATION_SAVING_STRATEGY.value,
        workflow=WorkflowType.EDUCATION,
        name="Personalized Saving Strategy Coaching",
        description="Provide advisory guidance on savings strategies, irregular income management, or fund allocation.",
        examples=("My income changes every month, how should I save?", "How to budget with irregular business income?", "Should I save or invest first?"),
    ),

    # --- SACCO Information (RAG) Operations ---
    OperationDefinition(
        id=OperationType.SACCO_PRODUCT_INQUIRY.value,
        workflow=WorkflowType.SACCO_INFORMATION,
        name="SACCO Product Information",
        description="Answer inquiries about SACCO loan products, savings accounts, requirements, dividends, and interest rates.",
        examples=("What are the requirements for a development loan?", "How much interest does the Super Savings account earn?", "Tell me about emergency loans"),
    ),
    OperationDefinition(
        id=OperationType.SACCO_POLICY_INQUIRY.value,
        workflow=WorkflowType.SACCO_INFORMATION,
        name="SACCO Bylaws & Policy Inquiry",
        description="Answer questions regarding SACCO membership eligibility, withdrawal policies, dividends payout, and guarantorship.",
        examples=("Who can join the SACCO?", "How do guarantors work for loans?", "When are dividends paid out?"),
    ),

    # --- Escalation Operations ---
    OperationDefinition(
        id=OperationType.ESCALATION_SUPPORT.value,
        workflow=WorkflowType.HUMAN_ESCALATION,
        name="Speak with Human Representative",
        description="Connect with a human customer support officer or request staff callback.",
        examples=("I want to speak to a person", "Connect me to customer service", "Nataka kuongea na mfanyakazi"),
    ),
    OperationDefinition(
        id=OperationType.ESCALATION_COMPLAINT.value,
        workflow=WorkflowType.HUMAN_ESCALATION,
        name="Lodge Formal Complaint or Dispute",
        description="Register a complaint, security dispute, or service issue for management review.",
        examples=("I want to report an issue", "I have a complaint about my account deduction", "Huduma zenu zina matatizo"),
    ),

    # --- Clarification Operations ---
    OperationDefinition(
        id=OperationType.CLARIFY_DISAMBIGUATE.value,
        workflow=WorkflowType.CLARIFICATION,
        name="Request Clarification",
        description="Ask the user a disambiguation question when query is vague or ambiguous (e.g. 'How much can I get?').",
        examples=("How much can I get?", "Contract", "How does it work?", "Nataka pesa"),
    ),
)


class OperationRegistry:
    """Registry managing available operations and formatting candidate sets."""

    def __init__(self, operations: Sequence[OperationDefinition] = DEFAULT_OPERATIONS) -> None:
        self._operations: dict[str, OperationDefinition] = {op.id: op for op in operations}

    def get(self, operation_id: str) -> OperationDefinition | None:
        return self._operations.get(operation_id)

    def all_operations(self) -> list[OperationDefinition]:
        return list(self._operations.values())

    def get_for_workflow(self, workflow: WorkflowType) -> list[OperationDefinition]:
        return [op for op in self._operations.values() if op.workflow == workflow]

    def format_candidates_for_prompt(self, candidate_operations: Sequence[OperationDefinition]) -> str:
        """Format candidate operations as concise bullet points for LLM prompt."""
        lines = []
        for op in candidate_operations:
            lines.append(f"- **{op.id}** ({op.workflow.value}): {op.description}")
        return "\n".join(lines)
