"""Tests for PersonalizationHistoryRepository (InMemory)."""

import pytest

from app.database.in_memory_personalization_repository import InMemoryPersonalizationHistoryRepository


@pytest.fixture
def repo():
    return InMemoryPersonalizationHistoryRepository()


def test_record_topic(repo):
    record = repo.record_topic(
        member_id="member_001",
        topic="compound_interest",
        summary="Explained compound interest mechanics for emergency savings.",
        goal_id="goal_001",
    )
    assert record.id == 1
    assert record.member_id == "member_001"
    assert record.topic == "compound_interest"
    assert record.goal_id == "goal_001"
    assert record.created_at is not None


def test_get_recent_topics(repo):
    repo.record_topic("member_001", "budgeting")
    repo.record_topic("member_001", "compound_interest")
    repo.record_topic("member_001", "budgeting")  # duplicate topic
    repo.record_topic("member_002", "emergency_fund")

    recent_m1 = repo.get_recent_topics("member_001", limit=5)
    assert "budgeting" in recent_m1
    assert "compound_interest" in recent_m1
    assert len(recent_m1) == 2  # deduplicated

    recent_m2 = repo.get_recent_topics("member_002", limit=5)
    assert recent_m2 == ["emergency_fund"]


def test_get_history_chronological(repo):
    repo.record_topic("member_001", "budgeting", "First lesson")
    repo.record_topic("member_001", "compound_interest", "Second lesson")

    history = repo.get_history("member_001")
    assert len(history) == 2
    # most recent first
    assert history[0].topic == "compound_interest"
    assert history[1].topic == "budgeting"
