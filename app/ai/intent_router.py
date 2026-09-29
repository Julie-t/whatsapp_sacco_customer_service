import json
import logging
import re
from typing import Sequence

from app.ai.llm import LLM
from app.ai.operation_registry import OperationDefinition, OperationRegistry
from app.ai.prompts import DECISION_ROUTER_PROMPT_TEMPLATE, ROUTER_PROMPT
from app.ai.routing_types import OperationType, WorkflowType
from app.schemas.intent import RequestTriageResult, RoutingDecision

logger = logging.getLogger(__name__)


def _parse_triage_response(raw_response: str) -> RoutingDecision:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))
    return RoutingDecision.model_validate(payload)


def classify_deterministic(message: str) -> RoutingDecision | None:
    """Lightweight deterministic pre-router for high-confidence common requests.

    Confidently routes:
    - Obvious greetings (e.g. 'Hello', 'Habari', 'Good morning')
    - Obvious help/menu triggers (e.g. 'HELP', 'menu')
    - Obvious human escalations (e.g. 'speak to someone', unrecognized transaction)
    - Obvious personal member data requests (e.g. 'What is my balance?', 'When is my next payment?')

    Any ambiguous, general, or educational inquiries return None and fall
    through to the full LLM Request Router.
    """
    raw = message.strip()
    if not raw:
        return None

    normalized = raw.lower()
    cleaned = re.sub(r"[^\w\s]", " ", normalized)
    words = cleaned.split()

    sw_words = {
        "habari", "mambo", "jambo", "sasa", "vipi", "akiba", "mkopo", "mikopo",
        "deni", "salio", "pesa", "shilingi", "nisaidie", "asante", "karibu",
    }
    language = "sw" if any(w in words for w in sw_words) else "en"

    # 1. Obvious Greetings
    greeting_pattern = (
        r"^(?:hello|hi|hey|habari|habari\s+yako|habari\s+za\s+\w+|"
        r"mambo|mambo\s+vipi|jambo|sasa|good\s+morning|good\s+afternoon|"
        r"good\s+evening|good\s+day)(?:\s+(?:sacco|there|admin|rafiki|companion))?[\s!.,?]*$"
    )
    if re.match(greeting_pattern, normalized, re.IGNORECASE):
        return RoutingDecision(
            language=language,
            needs_member_data=False,
            is_goal_related=False,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="Deterministic greeting fast path",
            workflow=WorkflowType.SACCO_INFORMATION,
        )

    # 2. Obvious HELP / Menu
    if re.match(r"^(?:help|menu|msaada)[\s!.]*$", normalized, re.IGNORECASE):
        return RoutingDecision(
            language=language,
            needs_member_data=False,
            is_goal_related=False,
            is_education_related=False,
            likely_needs_human=False,
            reasoning="Deterministic menu fast path",
            workflow=WorkflowType.SACCO_INFORMATION,
        )

    # 3. Obvious Human Escalation & Security Disputes
    escalation_patterns = (
        r"\b(?:speak|talk)\s+to\s+(?:someone|a\s+human|an?\s+agent|a\s+person|staff|customer\s+(?:care|service))\b",
        r"\b(?:connect|transfer)\s+(?:me\s+)?to\s+(?:someone|a\s+human|an?\s+agent|staff|customer\s+(?:care|service))\b",
        r"\b(?:customer\s+care|customer\s+service)\s+(?:agent|number|help|representative)\b",
        r"\bi\s+want\s+to\s+(?:speak|talk|reach|contact)\s+(?:to\s+)?(?:someone|a\s+person|an?\s+agent|staff|human)\b",
        r"\bi\s+(?:want|need|wish)\s+to\s+make\s+a\s+complaint\b",
        r"\b(?:unrecognized|unauthorized|didn't\s+authorize|did\s+not\s+authorize)\s+transaction\b",
        r"\b(?:someone\s+used\s+my\s+account|stolen\s+sim|stolen\s+phone|fraud|scam|wrong\s+deduction|reversed?\s+money)\b",
    )
    if any(re.search(pat, normalized, re.IGNORECASE) for pat in escalation_patterns):
        return RoutingDecision(
            language=language,
            needs_member_data=False,
            is_goal_related=False,
            is_education_related=False,
            likely_needs_human=True,
            reasoning="Deterministic human escalation fast path",
            workflow=WorkflowType.HUMAN_ESCALATION,
            operation=OperationType.ESCALATION_SUPPORT.value,
        )

    # 4. Obvious Member Data Requests
    general_inquiry_patterns = (
        r"\b(?:types?\s+of\s+loans?|kinds?\s+of\s+loans?|loan\s+types?|what\s+loans?\s+do\s+you)\b",
        r"\b(?:interest\s+rates?|rates?\s+of\s+interest|what\s+is\s+the\s+rate|what\s+are\s+the\s+rates)\b",
        r"\b(?:how\s+(?:to|can\s+i|do\s+i)\s+apply|requirements?|qualify|qualifications?|eligibility|eligible)\b",
        r"\b(?:compound\s+interest|how\s+does\s+(?:it|compound|savings?)\s+work|difference\s+between)\b",
        r"\b(?:products?|options?|terms?\s+and\s+conditions?|policy|explain)\b",
    )
    is_general_inquiry = any(re.search(pat, normalized, re.IGNORECASE) for pat in general_inquiry_patterns)

    if not is_general_inquiry:
        member_data_patterns = (
            # Balance checks
            r"^(?:what\s+is\s+my\s+balance|check\s+my\s+balance|my\s+balance|show\s+my\s+balance|view\s+my\s+balance|how\s+much\s+(?:do\s+i\s+have|is\s+in\s+my\s+account)|salio\s+langu)[\s!.,?]*$",
            r"^(?:account\s+balance|savings\s+balance|share\s+balance|my\s+savings|my\s+shares)[\s!.,?]*$",
            # Loan balance / debt checks
            r"^(?:what\s+is\s+my\s+loan\s+balance|what\s+about\s+my\s+loan|how\s+much\s+do\s+i\s+(?:still\s+)?owe|what\s+do\s+i\s+owe|how\s+much\s+is\s+my\s+loan|check\s+my\s+loan|my\s+loan\s+balance|deni\s+langu|mkopo\s+wangu)[\s!.,?]*$",
            r"^what\s+about\s+my\s+loan\b.*how\s+much\s+do\s+i\s+(?:still\s+)?owe[\s!.,?]*$",
            # Next payment / instalment / schedule checks
            r"^(?:when\s+is\s+my\s+next\s+payment|when\s+is\s+my\s+next\s+instalment|when\s+is\s+my\s+next\s+installment|when\s+do\s+i\s+pay|what\s+is\s+my\s+next\s+payment|next\s+payment\s+date|due\s+date\s+of\s+my\s+loan|how\s+much\s+is\s+my\s+instalment)[\s!.,?]*$",
            # Statement / contributions
            r"^(?:my\s+statement|account\s+statement|my\s+contributions|monthly\s+contributions)[\s!.,?]*$",
        )
        if any(re.search(pat, normalized, re.IGNORECASE) for pat in member_data_patterns):
            op = OperationType.MEMBER_BALANCE.value
            if "loan" in normalized or "owe" in normalized or "mkopo" in normalized:
                op = OperationType.MEMBER_LOAN_BALANCE.value
            elif "next" in normalized or "due" in normalized or "pay" in normalized:
                op = OperationType.MEMBER_NEXT_PAYMENT.value
            return RoutingDecision(
                language=language,
                needs_member_data=True,
                is_goal_related=False,
                is_education_related=False,
                likely_needs_human=False,
                reasoning="Deterministic member data fast path",
                workflow=WorkflowType.MEMBER_DATA,
                operation=op,
            )

    # 5. Obvious Financial Education / Savings Strategy Requests
    education_patterns = (
        r"\b(?:income\s+changes|irregular\s+income|variable\s+income|fluctuat\w*)\b.*\b(?:sav(?:e|ing|ings)|budget|plan)\b",
        r"\b(?:how\s+(?:should|can|do)\s+i\s+(?:think\s+about\s+)?sav(?:e|ing)|how\s+to\s+save)\b.*\b(?:income|irregular|variable|fluctuat\w*|slow|busy)\b",
        r"\b(?:how\s+should\s+i\s+think\s+about\s+saving)\b",
        r"\b(?:busy\s+(?:and|months?).*slow\s+months?|slow\s+(?:and|months?).*busy\s+months?)\b",
    )
    if any(re.search(pat, normalized, re.IGNORECASE) for pat in education_patterns):
        return RoutingDecision(
            language=language,
            needs_member_data=False,
            is_goal_related=False,
            is_education_related=True,
            likely_needs_human=False,
            reasoning="Deterministic financial education fast path",
            workflow=WorkflowType.EDUCATION,
            operation=OperationType.EDUCATION_SAVING_STRATEGY.value,
        )

    return None


