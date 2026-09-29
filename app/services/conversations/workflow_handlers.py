"""Workflow handler implementations.

Each handler method delegates to the appropriate domain service and returns a
formatted response string.  These were extracted from the inline logic in
``conversation_service.handle_message_async()`` and from the private
functions ``_handle_member_query()`` and ``_handle_goal_query()``.
"""

import logging
import re
from typing import Any

from app.config.settings import settings
from app.schemas.intent import RequestTriageResult
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_context import ConversationContext
from app.services.conversations.response import (
    GENERAL_ASSISTANCE_PLACEHOLDER,
    HUMAN_SUPPORT_PLACEHOLDER,
    MEMBER_NO_ACCOUNTS,
    MEMBER_NOT_RECOGNIZED,
    clean_ai_artifacts,
    format_rag_response,
)
from app.services.conversations.service_container import ServiceContainer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Goal-eligibility helpers (moved from conversation_service.py)
# ---------------------------------------------------------------------------


def _is_goal_advisory_or_educational_query(text: str) -> bool:
    """Detect if a query referencing a goal is actually an advisory, educational, or product inquiry."""
    lower = text.lower()
    advisory_patterns = (
        r"\b(?:which|what|best|recommend|available|list|show)\b.*\b(?:accounts?|products?|options?|plans?|services?)\b",
        r"\b(?:stocks?|shares?|bonds?|dividends?|fixed\s+deposit|interest|rates?|yield|returns?)\b",
        r"\b(?:how\s+(?:can|does|do)\s+.*\s+(?:help|supplement|boost|reach|grow))\b",
        r"\b(?:can\s+i\s+(?:buy|get|use|take|invest|supplement|join))\b",
        r"\b(?:is\s+it\s+(?:better|good|advisable)\s+to)\b",
        r"\b(?:explain|tell\s+me\s+about|guide\s+me|learn|understand|information|topics?)\b",
        r"\b(?:how\s+(?:should|can|do)\s+i\s+(?:think\s+about\s+|approach\s+)?sav(?:e|ing))\b",
        r"\b(?:income\s+changes|irregular\s+income|variable\s+income|fluctuat\w*)\b",
        r"\b(?:how\s+(?:should|can|do)\s+i\s+budget|budgeting\s+tips|50/30/20)\b",
    )
    return any(re.search(pat, lower) for pat in advisory_patterns)


def _is_goal_eligible(
    triage: RequestTriageResult,
    context: ConversationContext,
    body: str,
    effective_query: str,
) -> bool:
    """Determine whether a message should be dispatched to the goal handler.

    Extracted from conversation_service.py lines 733-772.
    """
    normalized = body.lower()

    has_goal_context = bool(
        context.context_summary
        and any(
            k in context.context_summary.lower()
            for k in ("goal", "target", "save", "saving", "contribution")
        )
    )

    goal_explicit_pattern = r"\b(save|saved|saving|savings|goal|goals|target|targets|changa|progress)\b"
    has_explicit_goal_terms = bool(
        re.search(goal_explicit_pattern, normalized, re.IGNORECASE)
    ) or bool(re.search(goal_explicit_pattern, effective_query, re.IGNORECASE))

    goal_followup_pattern = r"\b(afford|manage|enough|update|deposit|contribute|month|months|year|years|ksh|kes|thousand|better|compare|versus|option|options|instead)\b"
    has_goal_followup_terms = bool(
        re.search(goal_followup_pattern, normalized, re.IGNORECASE)
    ) or bool(re.search(goal_followup_pattern, effective_query, re.IGNORECASE))

    from app.services.goals.goal_extractor import _parse_amount

    has_numeric_target = bool(_parse_amount(body) or _parse_amount(effective_query))

    is_scenario_comparison = bool(
        re.search(
            r"\b(which\s+one\s+is\s+better|which\s+is\s+better|better\s+for\s+me|should\s+i\s+save|"
            r"compare|versus|\bvs\b|between\s+\d+.*and\s+\d+)\b",
            normalized,
            re.IGNORECASE,
        )
    ) or bool(
        re.search(
            r"\b(which\s+one\s+is\s+better|which\s+is\s+better|better\s+for\s+me|should\s+i\s+save|"
            r"compare|versus|\bvs\b|between\s+\d+.*and\s+\d+)\b",
            effective_query,
            re.IGNORECASE,
        )
    )

    return (
        not triage.is_education_related
        and (
            triage.is_goal_related
            or (
                has_goal_context
                and (
                    has_explicit_goal_terms
                    or has_goal_followup_terms
                    or has_numeric_target
                    or is_scenario_comparison
                )
            )
            or (context.has_active_goal and (has_explicit_goal_terms or is_scenario_comparison))
        )
    ) and not (
        _is_goal_advisory_or_educational_query(effective_query)
        or _is_goal_advisory_or_educational_query(body)
    )


