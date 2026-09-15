"""Personalized Financial Education & Goal-Aware Coaching Service.

Combines member profile, active goals, and deterministic calculations with
approved SACCO knowledge to deliver tailored financial explanations.
"""

import inspect
import logging
import re
from typing import Optional

from app.ai.llm import LLM
from app.ai.prompts import PERSONALIZED_EDUCATION_SYSTEM_PROMPT
from app.ai.rag.context import build_context, select_context
from app.ai.rag.pipeline import RAGPipeline
from app.config.settings import settings
from app.database.personalization_repository import PersonalizationHistoryRepository
from app.models.personalization import EducationTopic, KnowledgeLevel, PersonalizationContext
from app.schemas.personalization import PersonalizedEducationResponse
from app.services.rag.knowledge_gap_service import KnowledgeGapService
from app.services.education.personalization_context_builder import PersonalizationContextBuilder

logger = logging.getLogger(__name__)

DIRECTIVE_INVESTMENT_TERMS = (
    "should i invest in",
    "tell me where to invest",
    "which stock",
    "crypto",
    "cryptocurrency",
    "bitcoin",
    "stock market",
    "guaranteed return",
    "which shares should i buy",
    "put my money into",
)

GUARDRAIL_EDUCATION_DISCLAIMER = (
    "As a SACCO financial coach, I can explain savings principles, compound growth, and "
    "budgeting strategies, but I cannot give specific investment advice or recommend individual "
    "stocks, funds, or speculative assets like cryptocurrencies. Please consult a licensed "
    "financial advisor or visit our branch for official investment options."
)


