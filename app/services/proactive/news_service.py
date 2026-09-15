"""Trusted Financial News Service for System 10.

Manages curated, SACCO-approved financial news articles, matches them to member goals,
and generates concise, source-grounded WhatsApp summaries without directive investment advice.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.database.engagement_repository import EngagementRepository
from app.models.engagement import FinancialNewsArticle, NewsCategory, NewsFrequency
from app.models.goal import FinancialGoal, GoalType
from app.services.goals.goal_service import GoalService


@dataclass
class NewsRecommendation:
    """Recommended news item matched to member context."""
    member_id: str
    article: FinancialNewsArticle
    match_reason: str
    whatsapp_message: str
    is_eligible: bool = True
    ineligibility_reason: Optional[str] = None


class NewsService:
    """Handles news ingestion, goal-relevance matching, and safe WhatsApp formatting."""

    GOAL_CATEGORY_PREFERENCES = {
        GoalType.RETIREMENT: [NewsCategory.RETIREMENT, NewsCategory.SACCO_REGULATIONS, NewsCategory.INTEREST_RATES],
        GoalType.EDUCATION: [NewsCategory.INFLATION, NewsCategory.SAVING_TIPS, NewsCategory.EDUCATION_FUNDS],
        GoalType.EMERGENCY_FUND: [NewsCategory.INFLATION, NewsCategory.INTEREST_RATES, NewsCategory.SAVING_TIPS],
        GoalType.ASSET_PURCHASE: [NewsCategory.INTEREST_RATES, NewsCategory.GENERAL_ECONOMY, NewsCategory.SACCO_REGULATIONS],
        GoalType.GENERAL_SAVINGS: [NewsCategory.SAVING_TIPS, NewsCategory.INTEREST_RATES, NewsCategory.INFLATION],
    }

    def __init__(
        self,
        engagement_repo: Optional[EngagementRepository] = None,
        goal_service: Optional[GoalService] = None,
    ) -> None:
        self.engagement_repo = engagement_repo or EngagementRepository()
        self.goal_service = goal_service or GoalService()

    def get_active_articles(self, category: Optional[str] = None) -> list[FinancialNewsArticle]:
        """Fetch unexpired, approved news articles."""
        return self.engagement_repo.list_active_articles(category=category)

    def recommend_news_for_member(self, member_id: str) -> Optional[NewsRecommendation]:
        """Find the most relevant unexpired news article for a member."""
        prefs = self.engagement_repo.get_preferences(member_id)
        if prefs and prefs.news_frequency == NewsFrequency.PAUSED:
            return NewsRecommendation(
                member_id=member_id,
                article=None,  # type: ignore
                match_reason="",
                whatsapp_message="",
                is_eligible=False,
                ineligibility_reason="Member has paused financial news updates.",
            )

        active_articles = self.get_active_articles()
        if not active_articles:
            return None

        # Determine target categories based on member active goals
        target_categories = [NewsCategory.SAVING_TIPS, NewsCategory.INTEREST_RATES, NewsCategory.GENERAL_ECONOMY]
        goals = self.goal_service.get_member_goals(member_id)
        active_goals = [g for g in goals if getattr(g, "status", None) == "active" or getattr(g, "status", None) == "ACTIVE"]

        matched_goal: Optional[FinancialGoal] = None
        if active_goals:
            matched_goal = active_goals[0]
            g_type = matched_goal.goal_type
            if g_type in self.GOAL_CATEGORY_PREFERENCES:
                target_categories = self.GOAL_CATEGORY_PREFERENCES[g_type]

        # Find best unexpired article not sent recently
        chosen_article: Optional[FinancialNewsArticle] = None
        match_reason = "General financial update"

        for cat in target_categories:
            cat_val = cat.value if isinstance(cat, NewsCategory) else str(cat)
            candidates = [a for a in active_articles if a.category.value == cat_val]
            for candidate in candidates:
                if not self.engagement_repo.has_received_content_recently(member_id, candidate.id, within_days=30):
                    chosen_article = candidate
                    if matched_goal:
                        match_reason = f"Relevant to your {matched_goal.name} goal"
                    else:
                        match_reason = f"Matches your interest in {cat_val.replace('_', ' ')}"
                    break
            if chosen_article:
                break

        # Fallback to any unexpired article not received recently
        if not chosen_article:
            for candidate in active_articles:
                if not self.engagement_repo.has_received_content_recently(member_id, candidate.id, within_days=30):
                    chosen_article = candidate
                    match_reason = "Curated SACCO financial intelligence"
                    break

        if not chosen_article:
            return None

        # Build clean WhatsApp message
        msg = self._format_whatsapp_news(chosen_article, match_reason)

        return NewsRecommendation(
            member_id=member_id,
            article=chosen_article,
            match_reason=match_reason,
            whatsapp_message=msg,
            is_eligible=True,
        )

    def _format_whatsapp_news(self, article: FinancialNewsArticle, match_reason: str) -> str:
        """Format article summary adhering strictly to WhatsApp hygiene."""
        pub_date = ""
        if article.published_at:
            pub_date = f" ({article.published_at.strftime('%d %b %Y')})"

        summary_text = article.summary or article.content[:200]
        url_text = f"\nSource link: {article.url}" if article.url else ""

        return (
            f"Financial News Update{pub_date}\n"
            f"Source: {article.source}\n\n"
            f"{article.title}\n\n"
            f"{summary_text}\n"
            f"{url_text}\n\n"
            "Reply HELPFUL or NOT HELPFUL to adjust your news preferences."
        )
