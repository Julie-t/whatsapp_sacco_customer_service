"""Knowledge Gap Intelligence Service for System 10.

Aggregates unanswered member questions into executive SACCO intelligence, identifying
policy confusion hotspots and actionable knowledge-base improvements.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from app.models.knowledge_gap_event import KnowledgeGapEvent
from app.schemas.engagement import KnowledgeGapIntelligenceSummary, TopicConfusionMetric
from app.services.rag.knowledge_gap_repository import KnowledgeGapRepository


class KnowledgeGapIntelligenceService:
    """Transforms raw knowledge gaps into structured SACCO management intelligence."""

    TOPIC_KEYWORD_MAP = {
        "Loan Fees & Charges": ("fee", "charges", "interest rate", "cost", "deduction"),
        "Guarantor Rules & Exit": ("guarantor", "substitute", "replace guarantor", "release guarantor"),
        "Withdrawal Timelines": ("withdraw", "withdrawal", "notice period", "days to receive"),
        "Dividend Calculation": ("dividend", "rebate", "distribution", "annual return"),
        "Account Security & PIN": ("pin", "blocked", "reset", "password", "security"),
        "Shares & Equity Transfer": ("transfer shares", "sell shares", "share capital"),
    }

    ACTION_RECOMMENDATIONS = {
        "Loan Fees & Charges": "Publish a transparent fee schedule FAQ in member portal and onboarding leaflet.",
        "Guarantor Rules & Exit": "Add a dedicated FAQ on the 60-day guarantor replacement and discharge workflow.",
        "Withdrawal Timelines": "Clarify statutory notice periods (e.g. 60 days) in general savings product guide.",
        "Dividend Calculation": "Draft an educational one-pager explaining AGM dividend formula vs deposit interest.",
        "Account Security & PIN": "Implement automated USSD/SMS self-service PIN reset to relieve support desk.",
        "Shares & Equity Transfer": "Create clear documentation on the share transfer protocol between active members.",
    }

    def __init__(self, gap_repo: Optional[KnowledgeGapRepository] = None) -> None:
        self.gap_repo = gap_repo

    async def generate_summary(
        self, sacco_id: str = "demo_sacco", limit: int = 100
    ) -> KnowledgeGapIntelligenceSummary:
        """Aggregate knowledge gap events into top member confusion topics."""
        events: list[KnowledgeGapEvent] = []
        if self.gap_repo:
            try:
                events = await self.gap_repo.query_gaps_by_sacco(sacco_id=sacco_id, limit=limit)
            except Exception:
                events = []

        # Categorize events
        topic_counts: dict[str, int] = defaultdict(int)
        topic_samples: dict[str, list[str]] = defaultdict(list)

        for event in events:
            query_text = getattr(event, "query", None) or getattr(event, "user_query", "")
            query = (query_text or "").lower()
            matched_topic = "General SACCO Inquiries"

            for topic_name, keywords in self.TOPIC_KEYWORD_MAP.items():
                if any(kw in query for kw in keywords):
                    matched_topic = topic_name
                    break

            topic_counts[matched_topic] += 1
            if len(topic_samples[matched_topic]) < 3:
                topic_samples[matched_topic].append(query_text)

        # Build topic metrics
        metrics: list[TopicConfusionMetric] = []
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            action = self.ACTION_RECOMMENDATIONS.get(
                topic, "Review unanswered queries and enrich SACCO knowledge base documentation."
            )
            metrics.append(
                TopicConfusionMetric(
                    topic=topic,
                    question_count=count,
                    unanswered_queries=topic_samples[topic],
                    suggested_action=action,
                )
            )

        return KnowledgeGapIntelligenceSummary(
            total_unanswered_questions=len(events),
            top_topics=metrics,
            generated_at=datetime.now(timezone.utc),
        )
