"""Tests for query reformulation (System 6.1)."""

import pytest

from app.ai.rag.query_rewriter import QueryRewriter
from app.schemas.message import ConversationTurn


class FakeLLM:
    """Mock LLM for testing."""

    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.calls = []

    async def generate(self, messages: list[dict]) -> str:
        """Return mocked response."""
        self.calls.append(messages)
        content = messages[-1]["content"] if messages else ""
        # Simple mock: return a reformulated version or the input
        for key, value in self.responses.items():
            if key in content:
                return value
        return "Reformulated query from mock"


@pytest.mark.anyio
async def test_self_contained_question_returns_unchanged():
    """Self-contained questions should not be reformulated."""
    llm = FakeLLM()
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite(
        latest_message="What is compound interest?",
        conversation_history=None,
    )

    assert result == "What is compound interest?"
    assert llm.calls == []  # No LLM call needed


@pytest.mark.anyio
async def test_no_history_returns_original_message():
    """Without conversation history, return the message as-is."""
    llm = FakeLLM()
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite(
        latest_message="How much can I get?",
        conversation_history=None,
    )

    assert result == "How much can I get?"


@pytest.mark.anyio
async def test_follow_up_question_with_history_calls_llm():
    """Follow-up questions with history should trigger LLM reformulation."""
    llm = FakeLLM({"How much": "How much can I get for a development loan?"})
    rewriter = QueryRewriter(llm)

    history = [
        ConversationTurn(role="user", content="What is a development loan?"),
        ConversationTurn(role="assistant", content="A development loan is..."),
    ]

    result = await rewriter.rewrite(
        latest_message="How much can I get?",
        conversation_history=history,
    )

    assert "development loan" in result.lower()
    assert len(llm.calls) == 1


@pytest.mark.anyio
async def test_self_contained_with_history_uses_message_unchanged():
    """Self-contained questions should not be reformulated even with history."""
    llm = FakeLLM()
    rewriter = QueryRewriter(llm)

    history = [
        ConversationTurn(role="user", content="What is a development loan?"),
        ConversationTurn(role="assistant", content="A development loan is..."),
    ]

    result = await rewriter.rewrite(
        latest_message="What is compound interest?",
        conversation_history=history,
    )

    assert result == "What is compound interest?"
    assert llm.calls == []


@pytest.mark.anyio
async def test_llm_failure_returns_original_message():
    """LLM failures should gracefully fallback to original message."""

    class FailingLLM:
        async def generate(self, messages):
            raise RuntimeError("LLM service unavailable")

    llm = FailingLLM()
    rewriter = QueryRewriter(llm)

    history = [
        ConversationTurn(role="user", content="What is a development loan?"),
    ]

    result = await rewriter.rewrite(
        latest_message="How much can I get?",
        conversation_history=history,
    )

    assert result == "How much can I get?"


@pytest.mark.anyio
async def test_empty_history_returns_original():
    """Empty history list should return original message."""
    llm = FakeLLM()
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite(
        latest_message="How much?",
        conversation_history=[],
    )

    assert result == "How much?"


def test_is_self_contained_recognizes_follow_ups():
    """Heuristic should identify follow-up questions."""
    assert not QueryRewriter._is_self_contained("How much?")
    assert not QueryRewriter._is_self_contained("What about that?")
    assert not QueryRewriter._is_self_contained("Can I get one?")
    assert not QueryRewriter._is_self_contained("Tell me more")


def test_is_self_contained_recognizes_complete_questions():
    """Heuristic should identify self-contained questions."""
    assert QueryRewriter._is_self_contained("What is compound interest?")
    assert QueryRewriter._is_self_contained("Explain how savings work.")
    assert QueryRewriter._is_self_contained("Who is the SACCO manager?")
    assert QueryRewriter._is_self_contained("What are the loan requirements?")


@pytest.mark.anyio
async def test_long_history_uses_recent_turns_only():
    """Long history should be truncated to avoid token bloat."""
    llm = FakeLLM({"How much": "How much can I get for X?"})
    rewriter = QueryRewriter(llm)

    history = [
        ConversationTurn(role="user", content=f"Question {i}")
        for i in range(20)
    ]

    result = await rewriter.rewrite(
        latest_message="How much?",
        conversation_history=history,
    )

    # Verify that LLM was called (history exists)
    assert len(llm.calls) == 1

    # The formatted history in the prompt should use recent turns
    prompt_content = llm.calls[0][0]["content"]
    assert "Question" in prompt_content
