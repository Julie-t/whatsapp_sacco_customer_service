"""Unit tests for goal extractor heuristics and parsing."""

import pytest

from app.models.goal import GoalType
from app.services.goals.goal_extractor import GoalExtractor, _parse_amount, _parse_months


def test_parse_amount():
    assert _parse_amount("I want to save 300k for university") == 300000.0
    assert _parse_amount("Target is KSh 240,000") == 240000.0
    assert _parse_amount("saving 50000 shillings") == 50000.0
    assert _parse_amount("no numbers here") is None


def test_parse_months():
    assert _parse_months("in 2 years") == 24
    assert _parse_months("in 18 months") == 18
    assert _parse_months("within 1 year") == 12
    assert _parse_months("miaka 3") == 36
    assert _parse_months("miezi 6") == 6
    assert _parse_months("tomorrow") is None


def test_extract_heuristic_complete_goal():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("I want to save KSh 240,000 for school fees in 18 months")
    assert res.target_amount == 240000.0
    assert res.timeline_months == 18
    assert res.goal_type == GoalType.EDUCATION
    assert res.needs_clarification is False
    assert res.target_date is not None


def test_extract_heuristic_missing_amount():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("I want to save for my daughter's university in 2 years")
    assert res.needs_clarification is True
    assert "target_amount" in res.missing_fields
    assert res.timeline_months == 24


def test_extract_heuristic_missing_timeline():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("I want to save 300,000 for an emergency fund")
    assert res.needs_clarification is True
    assert "target_date" in res.missing_fields
    assert res.target_amount == 300000.0
    assert res.goal_type == GoalType.EMERGENCY_FUND


def test_extract_heuristic_scenario():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("What if I save 15k instead of 10k?")
    assert res.is_scenario_query is True
    assert res.proposed_scenario_amount == 15000.0


def test_extract_heuristic_progress_inquiry():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("What is my school fees goal progress?")
    assert res.is_progress_inquiry is True


def test_parse_amount_raise():
    assert _parse_amount("I want to raise KSh 300,000 for my shop by next year") == 300000.0
    assert _parse_amount("I want to raise 300k for my shop next year") == 300000.0
    assert _parse_amount("raise 50000") == 50000.0
    assert _parse_amount("changa 20000") == 20000.0


def test_parse_months_relative():
    assert _parse_months("by next year") == 12
    assert _parse_months("next year") == 12
    assert _parse_months("mwaka ujao") == 12
    assert _parse_months("end of year") >= 1
    assert _parse_months("half a year") == 6
    assert _parse_months("in a month") == 1


def test_extract_heuristic_raise_business_next_year():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("I want to raise KSh 300,000 for my shop by next year.")
    assert res.target_amount == 300000.0
    assert res.timeline_months == 12
    assert res.goal_type == GoalType.BUSINESS
    assert res.name == "Business Growth"
    assert res.needs_clarification is False
    assert res.target_date is not None


def test_extract_heuristic_advisory_not_progress():
    extractor = GoalExtractor()
    res = extractor.extract_heuristic("what savings account is best for my goal")
    assert res.is_progress_inquiry is False
    assert res.is_scenario_query is False

    res2 = extractor.extract_heuristic("are there stocks or shares I can buy to supplement this goal")
    assert res2.is_progress_inquiry is False
    assert res2.is_scenario_query is False