# ---------------------------------------------------------------------------
# Member query helper (standalone for test compatibility and reuse)
# ---------------------------------------------------------------------------


def _handle_member_query(
    phone_number: str,
    query: str,
    member_service: Any | None = None,
    auth_service: Any | None = None,
    audit_service: Any | None = None,
    require_auth: bool | None = None,
) -> str:
    """Resolve member identity and return a formatted response from structured data.

    This is the 'fast-path' — no LLM is invoked.  Deterministic template
    responses guarantee 0% hallucination risk on personal data.
    """
    enforce_auth = require_auth if require_auth is not None else settings.REQUIRE_MEMBER_AUTH
    if enforce_auth:
        from app.services.members.member_auth_service import MemberAuthService

        a_svc = auth_service or MemberAuthService()
        if not a_svc.is_session_active(phone_number, sacco_id=settings.DEFAULT_SACCO_ID):
            ok, prompt_msg, _ = a_svc.request_otp(
                phone_number, sacco_id=settings.DEFAULT_SACCO_ID
            )
            return prompt_msg

    if member_service is None:
        from app.services.members.member_service import MemberDataService

        service = MemberDataService()
    else:
        service = member_service

    snapshot = service.get_member_snapshot(phone_number)

    if snapshot is None:
        return MEMBER_NOT_RECOGNIZED

    if not snapshot.accounts and not snapshot.loans:
        return MEMBER_NO_ACCOUNTS

    from app.services.members.member_audit_service import MemberAuditService

    auditor = audit_service or MemberAuditService()
    try:
        auditor.log_access(
            sacco_id=settings.DEFAULT_SACCO_ID,
            action="MEMBER_FINANCIAL_LOOKUP",
            member_id=snapshot.profile.id if snapshot and snapshot.profile else None,
            phone_number=phone_number,
            accessed_fields=["accounts", "loans"] if snapshot else [],
            details={"query": query},
        )
    except Exception as aud_err:
        logger.warning("Failed to log audit event: %s", aud_err)

    from app.services.members.member_response_formatter import format_member_response

    return format_member_response(
        snapshot,
        query,
        demo_label=settings.MEMBER_DATA_DEMO_MODE,
    )


# ---------------------------------------------------------------------------
# WorkflowHandlers
# ---------------------------------------------------------------------------


