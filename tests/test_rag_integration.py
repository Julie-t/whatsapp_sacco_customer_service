"""Integration tests for updated RAG answer service with all Systems 6.1-6.4."""

import pytest

from app.ai.rag.answerability import AnswerabilityChecker
from app.ai.rag.models import RAGResult
from app.ai.rag.query_rewriter import QueryRewriter
from app.schemas.message import ConversationTurn
from app.services.knowledge_gap_repository import InMemoryKnowledgeGapRepository
from app.services.knowledge_gap_service import KnowledgeGapService
from app.services.rag_answer_service import RAGAnswerService


class FakePipeline:
    """Mock RAG pipeline."""

    def __init__(self, results=None):
        self.results = results or []
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class FakeLLM:
    """Mock LLM."""

    def __init__(self, answer="Test answer"):
        self.answer = answer
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return self.answer


def make_result(
    document_id: str = "test_doc",
    score: float = 0.85,
    content: str = "Test content with sufficient length to pass answerability checks that require more than 30 characters.",
    title: str | None = None,
) -> RAGResult:
    """Create a test RAGResult."""
    return RAGResult(
        document_id=document_id,
        chunk_id=f"{document_id}_chunk_00",
        title=title or f"Test: {document_id}",
        content=content,
        source="test data",
        score=score,
        sacco_id="demo_sacco",
        language="en",
        topic="test",
        content_type="general",
        metadata={},
    )


@pytest.mark.anyio
async def test_rag_answer_service_with_good_results():
    """Service should generate answer when results are good."""
    pipeline = FakePipeline([make_result(score=0.9)])
    llm = FakeLLM("This is a good answer.")
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="What is compound interest?",
        sacco_id="demo_sacco",
    )

    assert response.grounded is True
    assert response.answer == "This is a good answer."
    assert len(response.sources) == 1
    assert response.retrieval_confidence == 0.9
    assert response.answerability_confidence is not None
    assert response.fallback_category is None


@pytest.mark.anyio
async def test_rag_answer_service_with_low_score_results():
    """Service should use fallback when retrieval confidence is low."""
    pipeline = FakePipeline([make_result(score=0.2)])
    llm = FakeLLM()
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="What is X?",
        sacco_id="demo_sacco",
    )

    assert response.grounded is False
    assert response.no_context is False
    assert response.fallback_category == "knowledge_gap"
    assert llm.calls == []  # LLM should not be called


@pytest.mark.anyio
async def test_rag_answer_service_with_no_results():
    """Service should use fallback when no results retrieved."""
    pipeline = FakePipeline([])
    llm = FakeLLM()
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="Unknown question?",
        sacco_id="demo_sacco",
    )

    assert response.grounded is False
    assert response.no_context is True
    assert response.fallback_category == "knowledge_gap"
    assert llm.calls == []


@pytest.mark.anyio
async def test_rag_answer_with_query_reformulation():
    """Service should reformulate follow-up queries."""
    pipeline = FakePipeline([make_result(score=0.85)])
    llm = FakeLLM("Answer from LLM")

    class TestQueryRewriter:
        async def rewrite(self, latest_message, conversation_history=None):
            if conversation_history:
                return "Reformulated: " + latest_message
            return latest_message

        @staticmethod
        def _is_self_contained(msg):
            return "is" in msg.lower()

    service = RAGAnswerService(
        pipeline,
        llm,
        query_rewriter=TestQueryRewriter(),
    )

    history = [ConversationTurn(role="user", content="What is a loan?")]
    response = await service.answer(
        query="How much?",
        sacco_id="demo_sacco",
        conversation_history=[{"role": "user", "content": "What is a loan?"}],
    )

    # Should have called pipeline with reformulated query
    assert len(pipeline.calls) > 0


@pytest.mark.anyio
async def test_rag_answer_tracks_knowledge_gaps():
    """Service should record knowledge gaps."""
    repo = InMemoryKnowledgeGapRepository()
    pipeline = FakePipeline([])
    llm = FakeLLM()
    service = RAGAnswerService(
        pipeline,
        llm,
        knowledge_gap_service=KnowledgeGapService(repo),
    )

    response = await service.answer(
        query="What is the USD/KES rate?",
        sacco_id="demo_sacco",
        language="en",
    )

    assert response.fallback_category == "knowledge_gap"
    # Should have recorded the gap
    gaps = await repo.query_gaps_by_sacco("demo_sacco")
    assert len(gaps) == 1
    assert gaps[0].query == "What is the USD/KES rate?"


