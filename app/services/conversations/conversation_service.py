import logging
import re
from time import perf_counter
from typing import Any, Optional

from app.ai.intent_router import IntentRouter
from app.ai.llm import LLM
from app.ai.rag.pipeline import RAGPipeline
from app.schemas.message import IncomingWhatsAppMessage
from app.services.rag.rag_answer_service import NO_CONTEXT_ANSWER, RAGAnswerService
from app.services.conversations.conversation_history import InMemoryConversationHistory
from app.services.conversations.postgres_conversation_history import get_runtime_conversation_history
from app.services.members.member_service import MemberDataService
from app.services.members.member_response_formatter import format_member_response
from app.services.goals.goal_service import GoalService
from app.services.goals.goal_extractor import (
    GoalExtractor,
    _detect_goal_type,
    _parse_amount,
    _parse_months,
)
from app.models.goal import GoalType
from app.schemas.goal import GoalCreate
from app.services.goals.goal_response_formatter import (
    format_clarification_prompt,
    format_goal_created,
    format_goal_progress,
    format_goal_scenario,
    format_goal_updated,
    format_no_goals_message,
)
from app.services.education.personalized_education_service import PersonalizedEducationService
from app.services.proactive.member_feedback_service import MemberFeedbackService
from app.config.settings import settings

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "👋🏾 Karibu! I'm your SACCO financial companion.\n\n"
    "I can help you with:\n\n"
    "1️⃣ Financial education\n"
    "2️⃣ SACCO information\n"
    "3️⃣ My financial goals\n"
    "4️⃣ Talk to a SACCO representative\n\n"
    "For now, this is an early MVP. You can type HELP at any time."
)

FALLBACK_MESSAGE = (
    "Thank you for your message. My AI assistant capabilities are being introduced soon. "
    "For now, you can type HELP to see what I can do."
)

MEDIA_NOT_SUPPORTED = (
    "I can't process media messages yet. Please type HELP to see how I can assist you."
)

HUMAN_SUPPORT_PLACEHOLDER = (
    "Your request may need staff assistance. Human support connection is coming later. "
    "Please type HELP to see what is available now."
)
MEMBER_DATA_PLACEHOLDER = (
    "This question requires your personal SACCO information, which I don't have access "
    "to yet. A future version will connect this assistant to authorized member data."
)
MEMBER_NOT_RECOGNIZED = (
    "I couldn't verify your member information. "
    "Please contact a SACCO representative for help with personal account queries."
)
MEMBER_NO_ACCOUNTS = (
    "Your member profile is on file but I don't have account information available "
    "right now. Please contact a SACCO representative."
)
GENERAL_ASSISTANCE_PLACEHOLDER = (
    "General assistance is temporarily unavailable. Please contact a SACCO representative."
)

GREETINGS = {"hello", "hi", "hey", "habari", "jambo", "sasa"}
MENU_TRIGGERS = {"menu", "help"}

MENU_RESPONSES: dict[str, str] = {
    "1": (
        "📚 *Financial Education*\n\n"
        "I can explain topics like:\n"
        "• Budgeting and the 50/30/20 rule\n"
        "• Compound interest\n"
        "• Good debt vs bad debt\n"
        "• Emergency funds\n"
        "• Saving and investing basics\n\n"
        "Just ask me a question! For example:\n"
        "_\"How can I create a budget?\"_"
    ),
    "2": (
        "🏦 *SACCO Information*\n\n"
        "I can help with:\n"
        "• Membership requirements\n"
        "• Loan types and eligibility\n"
        "• Savings accounts and interest rates\n"
        "• Deposits and withdrawals\n"
        "• Dividends and shares\n\n"
        "Just ask me a question! For example:\n"
        "_\"What are the requirements to become a member?\"_"
    ),
    "3": (
        "🎯 *My Financial Goals*\n\n"
        "I can help you think through your savings goals and what "
        "it would take to reach them.\n\n"
        "Try asking something like:\n"
        "_\"How can I save for an emergency fund?\"_\n"
        "_\"What savings account is best for a goal?\"_"
    ),
    "4": HUMAN_SUPPORT_PLACEHOLDER,
}