class PersonalizedEducationService:
    """Delivers member-personalized financial education grounded in approved SACCO knowledge."""

    def __init__(
        self,
        pipeline: Optional[RAGPipeline] = None,
        llm: Optional[LLM] = None,
        context_builder: Optional[PersonalizationContextBuilder] = None,
        history_repo: Optional[PersonalizationHistoryRepository] = None,
        knowledge_gap_service: Optional[KnowledgeGapService] = None,
    ) -> None:
        self.pipeline = pipeline or RAGPipeline()
        self.llm = llm or LLM()
        self.context_builder = context_builder or PersonalizationContextBuilder()
        self.history_repo = history_repo or PersonalizationHistoryRepository()
        self.knowledge_gap_service = knowledge_gap_service or KnowledgeGapService()

    @staticmethod
    def detect_topic(query: str) -> str:
        """Infer financial education topic from the query."""
        normalized = query.lower()
        if any(term in normalized for term in ("compound", "riba", "interest on interest")):
            return EducationTopic.COMPOUND_INTEREST.value
        if any(term in normalized for term in ("budget", "50/30/20", "spending", "expenses")):
            return EducationTopic.BUDGETING.value
        if any(term in normalized for term in ("emergency", "buffer", "rainy day", "dharura")):
            return EducationTopic.EMERGENCY_FUND.value
        if any(term in normalized for term in ("debt", "loan repayment", "deni", "snowball")):
            return EducationTopic.DEBT_MANAGEMENT.value
        if any(term in normalized for term in ("share", "dividend", "hisa", "capital")):
            return EducationTopic.SACCO_SHARES.value
        if any(term in normalized for term in ("retire", "pension", "uzee")):
            return EducationTopic.RETIREMENT.value
        if any(term in normalized for term in ("save", "saving", "akiba", "discipline")):
            return EducationTopic.SAVINGS_DISCIPLINE.value
        return EducationTopic.GENERAL_EDUCATION.value

    @staticmethod
    def is_directive_investment_query(query: str) -> bool:
        """Check if query requests prohibited speculative/directive investment advice."""
        normalized = query.lower()
        return any(term in normalized for term in DIRECTIVE_INVESTMENT_TERMS)

    @staticmethod
    def is_curriculum_recommendation_query(query: str) -> bool:
        """Check if query is asking what to learn or seeking learning recommendations."""
        lower = query.lower()
        patterns = (
            r"\b(?:what|which)\s+(?:financial\s+)?(?:information|topics?|concepts?|things?|lessons?)\b.*\b(?:learn|study|read|explore)\b",
            r"\b(?:what\s+should\s+i\s+learn)\b",
            r"\b(?:recommend\s+(?:me\s+)?(?:a\s+)?(?:topic|lesson|something\s+to\s+learn))\b",
            r"\b(?:what\s+(?:can|could)\s+i\s+learn)\b",
            r"\b(?:what\s+is\s+useful\s+to\s+learn)\b",
        )
        return any(re.search(pat, lower) for pat in patterns)

    async def explain(
        self,
        member_id_or_phone: str,
        query: str,
        override_language: Optional[str] = None,
        sacco_id: str = "demo_sacco",
    ) -> PersonalizedEducationResponse:
        """Generate a personalized, grounded educational explanation."""
        # 1. Check directive investment guardrail first
        if self.is_directive_investment_query(query):
            return PersonalizedEducationResponse(
                answer=GUARDRAIL_EDUCATION_DISCLAIMER,
                topic="guardrail",
                knowledge_level_applied="beginner",
                goal_context_applied=None,
                language_applied=override_language or "en",
                sources=[],
                is_demo=settings.MEMBER_DATA_DEMO_MODE,
            )

        # 2. Build structured PersonalizationContext
        ctx = self.context_builder.build_context(member_id_or_phone, query=query)
        language = override_language or ctx.preferred_language or "en"
        topic = self.detect_topic(query)

        # Handle curriculum and learning recommendations directly
        if self.is_curriculum_recommendation_query(query):
            goal_line = f"toward your goal of {ctx.active_goal.name}" if ctx.active_goal else "for your financial journey"
            lines = [
                f"Here are 3 key financial topics that will help you {goal_line}:",
                "",
                "1. Budgeting and the 50/30/20 rule: Manage daily expenses and free up money to save.",
                "2. Compound interest: Understand how your deposits grow and earn returns over time.",
                "3. SACCO shares and dividends: Learn how member ownership builds long-term wealth.",
                "",
                "Which of these would you like to explore first? (Just ask me, for example: 'Explain compound interest')",
            ]
            if settings.MEMBER_DATA_DEMO_MODE:
                lines.append("")
                lines.append("(demo data)")
            return PersonalizedEducationResponse(
                answer="\n".join(lines),
                topic="curriculum_recommendation",
                knowledge_level_applied=ctx.knowledge_level.value,
                goal_context_applied=ctx.active_goal.name if ctx.active_goal else None,
                language_applied=language,
                sources=["financial_education_curriculum"],
                is_demo=settings.MEMBER_DATA_DEMO_MODE,
            )

        # 3. Retrieve approved SACCO knowledge
        try:
            retrieved = self.pipeline.search(
                query=query,
                sacco_id=sacco_id,
                language=language if language in ("en", "sw") else "en",
                top_k=5,
            )
            selected_results = select_context(query, retrieved)
        except Exception as search_err:
            logger.warning("RAG pipeline search failed: %s", search_err)
            retrieved = []
            selected_results = []

        # If no relevant context found, track knowledge gap and return fallback
        if not selected_results or (retrieved and retrieved[0].score < settings.RAG_MIN_SCORE):
            gap_res = self.knowledge_gap_service.record_gap(
                query=query,
                sacco_id=sacco_id,
                retrieved_results=retrieved,
                language=language,
            )
            if inspect.isawaitable(gap_res):
                await gap_res
            fallback_text = (
                "Sikuweza kupata maelezo hayo katika kumbukumbu za SACCO. Tafadhali wasiliana na afisa wa SACCO kwa usaidizi."
                if language == "sw"
                else "I could not find that specific topic in the SACCO knowledge base. Please contact a SACCO representative for detailed guidance."
            )
            return PersonalizedEducationResponse(
                answer=fallback_text,
                topic=topic,
                knowledge_level_applied=ctx.knowledge_level.value,
                goal_context_applied=ctx.active_goal.name if ctx.active_goal else None,
                language_applied=language,
                sources=[],
                is_demo=settings.MEMBER_DATA_DEMO_MODE,
            )

        context_str = build_context(selected_results)
        sources = [item.document_id for item in selected_results]

        # 4. Format goal section if active goal exists
        goal_section = ""
        goal_context_name = None
        if ctx.active_goal and ctx.goal_progress:
            goal_context_name = ctx.active_goal.name
            calc = ctx.goal_progress
            goal_section = (
                f"\nACTIVE MEMBER GOAL:\n"
                f"- Name: {ctx.active_goal.name}\n"
                f"- Target Amount: KSh {ctx.active_goal.target_amount:,.0f}\n"
                f"- Target Date: {ctx.active_goal.target_date}\n"
                f"- Current Balance: KSh {calc.current_amount:,.0f} ({calc.progress_percentage:.0f}% reached)\n"
                f"- Remaining Gap: KSh {calc.amount_remaining:,.0f}\n"
                f"- Required Monthly Contribution: KSh {calc.required_monthly_contribution:,.0f}\n"
                f"- Assessment: {calc.pace_assessment}\n"
            )

        # 5. Format prompt and generate explanation
        system_prompt = PERSONALIZED_EDUCATION_SYSTEM_PROMPT.format(
            sacco_name="Demo SACCO",
            member_name=ctx.display_name,
            knowledge_level=ctx.knowledge_level.value,
            preferred_language=language,
            goal_section=goal_section,
            context=context_str,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        raw_answer = await self.llm.generate(messages)

        # 6. Apply WhatsApp formatting hygiene
        clean_answer = self._clean_whatsapp_formatting(raw_answer)

        # Append demo disclaimer if configured
        if settings.MEMBER_DATA_DEMO_MODE:
            clean_answer += " (demo data)"

        # 7. Record topic in member history
        if ctx.member_id:
            try:
                self.history_repo.record_topic(
                    member_id=ctx.member_id,
                    topic=topic,
                    summary=clean_answer[:150],
                    goal_id=ctx.active_goal.id if ctx.active_goal else None,
                )
            except Exception as exc:
                logger.warning("Failed to record education history for %s: %s", ctx.member_id, exc)

        return PersonalizedEducationResponse(
            answer=clean_answer,
            topic=topic,
            knowledge_level_applied=ctx.knowledge_level.value,
            goal_context_applied=goal_context_name,
            language_applied=language,
            sources=sources,
            is_demo=settings.MEMBER_DATA_DEMO_MODE,
        )

    @staticmethod
    def _clean_whatsapp_formatting(text: str) -> str:
        """Strip markdown asterisks and em dashes for clean WhatsApp presentation."""
        # Strip bold/italic asterisks
        text = text.replace("*", "")
        # Replace em/en dashes
        text = text.replace("—", ", ").replace("–", "-")
        # Remove sycophantic greetings if present
        text = re.sub(r"^(Certainly!|Great question!|Sure!|Hello!)\s*", "", text, flags=re.IGNORECASE)
        # Normalize whitespace
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()
