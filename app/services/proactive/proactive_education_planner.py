"""Proactive Education Planner for System 10.

Selects relevant, grounded educational content based on member profile, active goals,
engagement preferences, and past educational history.
"""

from dataclasses import dataclass
from typing import Optional

from app.database.engagement_repository import EngagementRepository
from app.models.engagement import EducationFrequency, MemberEngagementPreferences
from app.models.personalization import KnowledgeLevel, PersonalizationContext
from app.services.education.personalization_context_builder import PersonalizationContextBuilder
from app.services.education.personalized_education_service import PersonalizedEducationService


@dataclass
class ProactiveEducationPlan:
    """A scheduled education message candidate for a member."""
    member_id: str
    topic: str
    message_body: str
    goal_id: Optional[str] = None
    goal_type: Optional[str] = None
    knowledge_level: KnowledgeLevel = KnowledgeLevel.BEGINNER
    interactive_prompt: str = "Reply MORE if you would like an example."
    is_eligible: bool = True
    ineligibility_reason: Optional[str] = None


class ProactiveEducationPlanner:
    """Plans proactive educational micro-lessons for SACCO members."""

    GOAL_TOPIC_MAP = {
        "emergency_fund": ["budgeting", "savings_discipline", "emergency_fund", "compound_interest"],
        "school_fees": ["budgeting", "savings_discipline", "debt_management", "emergency_fund"],
        "land_purchase": ["savings_discipline", "asset_purchase", "compound_interest", "debt_management"],
        "retirement": ["compound_interest", "savings_discipline", "retirement", "sacco_shares"],
        "general_savings": ["budgeting", "compound_interest", "savings_discipline", "emergency_fund"],
    }

    DEFAULT_CURRICULUM = [
        "budgeting",
        "savings_discipline",
        "emergency_fund",
        "compound_interest",
        "debt_management",
        "sacco_shares",
    ]

    TOPIC_EXPLANATIONS = {
        "budgeting": {
            KnowledgeLevel.BEGINNER: (
                "Since you are saving with our SACCO, a simple budget can make a big difference. "
                "A popular approach is dividing income into essentials, savings, and personal spending. "
                "Even saving KSh 500 consistently creates momentum."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "Practical cash flow allocation helps maintain regular savings. "
                "Using the 50/30/20 framework ensures that at least 20% of monthly income directly funds your SACCO savings and goals."
            ),
            KnowledgeLevel.ADVANCED: (
                "Strategic budgeting balances fixed monthly obligations against growth capital. "
                "Optimizing monthly discretionary expenses maximizes surplus allocated to high-yielding SACCO deposit accounts."
            ),
        },
        "compound_interest": {
            KnowledgeLevel.BEGINNER: (
                "When your savings earn returns that are added back to your balance, future returns build on that larger balance. "
                "Over time, your money earns its own money."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "Compounding yields accelerate savings when returns are retained rather than withdrawn. "
                "Reinvesting annual dividends generates exponential deposit growth."
            ),
            KnowledgeLevel.ADVANCED: (
                "Compound return mechanics maximize terminal asset accumulation over extended horizons, "
                "substantially outperforming linear nominal contribution growth."
            ),
        },
        "emergency_fund": {
            KnowledgeLevel.BEGINNER: (
                "An emergency fund is a financial safety net for unexpected costs like medical bills or repairs. "
                "Keeping 3 to 6 months of basic expenses in a SACCO account protects your main goals from being interrupted."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "An emergency buffer safeguards long-term investments by avoiding expensive short-term emergency loans. "
                "Maintain liquid reserves in regular savings for instant access."
            ),
            KnowledgeLevel.ADVANCED: (
                "Capital preservation reserves prevent forced liquidation of higher-yielding term deposits during unexpected liquidity shocks."
            ),
        },
        "debt_management": {
            KnowledgeLevel.BEGINNER: (
                "Not all debt is the same. Good debt helps you acquire an asset or grow an enterprise, "
                "while expensive high-interest debt drains your savings. Paying off costly loans first saves money."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "Strategic debt utilization involves comparing interest rates. "
                "SACCO loans at single-digit or reducing balance rates are more sustainable than digital short-term loans."
            ),
            KnowledgeLevel.ADVANCED: (
                "Optimizing leverage ratios and debt service coverage ensures debt functions as productive capital expansion rather than cash-flow drag."
            ),
        },
        "savings_discipline": {
            KnowledgeLevel.BEGINNER: (
                "Discipline means paying yourself first before spending. "
                "Setting up an automated standing order or check-off ensures your SACCO savings grow every month without extra effort."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "Automating monthly contributions minimizes behavioral friction and guarantees consistent progress toward your target."
            ),
            KnowledgeLevel.ADVANCED: (
                "Systematic contribution schedules eliminate market timing risk and reinforce institutional capital accumulation."
            ),
        },
        "retirement": {
            KnowledgeLevel.BEGINNER: (
                "Retirement planning starts early. Consistent small contributions build substantial security over time."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "Long-term retirement compounding through SACCO schemes protects purchasing power against inflation."
            ),
            KnowledgeLevel.ADVANCED: (
                "Asset-liability matching in retirement planning ensures post-active income replacement through structured annuity-like dividend flows."
            ),
        },
        "sacco_shares": {
            KnowledgeLevel.BEGINNER: (
                "Share capital makes you an owner of the SACCO and earns annual dividends. It cannot be withdrawn, but it can be transferred."
            ),
            KnowledgeLevel.INTERMEDIATE: (
                "Non-withdrawable share capital forms the permanent equity base of the SACCO, typically generating healthy annual dividend payouts."
            ),
            KnowledgeLevel.ADVANCED: (
                "Equity capital participation aligns member interests with institutional profitability, delivering dual benefits of dividend yield and voting rights."
            ),
        },
    }

    def __init__(
        self,
        context_builder: Optional[PersonalizationContextBuilder] = None,
        engagement_repo: Optional[EngagementRepository] = None,
        education_service: Optional[PersonalizedEducationService] = None,
    ) -> None:
        self.context_builder = context_builder or PersonalizationContextBuilder()
        self.engagement_repo = engagement_repo or EngagementRepository()
        self.education_service = education_service or PersonalizedEducationService()

    def plan_next_lesson(self, member_id: str) -> ProactiveEducationPlan:
        """Evaluate member context and determine the next educational micro-lesson."""
        prefs = self.engagement_repo.get_preferences(member_id)
        if prefs and prefs.education_frequency == EducationFrequency.PAUSED:
            return ProactiveEducationPlan(
                member_id=member_id,
                topic="",
                message_body="",
                is_eligible=False,
                ineligibility_reason="Member has paused proactive education notifications.",
            )

        context = self.context_builder.build_context(member_id)
        allowed = prefs.allowed_topics if prefs else self.DEFAULT_CURRICULUM

        # Determine curriculum sequence based on active goal
        goal_type = None
        goal_id = None
        if context.active_goal:
            goal_type = getattr(context.active_goal, "goal_type", None)
            if hasattr(goal_type, "value"):
                goal_type = goal_type.value
            goal_id = getattr(context.active_goal, "id", None)

        curriculum = self.GOAL_TOPIC_MAP.get(str(goal_type), self.DEFAULT_CURRICULUM)

        # Select candidate: in allowed and not in recent_topics
        candidate_topic = None
        for topic in curriculum:
            if topic in allowed and topic not in context.recent_topics:
                candidate_topic = topic
                break

        # If all curriculum topics were taught recently, fallback to any allowed topic not in recent
        if not candidate_topic:
            for topic in self.DEFAULT_CURRICULUM:
                if topic in allowed and topic not in context.recent_topics:
                    candidate_topic = topic
                    break

        # If all have been completed, cycle back to the first allowed topic
        if not candidate_topic:
            candidate_topic = allowed[0] if allowed else "saving"

        # Generate the micro-lesson message
        level = context.knowledge_level or KnowledgeLevel.BEGINNER
        level_map = self.TOPIC_EXPLANATIONS.get(candidate_topic, self.TOPIC_EXPLANATIONS["budgeting"])
        explanation = level_map.get(level, level_map[KnowledgeLevel.BEGINNER])

        name = context.display_name.split()[0] if context.display_name else "Member"
        greeting = f"Habari {name}." if context.preferred_language in ("sw", "mixed") else f"Hello {name}."

        goal_anchor = ""
        if context.active_goal:
            g_name = getattr(context.active_goal, "name", None) or getattr(context.active_goal, "title", None) or str(goal_type or "savings").replace("_", " ")
            goal_anchor = f" As you work toward your {g_name} goal, here is a helpful principle."

        topic_display = candidate_topic.replace("_", " ").title()
        message = (
            f"{greeting} This week's financial tip is about {topic_display}.{goal_anchor}\n\n"
            f"{explanation}\n\n"
            "Reply MORE if you would like an example."
        )

        return ProactiveEducationPlan(
            member_id=member_id,
            topic=candidate_topic,
            message_body=message,
            goal_id=goal_id,
            goal_type=str(goal_type) if goal_type else None,
            knowledge_level=level,
            interactive_prompt="Reply MORE if you would like an example.",
            is_eligible=True,
        )
