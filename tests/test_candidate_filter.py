"""Unit tests for CandidateFilter and OperationRegistry."""

from app.ai.candidate_filter import CandidateFilter
from app.ai.operation_registry import DEFAULT_OPERATIONS, OperationRegistry
from app.ai.routing_types import OperationType, WorkflowType
from app.services.conversations.conversation_context import ConversationContext


def _make_context(
    query: str,
    has_active_goal: bool = False,
    has_auth_session: bool = False,
) -> ConversationContext:
    return ConversationContext(
        raw_message=query,
        effective_query=query,
        conversation_key="whatsapp:+254700000001",
        language="en",
        previous_turns=[],
        context_summary=None,
        member_profile=None,
        has_active_goal=has_active_goal,
        active_goal=None,
        has_auth_session=has_auth_session,
    )


def test_operation_registry_retrieval():
    registry = OperationRegistry(DEFAULT_OPERATIONS)
    balance_op = registry.get(OperationType.MEMBER_BALANCE.value)
    assert balance_op is not None
    assert balance_op.workflow == WorkflowType.MEMBER_DATA
    assert balance_op.requires_auth is True

    prompt_str = registry.format_candidates_for_prompt([balance_op])
    assert "member.balance" in prompt_str
    assert "Check authenticated member's personal savings" in prompt_str


def test_candidate_filter_with_active_goal():
    cf = CandidateFilter()
    context = _make_context("Which is better saving 10k or 15k?", has_active_goal=True)
    candidates = cf.select_candidates(context)
    candidate_ids = {op.id for op in candidates}

    assert OperationType.GOAL_SCENARIO.value in candidate_ids
    assert OperationType.CLARIFY_DISAMBIGUATE.value in candidate_ids


def test_candidate_filter_with_loan_payment():
    cf = CandidateFilter()
    context = _make_context("When is my next loan payment due?")
    candidates = cf.select_candidates(context)
    candidate_ids = {op.id for op in candidates}

    assert OperationType.MEMBER_NEXT_PAYMENT.value in candidate_ids
    assert OperationType.CLARIFY_DISAMBIGUATE.value in candidate_ids


def test_candidate_filter_always_includes_clarification():
    cf = CandidateFilter()
    context = _make_context("How much can I get?")
    candidates = cf.select_candidates(context)
    candidate_ids = {op.id for op in candidates}

    assert OperationType.CLARIFY_DISAMBIGUATE.value in candidate_ids
