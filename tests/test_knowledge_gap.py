"""Tests for knowledge gap tracking (System 6.4)."""

import pytest

from app.models.knowledge_gap_event import KnowledgeGapEvent
from app.services.knowledge_gap_repository import (
    InMemoryKnowledgeGapRepository,
)
from app.services.knowledge_gap_service import KnowledgeGapService


@pytest.mark.anyio
async def test_record_knowledge_gap_event():
    """Recording a knowledge gap should create an event."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    event_id = await service.record_gap(
        query="What is the USD/KES exchange rate?",
        sacco_id="demo_sacco",
        language="en",
        top_retrieval_score=0.35,
        fallback_reason="knowledge_gap",
    )

    assert event_id is not None
    assert len(repo.events) == 1
    assert repo.events[0].query == "What is the USD/KES exchange rate?"


@pytest.mark.anyio
async def test_multiple_gaps_recorded():
    """Multiple knowledge gaps should be recorded separately."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    for i in range(3):
        await service.record_gap(
            query=f"Question {i}",
            sacco_id="demo_sacco",
            language="en",
            fallback_reason="knowledge_gap",
        )

    assert len(repo.events) == 3


@pytest.mark.anyio
async def test_query_gaps_by_sacco():
    """Should query gaps filtered by SACCO."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    # Add gaps for different SACCOs
    await service.record_gap("Q1", sacco_id="sacco_a", fallback_reason="knowledge_gap")
    await service.record_gap("Q2", sacco_id="sacco_a", fallback_reason="knowledge_gap")
    await service.record_gap("Q3", sacco_id="sacco_b", fallback_reason="knowledge_gap")

    gaps_a = await service.get_gaps_by_sacco("sacco_a")
    gaps_b = await service.get_gaps_by_sacco("sacco_b")

    assert len(gaps_a) == 2
    assert len(gaps_b) == 1
    assert all(g.sacco_id == "sacco_a" for g in gaps_a)
    assert all(g.sacco_id == "sacco_b" for g in gaps_b)


@pytest.mark.anyio
async def test_gaps_ordered_by_timestamp():
    """Gaps should be returned in reverse chronological order."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    await service.record_gap("First", sacco_id="demo_sacco", fallback_reason="knowledge_gap")
    await service.record_gap("Second", sacco_id="demo_sacco", fallback_reason="knowledge_gap")
    await service.record_gap("Third", sacco_id="demo_sacco", fallback_reason="knowledge_gap")

    gaps = await service.get_gaps_by_sacco("demo_sacco")

    assert gaps[0].query == "Third"
    assert gaps[1].query == "Second"
    assert gaps[2].query == "First"


@pytest.mark.anyio
async def test_count_gaps_by_fallback():
    """Should count gaps grouped by fallback reason."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    await service.record_gap("Q1", sacco_id="demo_sacco", fallback_reason="knowledge_gap")
    await service.record_gap("Q2", sacco_id="demo_sacco", fallback_reason="knowledge_gap")
    await service.record_gap("Q3", sacco_id="demo_sacco", fallback_reason="clarification")
    await service.record_gap("Q4", sacco_id="demo_sacco", fallback_reason="clarification")
    await service.record_gap("Q5", sacco_id="demo_sacco", fallback_reason="guardrail")

    counts = await service.get_gap_summary("demo_sacco")

    assert len(counts) > 0


@pytest.mark.anyio
async def test_pagination_with_limit_offset():
    """Should support pagination."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    for i in range(15):
        await service.record_gap(f"Q{i}", sacco_id="demo_sacco", fallback_reason="knowledge_gap")

    # Get first 5
    page1 = await service.get_gaps_by_sacco("demo_sacco", limit=5, offset=0)
    # Get next 5
    page2 = await service.get_gaps_by_sacco("demo_sacco", limit=5, offset=5)

    assert len(page1) == 5
    assert len(page2) == 5
    assert page1[0].query != page2[0].query


