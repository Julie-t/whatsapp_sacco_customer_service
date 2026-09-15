"""Tests for KnowledgeGapIntelligenceService (aggregation of member confusion hotspots)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest

from app.models.knowledge_gap_event import KnowledgeGapEvent
from app.services.rag.knowledge_gap_intelligence_service import KnowledgeGapIntelligenceService


@pytest.mark.anyio
async def test_generate_summary_aggregates_topics():
    mock_repo = AsyncMock()
    events = [
        KnowledgeGapEvent(
            sacco_id="demo_sacco",
            query="What are the hidden loan processing fees?",
            fallback_reason="knowledge_gap",
        ),
        KnowledgeGapEvent(
            sacco_id="demo_sacco",
            query="What is the appraisal fee on school fees loans?",
            fallback_reason="knowledge_gap",
        ),
        KnowledgeGapEvent(
            sacco_id="demo_sacco",
            query="How do I replace a guarantor who left the SACCO?",
            fallback_reason="knowledge_gap",
        ),
        KnowledgeGapEvent(
            sacco_id="demo_sacco",
            query="How long is the withdrawal notice period?",
            fallback_reason="knowledge_gap",
        ),
    ]
    mock_repo.query_gaps_by_sacco.return_value = events

    service = KnowledgeGapIntelligenceService(gap_repo=mock_repo)
    summary = await service.generate_summary(sacco_id="demo_sacco")

    assert summary.total_unanswered_questions == 4
    assert len(summary.top_topics) >= 3

    # Top topic should be Loan Fees & Charges (2 events)
    top = summary.top_topics[0]
    assert top.topic == "Loan Fees & Charges"
    assert top.question_count == 2
    assert "fee schedule FAQ" in top.suggested_action
    assert len(top.unanswered_queries) == 2
