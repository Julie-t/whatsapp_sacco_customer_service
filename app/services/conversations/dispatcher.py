"""Route-to-handler dispatcher.

Maps a ``RequestTriageResult`` / ``RoutingDecision`` to the appropriate
workflow handler method.
The dispatch priority order is encoded here — the orchestrator just calls
``dispatcher.dispatch()`` and gets a response string back.

This is the **only place** that knows which service handles which route.
"""

import logging
import re

from app.ai.routing_types import WorkflowType
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_context import ConversationContext
from app.services.conversations.response import HUMAN_SUPPORT_PLACEHOLDER
from app.services.conversations.workflow_handlers import (
    WorkflowHandlers,
    _is_goal_eligible,
)

logger = logging.getLogger(__name__)


class Dispatcher:
    """Maps routing decisions to workflow handlers.

    Dispatch priority order (mirrors the BBVA decision center):
    0. Clarification (disambiguation question)
    1. Human escalation
    2. Member data (unless explicitly asking about goal progress/scenario)
    3. Goal operations (creation, update, scenario, progress)
    4. Education / SACCO information (RAG)
    """

    def __init__(self, handlers: WorkflowHandlers) -> None:
        self.handlers = handlers

    async def dispatch(
        self,
        triage: RequestTriageResult,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
    ) -> str:
        """Execute the appropriate workflow handler.

        Returns a response string ready for WhatsApp delivery.
        """
        workflow = getattr(triage, "workflow", None)
        operation = getattr(triage, "operation", None)

        # --- 0. Clarification / Disambiguation ---
        if workflow == WorkflowType.CLARIFICATION or getattr(triage, "clarification_prompt", None):
            return await self.handlers.handle_clarification(context, message, triage)

        # --- 1. Human escalation takes absolute precedence ---
        if triage.likely_needs_human or workflow == WorkflowType.HUMAN_ESCALATION:
            return await self.handlers.handle_escalation(context, message)

        # --- 2. Member data request (precedence over goals) ---
        if triage.needs_member_data or workflow == WorkflowType.MEMBER_DATA:
            # Only divert to goal flow if user explicitly asked about goal progress/scenario
            normalized = context.raw_message.lower()
            is_explicit_goal_progress_or_scenario = bool(
                re.search(
                    r"\b(goal\s+progress|my\s+goal|target\s+progress|what\s+if\s+i\s+save)\b",
                    normalized,
                    re.IGNORECASE,
                )
            )
            if not is_explicit_goal_progress_or_scenario:
                return await self.handlers.handle_member_data(
                    context, message, operation=operation
                )

        # --- 3. Goal operations ---
        if _is_goal_eligible(
            triage, context, context.raw_message, context.effective_query
        ) or workflow == WorkflowType.GOAL:
            response = await self.handlers.handle_goal(context, message, operation=operation)
            if response is not None:
                return response
            logger.info(
                "Goal handler yielded no goal response; continuing with general request triage."
            )

        # --- 4. Education / SACCO information (RAG fallthrough) ---
        return await self.handlers.handle_education(context, message, triage)