@pytest.mark.anyio
async def test_language_metadata_preserved():
    """Language metadata should be preserved."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    await service.record_gap(
        "English question?",
        sacco_id="demo_sacco",
        language="en",
        fallback_reason="knowledge_gap",
    )
    await service.record_gap(
        "Swahili question?",
        sacco_id="demo_sacco",
        language="sw",
        fallback_reason="knowledge_gap",
    )

    gaps = await service.get_gaps_by_sacco("demo_sacco")

    en_gaps = [g for g in gaps if g.language == "en"]
    sw_gaps = [g for g in gaps if g.language == "sw"]

    assert len(en_gaps) == 1
    assert len(sw_gaps) == 1


@pytest.mark.anyio
async def test_retrieval_score_recorded():
    """Retrieval score should be recorded when available."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    await service.record_gap(
        "Query",
        sacco_id="demo_sacco",
        top_retrieval_score=0.42,
        fallback_reason="knowledge_gap",
    )

    gaps = await service.get_gaps_by_sacco("demo_sacco")
    assert gaps[0].top_retrieval_score == 0.42


@pytest.mark.anyio
async def test_knowledge_gap_event_creation():
    """KnowledgeGapEvent should be properly structured."""
    event = KnowledgeGapEvent(
        id="gap_001",
        query="Test query",
        sacco_id="demo_sacco",
        language="en",
        top_retrieval_score=0.5,
        fallback_reason="knowledge_gap",
    )

    assert event.id == "gap_001"
    assert event.query == "Test query"
    assert event.sacco_id == "demo_sacco"
    assert event.language == "en"


def test_knowledge_gap_event_without_id():
    """KnowledgeGapEvent should allow None ID (auto-generated later)."""
    event = KnowledgeGapEvent(
        id=None,
        query="Test",
        sacco_id="demo_sacco",
        fallback_reason="knowledge_gap",
    )

    assert event.id is None
    assert event.query == "Test"


@pytest.mark.anyio
async def test_conversation_id_optional():
    """Conversation ID should be optional."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    # Record without conversation_id
    id1 = await service.record_gap(
        "Q1",
        sacco_id="demo_sacco",
        fallback_reason="knowledge_gap",
    )
    # Record with conversation_id
    id2 = await service.record_gap(
        "Q2",
        sacco_id="demo_sacco",
        conversation_id="conv_123",
        fallback_reason="knowledge_gap",
    )

    gaps = await service.get_gaps_by_sacco("demo_sacco")
    assert gaps[0].conversation_id == "conv_123"
    assert gaps[1].conversation_id is None


@pytest.mark.anyio
async def test_member_id_optional():
    """Member ID should be optional and can be hashed."""
    repo = InMemoryKnowledgeGapRepository()
    service = KnowledgeGapService(repo)

    await service.record_gap(
        "Q1",
        sacco_id="demo_sacco",
        member_id="member_hash_xyz",
        fallback_reason="knowledge_gap",
    )

    gaps = await service.get_gaps_by_sacco("demo_sacco")
    assert gaps[0].member_id == "member_hash_xyz"


@pytest.mark.anyio
async def test_in_memory_repo_isolation():
    """Multiple repo instances should not share state."""
    repo1 = InMemoryKnowledgeGapRepository()
    repo2 = InMemoryKnowledgeGapRepository()
    service1 = KnowledgeGapService(repo1)
    service2 = KnowledgeGapService(repo2)

    await service1.record_gap("Q1", sacco_id="demo_sacco", fallback_reason="knowledge_gap")
    await service2.record_gap("Q2", sacco_id="demo_sacco", fallback_reason="knowledge_gap")

    gaps1 = await service1.get_gaps_by_sacco("demo_sacco")
    gaps2 = await service2.get_gaps_by_sacco("demo_sacco")

    assert len(gaps1) == 1
    assert len(gaps2) == 1
    assert gaps1[0].query != gaps2[0].query