_rag_answer_service: RAGAnswerService | None = None
_member_data_service: MemberDataService | None = None
_goal_service: GoalService | None = None
_goal_extractor: GoalExtractor | None = None
_education_service: PersonalizedEducationService | None = None
conversation_history = get_runtime_conversation_history()


def _get_rag_answer_service() -> RAGAnswerService:
    global _rag_answer_service
    if _rag_answer_service is None:
        _rag_answer_service = RAGAnswerService(RAGPipeline(), LLM())
    return _rag_answer_service


def _get_member_data_service() -> MemberDataService:
    global _member_data_service
    if _member_data_service is None:
        _member_data_service = MemberDataService()
    return _member_data_service


def _get_goal_service() -> GoalService:
    global _goal_service
    if _goal_service is None:
        _goal_service = GoalService()
    return _goal_service


def _get_goal_extractor() -> GoalExtractor:
    global _goal_extractor
    if _goal_extractor is None:
        _goal_extractor = GoalExtractor(LLM())
    return _goal_extractor


def _get_education_service() -> PersonalizedEducationService:
    global _education_service
    if _education_service is None:
        _education_service = PersonalizedEducationService()
    return _education_service


def _clean_ai_artifacts(text: str) -> str:
    """Strip common AI-writing artifacts that slip through despite prompt rules."""
    # Remove markdown bold/italic markers
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    # Replace em dashes and non-breaking hyphens with normal hyphens
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2011", "-")
    # Replace non-breaking spaces
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    # Remove sycophantic openers
    text = re.sub(
        r"^(Certainly!|Great question!|Absolutely!|Sure!|Of course!|I'd be happy to help[.!]?)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove "Here's/Here is" openers
    text = re.sub(r"^(Here'?s|Here is)[^:]*:\s*", "", text, flags=re.IGNORECASE)
    # Remove "Source:" blocks at the end
    text = re.sub(r"\n*Sources?:\s*\n.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove "Note:" disclaimer blocks at the end
    text = re.sub(
        r"\n*Note:\s*(?:The details|These|This|Please).*$",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.strip()


def _format_rag_response(response) -> str:
    return _clean_ai_artifacts(response.answer)


def _normalize(text: str) -> str:
    return text.strip()


def _is_greeting(text: str) -> bool:
    normalized = _normalize(text).lower()
    return normalized in GREETINGS


def _is_menu(text: str) -> bool:
    normalized = _normalize(text).lower()
    return normalized in MENU_TRIGGERS


def _handle_member_query(
    phone_number: str,
    query: str,
    member_service: MemberDataService | None = None,
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
            ok, prompt_msg, _ = a_svc.request_otp(phone_number, sacco_id=settings.DEFAULT_SACCO_ID)
            return prompt_msg

    service = member_service or _get_member_data_service()
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

    return format_member_response(
        snapshot,
        query,
        demo_label=settings.MEMBER_DATA_DEMO_MODE,
    )


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
    )
    return any(re.search(pat, lower) for pat in advisory_patterns)


async def _handle_goal_query(
    phone_number: str,
    query: str,
    member_service: MemberDataService | None = None,
    goal_service: GoalService | None = None,
    goal_extractor: GoalExtractor | None = None,
    context: str | None = None,
) -> str:
    """Resolve member identity and process financial goal creation, progress, or scenario analysis."""
    m_service = member_service or _get_member_data_service()
    profile = m_service.resolve_member(phone_number)
    if profile is None:
        if settings.MEMBER_DATA_DEMO_MODE:
            from app.database.member_repository import _hash_phone
            from app.schemas.member import MemberProfile
            profile = MemberProfile(
                id=f"demo_{_hash_phone(phone_number)[:8]}",
                display_name="Member",
                preferred_language="en",
                knowledge_level="beginner",
                sacco_id=settings.DEFAULT_SACCO_ID,
                is_demo=True,
            )
        else:
            return MEMBER_NOT_RECOGNIZED

    g_service = goal_service or _get_goal_service()
    extractor = goal_extractor or _get_goal_extractor()
    extracted = await extractor.extract_async(query, context=context)

    # 0. Balance update ("I have already saved KSh 80,000")
    if extracted.is_balance_update and extracted.current_amount is not None:
        active_goal = g_service.get_active_goal(profile.id)
        if active_goal:
            updated = g_service.update_goal_current_amount(active_goal.id, extracted.current_amount)
            if updated:
                return format_goal_updated(updated, demo_label=settings.MEMBER_DATA_DEMO_MODE)

    # 1. Scenario analysis ("What if I save 15k instead of 10k?")
    if extracted.is_scenario_query:
        active_goal = g_service.get_active_goal(profile.id)
        if not active_goal:
            return format_no_goals_message(profile.display_name, demo_label=settings.MEMBER_DATA_DEMO_MODE)
        scenario_amt = extracted.proposed_scenario_amount or 15000.0
        scenario = g_service.calculate_scenario(active_goal.id, scenario_amt)
        if scenario:
            return format_goal_scenario(scenario, demo_label=settings.MEMBER_DATA_DEMO_MODE)

    # 2. Progress inquiry ("What is my goal progress?")
    if extracted.is_progress_inquiry:
        active_goal = g_service.get_active_goal(profile.id)
        if not active_goal:
            return format_no_goals_message(profile.display_name, demo_label=settings.MEMBER_DATA_DEMO_MODE)
        return format_goal_progress(active_goal, demo_label=settings.MEMBER_DATA_DEMO_MODE)

    # 3. Missing info clarification
    if extracted.needs_clarification:
        return format_clarification_prompt(extracted.missing_fields)

    # 4. Create new goal
    has_current_amount = _parse_amount(query) is not None
    has_current_timeline = _parse_months(query) is not None
    has_current_goal_terms = any(w in query.lower() for w in ("goal", "save", "saving", "raise", "target", "create", "set", "changa"))

    if extracted.target_amount and extracted.target_date:
        if not has_current_amount and not has_current_timeline and not has_current_goal_terms:
            active_goal = g_service.get_active_goal(profile.id)
            if active_goal:
                return format_goal_progress(active_goal, demo_label=settings.MEMBER_DATA_DEMO_MODE)
            return format_clarification_prompt(["target_amount", "target_date"])

        heuristic_type, heuristic_name = _detect_goal_type(query + (" " + context if context else ""))
        final_type = extracted.goal_type or heuristic_type or GoalType.GENERAL_SAVINGS
        final_name = extracted.name if extracted.name and extracted.name != "Savings Goal" else heuristic_name

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
        return format_goal_created(created, demo_label=settings.MEMBER_DATA_DEMO_MODE)

    return format_clarification_prompt(["target_amount", "target_date"])


def handle_message(message: IncomingWhatsAppMessage) -> str:
    body = _normalize(message.body)

    if not body:
        if message.num_media and message.num_media != "0":
            return MEDIA_NOT_SUPPORTED
        return FALLBACK_MESSAGE

    if _is_greeting(body) or _is_menu(body):
        return WELCOME_MESSAGE

    menu_response = MENU_RESPONSES.get(body.strip())
    if menu_response:
        return menu_response

    return FALLBACK_MESSAGE


async def handle_message_async(
    message: IncomingWhatsAppMessage,
    intent_router: IntentRouter | None = None,
    rag_answer_service: RAGAnswerService | None = None,
    history_store: InMemoryConversationHistory | None = None,
    member_service: MemberDataService | None = None,
    goal_service: GoalService | None = None,
    goal_extractor: GoalExtractor | None = None,
    education_service: PersonalizedEducationService | None = None,
    feedback_service: MemberFeedbackService | None = None,
    auth_service: Any | None = None,
) -> str:
    body = _normalize(message.body)
    history_store = history_store or conversation_history

    if not body:
        return handle_message(message)

    if _is_greeting(body) or _is_menu(body):
        return WELCOME_MESSAGE

    menu_response = MENU_RESPONSES.get(body.strip())
    if menu_response:
        return menu_response

    # --- System 12: Member OTP verification reply check ---
    otp_match = re.match(r"^(?:VERIFY\s+)?(\d{6})$", body.strip(), re.IGNORECASE)
    if otp_match:
        from app.services.members.member_auth_service import MemberAuthService
        code = otp_match.group(1)
        a_svc = auth_service or MemberAuthService()
        success, sess, auth_msg = a_svc.verify_otp(message.from_number, code, sacco_id=settings.DEFAULT_SACCO_ID)
        return auth_msg

    # --- System 10: Feedback & MORE elaboration for proactive notifications ---
    feedback_svc = feedback_service or MemberFeedbackService()
    if feedback_svc.is_feedback_or_more_query(body):
        m_svc = member_service or MemberDataService()
        profile = m_svc.resolve_member(message.from_number)
        member_id = profile.id if profile else ""
        handled, reply = feedback_svc.handle_incoming_feedback(member_id, body)
        if handled and reply:
            return reply

    normalized = body.lower()

    # --- System 12: Fraud, stolen SIM, or unrecognized transaction security routing ---
    if re.search(r"\b(unrecognized|didn't authorize|did not authorize|fraud|stolen|scam|wrong deduction|reversed? money)\b", normalized):
        try:
            from app.services.admin.admin_escalation_service import AdminEscalationService
            m_svc = member_service or _get_member_data_service()
            prof = m_svc.resolve_member(message.from_number)
            esc = AdminEscalationService().record_from_conversation(
                conversation_key=message.from_number,
                query=body,
                member_id=prof.id if prof else None,
                sacco_id=settings.DEFAULT_SACCO_ID,
                category="fraud",
                priority="urgent",
            )
            return (
                f"Your report regarding an unrecognized transaction or security dispute has been escalated with urgent priority (Ticket #{esc.id}). "
                "A SACCO security and member accounts officer will contact you immediately."
            )
        except Exception as err:
            logger.warning("Failed to record fraud escalation: %s", err)
            return HUMAN_SUPPORT_PLACEHOLDER

    is_conversational_or_intent_like = bool(
        "?" in body
        or re.search(
            r"\b("
            r"what|why|how|when|where|who|which|can|could|do|does|did|is|are|am|will|would|should|"
            r"want|planning|plan|looking|aim|raise|save|saving|savings|invest|investing|investment|"
            r"deposit|deposits|withdraw|contribute|contribution|borrow|repay|repayment|pay|check|status|progress|"
            r"loan|loans|sacco|share|shares|stock|stocks|dividend|dividends|interest|member|membership|"
            r"account|accounts|salary|money|cash|fund|funds|capital|fee|fees|rate|rates|"
            r"goal|goals|target|targets|shop|business|biashara|duka|school|university|college|education|masomo|shule|"
            r"emergency|dharura|retire|retirement|pension|ustaafu|land|plot|shamba|house|nyumba|car|gari|expand|"
            r"nataka|nahitaji|ningependa|kujiunga|kufungua|kuweka|akiba|changa|nisaidie|nipatie|mkopo|mikopo|hisa|riba|"
            r"year|years|yr|yrs|month|months|mo|mos|week|weeks|mwaka|miaka|mwezi|miezi|verify|otp|code|"
            r"ksh|kes|shilling|shillings|shilingi"
            r")\b",
            normalized,
            re.IGNORECASE,
        )
        or bool(re.search(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", normalized))
    )

    if not is_conversational_or_intent_like:
        logger.info("Non-intent WhatsApp message treated as staff assistance fallback")
        return HUMAN_SUPPORT_PLACEHOLDER

    total_started = perf_counter()
    router_started = perf_counter()

    conversation_key = message.from_number
    previous_turns = history_store.get(conversation_key)
    context_str = None
    if previous_turns:
        context_str = "\n".join([f"{t.role}: {t.content}" for t in previous_turns[-4:]])

    router = intent_router or IntentRouter()
    try:
        result = await router.classify(body, context=context_str)
    except TypeError:
        result = await router.classify(body)
    logger.info("WhatsApp router latency: %.3fs", perf_counter() - router_started)

    # Check if this message is a follow-up to an active goal in progress or existing active goal
    g_svc = goal_service or _get_goal_service()
    m_svc = member_service or _get_member_data_service()
    prof = m_svc.resolve_member(message.from_number)
    has_active_goal = bool(prof and g_svc.get_active_goal(prof.id))
    has_goal_context = bool(
        context_str
        and any(k in context_str.lower() for k in ("goal", "target", "save", "saving", "contribution"))
    )

    is_goal_eligible = (
        result.is_goal_related
        or (has_goal_context and any(k in normalized for k in ("save", "saved", "saving", "manage", "afford", "month", "ksh", "kes", "thousand", "progress", "goal", "target", "enough", "yes", "no", "update")))
        or (has_active_goal and any(k in normalized for k in ("save", "saved", "saving", "manage", "afford", "month", "ksh", "kes", "thousand", "progress", "goal", "target", "enough")))
    ) and not _is_goal_advisory_or_educational_query(body)

    if is_goal_eligible:
        goal_started = perf_counter()
        response = await _handle_goal_query(
            message.from_number,
            body,
            member_service=member_service,
            goal_service=goal_service,
            goal_extractor=goal_extractor,
            context=context_str,
        )
        logger.info("Goal query latency: %.3fs", perf_counter() - goal_started)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        history_store.append(conversation_key, "user", body)
        history_store.append(conversation_key, "assistant", response)
        return response

    # --- Triage order: human escalation > member data > RAG / Personalized Education ---
    if result.likely_needs_human:
        try:
            from app.services.admin.admin_escalation_service import AdminEscalationService
            AdminEscalationService().record_from_conversation(
                conversation_key=message.from_number,
                query=body,
                member_id=prof.id if prof else None,
                sacco_id=settings.DEFAULT_SACCO_ID,
            )
        except Exception as esc_err:
            logger.warning("Failed to auto-record escalation ticket: %s", esc_err)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return HUMAN_SUPPORT_PLACEHOLDER

    if result.needs_member_data:
        member_started = perf_counter()
        response = _handle_member_query(
            message.from_number,
            body,
            member_service=member_service,
            auth_service=auth_service,
        )
        logger.info("Member-data lookup latency: %.3fs", perf_counter() - member_started)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return response

    try:
        answer_started = perf_counter()
        conversation_key = message.from_number
        previous_turns = history_store.get(conversation_key)

        if education_service is not None:
            edu_res = await education_service.explain(
                member_id_or_phone=message.from_number,
                query=body,
                override_language=result.language if result.language in ("en", "sw") else None,
            )
            response = _clean_ai_artifacts(edu_res.answer)
        elif rag_answer_service is not None:
            answer = await rag_answer_service.answer(
                query=body,
                sacco_id=settings.DEFAULT_SACCO_ID,
                language=result.language,
                conversation_history=[turn.model_dump() for turn in previous_turns],
            )
            response = _format_rag_response(answer)
        else:
            edu_svc = _get_education_service()
            edu_res = await edu_svc.explain(
                member_id_or_phone=message.from_number,
                query=body,
                override_language=result.language if result.language in ("en", "sw") else None,
            )
            response = _clean_ai_artifacts(edu_res.answer)

        logger.info("WhatsApp answer-service latency: %.3fs", perf_counter() - answer_started)
        history_store.append(conversation_key, "user", body)
        history_store.append(conversation_key, "assistant", response)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return response
    except Exception as exc:
        logger.exception("Grounded WhatsApp answer unavailable: %s", exc)
        logger.info("WhatsApp response latency: %.3fs", perf_counter() - total_started)
        return GENERAL_ASSISTANCE_PLACEHOLDER

