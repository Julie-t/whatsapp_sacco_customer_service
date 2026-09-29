"""Context-aware candidate filter for the BBVA-inspired routing architecture.

Narrows the set of possible operations down to 2–5 plausible candidates
based on current message cues, member profile, and conversation context.
"""

import re
from typing import Sequence

from app.ai.operation_registry import DEFAULT_OPERATIONS, OperationDefinition, OperationRegistry
from app.ai.routing_types import OperationType, WorkflowType
from app.services.conversations.conversation_context import ConversationContext


class CandidateFilter:
    """Filters available operations down to a plausible candidate subset."""

    def __init__(self, registry: OperationRegistry | None = None) -> None:
        self.registry = registry or OperationRegistry(DEFAULT_OPERATIONS)

    def select_candidates(
        self,
        context: ConversationContext,
    ) -> list[OperationDefinition]:
        """Select 2–5 plausible candidate operations for the given context.

        Uses conversational context (active goal, member profile) and
        linguistic cues from effective_query and raw_message.
        """
        selected_ids: set[str] = set()
        query = f"{context.effective_query} {context.raw_message}".lower()

        # 1. Member Data cues
        if any(w in query for w in ("balance", "salio", "owe", "loan balance", "next payment", "due", "instalment", "statement", "account")):
            selected_ids.add(OperationType.MEMBER_BALANCE.value)
            selected_ids.add(OperationType.MEMBER_LOAN_BALANCE.value)
            if "next" in query or "payment" in query or "due" in query or "malipo" in query or "tarehe" in query:
                selected_ids.add(OperationType.MEMBER_NEXT_PAYMENT.value)

        # 2. Goal cues
        has_goal_words = any(w in query for w in ("goal", "lengo", "save", "saving", "target", "scenario", "compare", "vs", "versus", "weka", "akiba"))
        if has_goal_words or context.has_active_goal:
            if context.has_active_goal:
                selected_ids.add(OperationType.GOAL_PROGRESS.value)
                selected_ids.add(OperationType.GOAL_SCENARIO.value)
                selected_ids.add(OperationType.GOAL_UPDATE.value)
            else:
                selected_ids.add(OperationType.GOAL_CREATE.value)
                selected_ids.add(OperationType.GOAL_SCENARIO.value)

        # 3. Education cues
        if any(w in query for w in ("compound", "budget", "rule", "explain", "what is", "learn", "how to save", "irregular", "advice", "strategy", "meaning")):
            selected_ids.add(OperationType.EDUCATION_CONCEPT.value)
            selected_ids.add(OperationType.EDUCATION_SAVING_STRATEGY.value)

        # 4. SACCO Info / Policy / Product cues
        if any(w in query for w in ("requirement", "qualify", "rate", "interest", "product", "dividend", "join", "eligibility", "terms", "rules", "sacco")):
            selected_ids.add(OperationType.SACCO_PRODUCT_INQUIRY.value)
            selected_ids.add(OperationType.SACCO_POLICY_INQUIRY.value)

        # 5. Escalation cues
        if any(w in query for w in ("speak", "agent", "human", "person", "staff", "rep", "complaint", "dispute", "stolen", "unauthorized")):
            selected_ids.add(OperationType.ESCALATION_SUPPORT.value)
            selected_ids.add(OperationType.ESCALATION_COMPLAINT.value)

        # 6. Always include Clarification candidate for ambiguous or underspecified queries
        selected_ids.add(OperationType.CLARIFY_DISAMBIGUATE.value)

        # If too few candidates matched (< 2 aside from clarification), provide broad default candidate set
        if len(selected_ids) <= 1:
            selected_ids.update([
                OperationType.SACCO_PRODUCT_INQUIRY.value,
                OperationType.EDUCATION_CONCEPT.value,
                OperationType.GOAL_CREATE.value,
                OperationType.MEMBER_BALANCE.value,
            ])

        # Retrieve matched OperationDefinitions
        candidates = [self.registry.get(op_id) for op_id in selected_ids if self.registry.get(op_id) is not None]

        # Prioritize candidates: ensure active goal requirements and auth requirements are respected
        filtered: list[OperationDefinition] = []
        for op in candidates:
            if op.requires_active_goal and not context.has_active_goal:
                continue
            filtered.append(op)

        # Keep candidate set bounded (between 3 and 6 candidates)
        return filtered[:6]