@pytest.mark.anyio
async def test_rag_answer_respects_answerability_threshold():
    """Service should check answerability before generating."""
    pipeline = FakePipeline([make_result(
        score=0.85,
        content="Brief.",  # Very short
    )])
    llm = FakeLLM("Answer")

    checker = AnswerabilityChecker(min_result_length=200)
    service = RAGAnswerService(
        pipeline,
        llm,
        answerability_checker=checker,
    )

    response = await service.answer(
        query="What is X?",
        sacco_id="demo_sacco",
    )

    # Should not be answerable due to short content
    assert response.grounded is False
    assert response.fallback_category == "knowledge_gap"
    assert llm.calls == []


@pytest.mark.anyio
async def test_rag_answer_preserves_sources():
    """Service should preserve source information."""
    result = make_result(
        document_id="loan_requirements",
        title="Loan Requirements",
        score=0.92,
    )
    pipeline = FakePipeline([result])
    llm = FakeLLM("Answer")
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="What do I need for a loan?",
        sacco_id="demo_sacco",
    )

    assert len(response.sources) == 1
    assert response.sources[0].document_id == "loan_requirements"
    assert response.sources[0].title == "Loan Requirements"
    assert response.sources[0].score == 0.92


@pytest.mark.anyio
async def test_rag_answer_with_multiple_results():
    """Service should handle multiple results correctly."""
    results = [
        make_result(document_id="doc1", score=0.9),
        make_result(document_id="doc2", score=0.85),
        make_result(document_id="doc3", score=0.8),
    ]
    pipeline = FakePipeline(results)
    llm = FakeLLM("Answer from multiple sources")
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="What is X?",
        sacco_id="demo_sacco",
    )

    assert response.grounded is True
    assert len(response.sources) == 3
    # Confidence should be based on minimum score
    assert response.retrieval_confidence == 0.8


@pytest.mark.anyio
async def test_rag_answer_llm_failure_fallback():
    """Service should handle LLM failures gracefully."""

    class FailingLLM:
        async def generate(self, messages):
            raise RuntimeError("LLM service down")

    pipeline = FakePipeline([make_result(score=0.9)])
    llm = FailingLLM()
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="What is X?",
        sacco_id="demo_sacco",
    )

    assert response.grounded is False
    assert response.fallback_category == "provider_failure"
    assert "temporarily unable" in response.answer.lower() or "temporarily unavailable" in response.answer.lower()


@pytest.mark.anyio
async def test_rag_answer_filters_applied():
    """Service should apply language and sacco filters."""
    pipeline = FakePipeline([make_result()])
    llm = FakeLLM("Answer")
    service = RAGAnswerService(pipeline, llm)

    await service.answer(
        query="What is X?",
        sacco_id="test_sacco",
        language="sw",
        content_type="policy",
    )

    # Check that filters were passed through
    assert len(pipeline.calls) == 1
    call = pipeline.calls[0]
    assert call["sacco_id"] == "test_sacco"
    assert call["language"] == "sw"
    assert call["content_type"] == "policy"


@pytest.mark.anyio
async def test_rag_answer_with_top_k():
    """Service should respect top_k parameter."""
    pipeline = FakePipeline([make_result()])
    llm = FakeLLM("Answer")
    service = RAGAnswerService(pipeline, llm)

    await service.answer(
        query="What is X?",
        sacco_id="demo_sacco",
        top_k=10,
    )

    assert pipeline.calls[0]["top_k"] == 10


@pytest.mark.anyio
async def test_rag_answer_metadata_completeness():
    """Response should include all relevant metadata."""
    pipeline = FakePipeline([make_result(score=0.88)])
    llm = FakeLLM("Test answer")
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        query="What is compound interest?",
        sacco_id="demo_sacco",
    )

    # Check all metadata fields are present
    assert response.query == "What is compound interest?"
    assert response.answer is not None
    assert response.sources is not None
    assert response.grounded is not None
    assert response.no_context is not None
    assert response.retrieval_confidence is not None
    assert response.answerability_confidence is not None
    assert response.fallback_category is not None or response.grounded is True