class WorkflowHandlers:
    """Implementations for each workflow target.

    Each method delegates to the appropriate domain service and returns a
    formatted response string ready for WhatsApp delivery.
    """

    def __init__(self, services: ServiceContainer) -> None:
        self.services = services

    # --- 0. Clarification (BBVA first-class outcome) ------------------------

    async def handle_clarification(
        self,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
        triage: RequestTriageResult,
    ) -> str:
        """Return a clarification / disambiguation question."""
        prompt = getattr(triage, "clarification_prompt", None)
        if prompt:
            return prompt
        return (
            "Would you like to check your personal account balance, "
            "calculate savings towards a goal, or ask about SACCO loan options?"
        )

    # --- 1. Human Escalation ------------------------------------------------

    async def handle_escalation(
        self,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
    ) -> str:
        """Create an escalation ticket and return the acknowledgment message."""
        try:
            from app.services.admin.admin_escalation_service import AdminEscalationService

            AdminEscalationService().record_from_conversation(
                conversation_key=message.from_number,
                query=context.effective_query,
                member_id=(
                    context.member_profile.id if context.member_profile else None
                ),
                sacco_id=settings.DEFAULT_SACCO_ID,
            )
        except Exception as esc_err:
            logger.warning("Failed to auto-record escalation ticket: %s", esc_err)
        return HUMAN_SUPPORT_PLACEHOLDER

    # --- 2. Member Data -----------------------------------------------------

    async def handle_member_data(
        self,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
        auth_service: Any | None = None,
        operation: str | None = None,
    ) -> str:
        """Auth-check → member lookup → audit → format.

        Deterministic template responses guarantee 0% hallucination risk
        on personal data.  Delegates to ``_handle_member_query()``.
        """
        return _handle_member_query(
            phone_number=message.from_number,
            query=context.effective_query,
            member_service=self.services.member_service,
            auth_service=auth_service or self.services.auth_service,
        )

    # --- 3. Goal Operations -------------------------------------------------

    async def handle_goal(
        self,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
        operation: str | None = None,
    ) -> str | None:
        """Goal creation, update, scenario, progress.

        Returns ``None`` if the goal handler cannot produce a response
        (in which case the dispatcher falls through to RAG/Education).

        Extracted from ``_handle_goal_query()`` (lines 323-503).
        """
        from app.models.goal import GoalStatus, GoalType
        from app.schemas.goal import GoalCreate, GoalUpdate
        from app.services.goals.goal_extractor import (
            _detect_goal_type,
            _parse_all_amounts,
            _parse_amount,
            _parse_months,
        )
        from app.services.goals.goal_response_formatter import (
            format_clarification_prompt,
            format_goal_created,
            format_goal_progress,
            format_goal_scenario,
            format_goal_updated,
            format_no_goals_message,
            format_scenario_comparison,
        )

        phone_number = message.from_number
        query = context.raw_message
        context_str = context.context_summary

        m_service = self.services.member_service
        profile = m_service.resolve_member(phone_number)
        if profile is None:
            if settings.MEMBER_DATA_DEMO_MODE:
                if hasattr(m_service, "get_or_create_demo_member"):
                    profile = m_service.get_or_create_demo_member(phone_number)
                else:
                    from app.database.member_repository import _hash_phone
                    from app.schemas.member import MemberProfile

                    profile = MemberProfile(
                        id=f"demo_{_hash_phone(phone_number)[:8]}",
                        display_name="Member",
                        preferred_language="en",
                        knowledge_level="beginner",
                        sacco_id=settings.DEFAULT_SACCO_ID,
                    )
            else:
                return MEMBER_NOT_RECOGNIZED

        g_service = self.services.goal_service
        extractor = self.services.goal_extractor
        extracted = await extractor.extract_async(query, context=context_str)

        active_goal = None
        state = self.services.state_store.get(phone_number)
        if state and state.active_goal_id:
            active_goal = g_service.get_goal(state.active_goal_id)
            if active_goal and getattr(active_goal, "status", None) not in (GoalStatus.ACTIVE, "active"):
                active_goal = None

        # If user explicitly references an existing goal by name, switch to it
        if hasattr(g_service, "get_member_goals"):
            try:
                member_goals = g_service.get_member_goals(profile.id, status=GoalStatus.ACTIVE)
                for g in member_goals:
                    if g.name and len(g.name) > 3 and g.name.lower() in query.lower():
                        active_goal = g
                        self.services.state_store.update(phone_number, active_goal_id=g.id)
                        break
            except Exception:
                pass

        if not active_goal:
            active_goal = g_service.get_active_goal(profile.id)
            if active_goal:
                self.services.state_store.update(phone_number, active_goal_id=active_goal.id)


        # 1. Scenario analysis
        is_scenario_or_comparison = extracted.is_scenario_query or bool(
            re.search(
                r"\b(what\s+if|suppose|how\s+fast|how\s+soon|how\s+many\s+months\s+if|instead\s+of|"
                r"which\s+one\s+is\s+better|which\s+is\s+better|better\s+for\s+me|should\s+i\s+save|"
                r"compare|versus|\bvs\b|between\s+\d+.*and\s+\d+)\b",
                query,
                re.IGNORECASE,
            )
        )
        if is_scenario_or_comparison:
            if not active_goal:
                return format_no_goals_message(
                    profile.display_name, demo_label=settings.MEMBER_DATA_DEMO_MODE
                )

            opt_a = extracted.proposed_scenario_amount
            opt_b = extracted.secondary_scenario_amount
            if not opt_a or not opt_b:
                found_amts = _parse_all_amounts(query)
                if len(found_amts) >= 2:
                    opt_a = found_amts[0]
                    opt_b = found_amts[1]
                elif len(found_amts) == 1 and not opt_a:
                    opt_a = found_amts[0]

            if opt_a is not None and opt_b is not None and opt_a != opt_b:
                comparison = g_service.calculate_comparison(active_goal.id, opt_a, opt_b)
                if comparison:
                    return format_scenario_comparison(
                        active_goal.name,
                        comparison,
                        demo_label=settings.MEMBER_DATA_DEMO_MODE,
                    )

            scenario_amt = opt_a or 15000.0
            scenario = g_service.calculate_scenario(active_goal.id, scenario_amt)
            if scenario:
                return format_goal_scenario(
                    scenario, demo_label=settings.MEMBER_DATA_DEMO_MODE
                )

        # 2. Progress inquiry
        if extracted.is_progress_inquiry:
            if not active_goal:
                return format_no_goals_message(
                    profile.display_name, demo_label=settings.MEMBER_DATA_DEMO_MODE
                )
            return format_goal_progress(
                active_goal, demo_label=settings.MEMBER_DATA_DEMO_MODE
            )

        # Detect goal categories and canonical names
        heuristic_type, heuristic_name = _detect_goal_type(
            query + (" " + context_str if context_str else "")
        )
        final_type = extracted.goal_type or heuristic_type or GoalType.GENERAL_SAVINGS
        final_name = (
            heuristic_name
            if (
                not extracted.name
                or extracted.name == "Savings Goal"
                or "loan" in extracted.name.lower()
                or final_type == GoalType.BUSINESS
            )
            else extracted.name
        )

        # 3. Existing active goal updates
        is_explicit_new_goal = bool(
            re.search(
                r"\b(another\s+goal|different\s+goal|new\s+goal|second\s+goal|also\s+want\s+to\s+save\s+for|save\s+for\s+a\s+different)\b",
                query,
                re.IGNORECASE,
            )
        )

        variability_patterns = r"\b(sometimes\s+business\s+is\s+slow|business\s+is\s+slow|income\s+(?:changes|varies|fluctuates)|irregular|some\s+months)\b"
        has_variability = bool(re.search(variability_patterns, query, re.IGNORECASE))

        cand_contrib = extracted.monthly_contribution
        if cand_contrib is None and any(
            m in query.lower()
            for m in ("month", "monthly", "mo", "mwezi", "put aside", "aside", "some months")
        ):
            cand_contrib = _parse_amount(query)

        has_balance_update = (
            extracted.is_balance_update
            or extracted.current_amount is not None
            or any(k in query.lower() for k in ("already", "saved", "have", "starting"))
        )

        has_explicit_target_change = _parse_amount(query) is not None and any(
            k in query.lower()
            for k in (
                "increase target",
                "change target",
                "new target",
                "update target",
                "target to",
                "target of",
            )
        )

        is_updating_existing_goal = bool(
            active_goal
            and not is_explicit_new_goal
            and (
                cand_contrib is not None
                or has_balance_update
                or has_variability
                or has_explicit_target_change
            )
        )

        if is_updating_existing_goal:
            update_fields: dict = {}
            if cand_contrib is not None:
                update_fields["contribution_amount"] = cand_contrib

            if extracted.current_amount is not None:
                update_fields["current_amount"] = extracted.current_amount
            elif any(k in query.lower() for k in ("already", "saved", "have", "starting")):
                parsed_amt = _parse_amount(query)
                if parsed_amt is not None:
                    update_fields["current_amount"] = parsed_amt

            if has_variability:
                update_fields["notes"] = "variable income"

            if _parse_months(query) is not None:
                from datetime import date

                from app.services.goals.goal_calculator import add_months

                months = _parse_months(query)
                if months:
                    update_fields["target_date"] = add_months(date.today(), months)

            if has_explicit_target_change:
                update_fields["target_amount"] = _parse_amount(query)

            if update_fields:
                updated = g_service.update_goal(
                    active_goal.id, GoalUpdate(**update_fields)
                )
                if updated:
                    self.services.state_store.update(phone_number, active_goal_id=updated.id)
                    return format_goal_updated(
                        updated, demo_label=settings.MEMBER_DATA_DEMO_MODE
                    )

            return format_goal_progress(
                active_goal, demo_label=settings.MEMBER_DATA_DEMO_MODE
            )

        # 4. Missing info clarification for new goals
        if extracted.needs_clarification:
            return format_clarification_prompt(extracted.missing_fields)

        # 5. Create new goal
        has_current_amount = _parse_amount(query) is not None
        has_current_timeline = _parse_months(query) is not None
        has_current_goal_terms = any(
            w in query.lower()
            for w in ("goal", "save", "saving", "raise", "target", "create", "set", "changa")
        )

        if extracted.target_amount and extracted.target_date:
            if (
                not has_current_amount
                and not has_current_timeline
                and not has_current_goal_terms
            ):
                if active_goal:
                    return format_goal_progress(
                        active_goal, demo_label=settings.MEMBER_DATA_DEMO_MODE
                    )
                return format_clarification_prompt(["target_amount", "target_date"])

            goal_create = GoalCreate(
                member_id=profile.id,
                goal_type=final_type,
                name=final_name,
                target_amount=extracted.target_amount,
                target_date=extracted.target_date,
                current_amount=extracted.current_amount or 0.0,
                contribution_amount=extracted.monthly_contribution,
            )
            created = g_service.create_goal(goal_create)
            if created:
                self.services.state_store.update(phone_number, active_goal_id=created.id)
            return format_goal_created(
                created, demo_label=settings.MEMBER_DATA_DEMO_MODE
            )

        if has_current_goal_terms or (extracted.target_amount or extracted.target_date):
            return format_clarification_prompt(["target_amount", "target_date"])

        return None

    # --- 4. Education -------------------------------------------------------

    async def handle_education(
        self,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
        triage: RequestTriageResult,
    ) -> str:
        """Personalized financial education.

        Extracted from handle_message_async lines 797-833.
        """
        from app.services.education.personalized_education_service import (
            PersonalizedEducationService,
        )

        body = context.raw_message
        effective_query = context.effective_query

        # Determine whether to use the injected or default education service
        if self.services._education_service is not None:
            edu_svc = self.services.education_service
            edu_query = (
                body
                if PersonalizedEducationService.is_curriculum_recommendation_query(body)
                else effective_query
            )
            edu_res = await edu_svc.explain(
                member_id_or_phone=message.from_number,
                query=edu_query,
                override_language=(
                    triage.language if triage.language in ("en", "sw") else None
                ),
            )
            return clean_ai_artifacts(edu_res.answer)

        if self.services._rag_answer_service is not None:
            return await self.handle_sacco_information(context, message, triage)

        use_education = (
            PersonalizedEducationService.is_curriculum_recommendation_query(body)
            or PersonalizedEducationService.is_curriculum_recommendation_query(effective_query)
            or PersonalizedEducationService.is_directive_investment_query(body)
            or PersonalizedEducationService.is_directive_investment_query(effective_query)
            or (
                context.member_profile
                and context.has_active_goal
                and (
                    triage.is_education_related
                    or PersonalizedEducationService.detect_topic(effective_query)
                    != "general_education"
                )
            )
        )

        if use_education or triage.is_education_related:
            edu_svc = self.services.education_service
            edu_query = (
                body
                if PersonalizedEducationService.is_curriculum_recommendation_query(body)
                else effective_query
            )
            edu_res = await edu_svc.explain(
                member_id_or_phone=message.from_number,
                query=edu_query,
                override_language=(
                    triage.language if triage.language in ("en", "sw") else None
                ),
            )
            return clean_ai_artifacts(edu_res.answer)

        # Fall through to RAG
        return await self.handle_sacco_information(context, message, triage)

    # --- 5. SACCO Information (RAG) -----------------------------------------

    async def handle_sacco_information(
        self,
        context: ConversationContext,
        message: IncomingWhatsAppMessage,
        triage: RequestTriageResult,
    ) -> str:
        """RAG-grounded SACCO knowledge answers.

        Extracted from handle_message_async lines 834-852.
        """
        try:
            rag_svc = self.services.rag_answer_service
            history_list = [
                turn.model_dump() if hasattr(turn, "model_dump") else dict(turn)
                for turn in (context.previous_turns or [])
            ]
            answer = await rag_svc.answer(
                query=context.effective_query,
                sacco_id=settings.DEFAULT_SACCO_ID,
                language=triage.language,
                conversation_history=history_list,
            )
            return format_rag_response(answer)
        except Exception as exc:
            logger.exception("Grounded WhatsApp answer unavailable: %s", exc)
            return GENERAL_ASSISTANCE_PLACEHOLDER