class IntentRouter:
    """Decision center for routing incoming customer queries to workflows."""

    def __init__(self, llm: LLM | None = None, registry: OperationRegistry | None = None):
        self.llm = llm or LLM()
        self.registry = registry or OperationRegistry()
        self.last_used_llm: bool = False

    async def classify(
        self,
        message: str,
        context: str | None = None,
        candidate_operations: Sequence[OperationDefinition] | None = None,
    ) -> RoutingDecision:
        deterministic_result = classify_deterministic(message)
        if deterministic_result is not None:
            self.last_used_llm = False
            logger.info(
                "Request triage resolved | route=deterministic_%s llm_called=false",
                deterministic_result.workflow.value,
            )
            return deterministic_result

        self.last_used_llm = True
        try:
            if candidate_operations:
                candidate_str = self.registry.format_candidates_for_prompt(candidate_operations)
                system_content = DECISION_ROUTER_PROMPT_TEMPLATE.format(
                    candidate_operations=candidate_str,
                    context_str=context or "None",
                    query=message,
                )
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": message},
                ]
            else:
                system_content = ROUTER_PROMPT
                if context:
                    system_content += f"\n\nRECENT CONVERSATION CONTEXT:\n{context}"
                messages = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": message},
                ]

            raw_response = await self.llm.generate(messages)
            result = _parse_triage_response(raw_response)
            logger.info(
                "Request triage resolved | route=%s operation=%s llm_called=true",
                result.workflow.value,
                result.operation,
            )
            return result
        except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
            logger.warning("Request triage failed safely: %s", exc)
            return RoutingDecision.fallback()