import pytest
from fastapi.testclient import TestClient

from app.ai.rag.context import build_context
from app.ai.rag.models import RAGResult
from app.ai.rag.prompts import grounded_answer_messages
from app.api.routes import rag as rag_route
from app.main import app
from app.services.rag_answer_service import NO_CONTEXT_ANSWER, RAGAnswerService


class FakePipeline:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


class FakeLLM:
    def __init__(self, answer="Grounded demo answer"):
        self.answer = answer
        self.calls = []

    async def generate(self, messages):
        self.calls.append(messages)
        return self.answer


def result(document_id="test_loan_documents", title="Test Demo: Loan Documents"):
    return RAGResult(
        document_id=document_id,
        chunk_id=f"{document_id}_chunk_00",
        title=title,
        content="A synthetic document lists illustrative application information.",
        score=0.86,
        source="synthetic test data",
        sacco_id="demo_sacco",
        language="en",
        topic="loans",
        content_type="sacco_policy",
        metadata={"is_test_data": True},
    )


@pytest.mark.anyio
async def test_relevant_context_generates_grounded_answer_with_sources():
    pipeline = FakePipeline([result()])
    llm = FakeLLM("The documents are listed in the synthetic demo context.")
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        "What documents do I need to apply for a development loan?",
        sacco_id="demo_sacco",
        language="en",
        top_k=5,
    )

    assert response.grounded is True
    assert response.no_context is False
    assert response.sources[0].document_id == "test_loan_documents"
    assert response.sources[0].score == 0.86
    assert len(llm.calls) == 1
    assert "Synthetic/demo data: True" in llm.calls[0][0]["content"]
    assert "A synthetic document lists" in llm.calls[0][0]["content"]
    assert pipeline.calls[0]["sacco_id"] == "demo_sacco"


@pytest.mark.anyio
async def test_no_context_returns_fallback_without_calling_nvidia():
    pipeline = FakePipeline([])
    llm = FakeLLM()
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer("What is today's USD/KES exchange rate?")

    assert response.answer == NO_CONTEXT_ANSWER
    assert response.grounded is False
    assert response.no_context is True
    assert response.sources == []
    assert llm.calls == []


@pytest.mark.anyio
async def test_source_integrity_is_preserved():
    source = result("test_shares_vs_deposits", "Test Demo: Shares and Deposits")
    service = RAGAnswerService(FakePipeline([source]), FakeLLM())

    response = await service.answer("What is the difference between shares and savings?")

    assert response.sources[0].model_dump() == {
        "document_id": "test_shares_vs_deposits",
        "chunk_id": "test_shares_vs_deposits_chunk_00",
        "title": "Test Demo: Shares and Deposits",
        "source": "synthetic test data",
        "score": 0.86,
    }


@pytest.mark.anyio
async def test_swahili_filter_with_english_only_context_returns_no_context():
    pipeline = FakePipeline([])
    llm = FakeLLM()
    service = RAGAnswerService(pipeline, llm)

    response = await service.answer(
        "Nieleze kuhusu riba ya jumla", language="sw", sacco_id="demo_sacco"
    )

    assert response.no_context is True
    assert llm.calls == []


def test_context_and_prompt_contain_grounding_rules():
    context = build_context([result()])
    messages = grounded_answer_messages("Explain the result", context)
    system_prompt = messages[0]["content"]

    assert "using only the retrieved context" in system_prompt
    assert "Do not invent facts" in system_prompt
    assert "not official SACCO policy" in system_prompt
    assert "not found in the SACCO knowledge base" in system_prompt
    assert "Synthetic/demo data: True" in context


def test_rag_answer_endpoint_uses_service(monkeypatch):
    pipeline = FakePipeline([result()])
    llm = FakeLLM("A grounded answer")
    monkeypatch.setattr(rag_route, "_answer_service", RAGAnswerService(pipeline, llm))

    response = TestClient(app).post(
        "/rag/answer",
        json={
            "query": "What documents do I need for a loan?",
            "sacco_id": "demo_sacco",
            "language": "en",
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "A grounded answer"
    assert body["grounded"] is True
    assert body["sources"][0]["document_id"] == "test_loan_documents"


@pytest.mark.anyio
async def test_nvidia_failure_is_propagated_for_route_handling():
    class FailingLLM:
        async def generate(self, messages):
            raise RuntimeError("NVIDIA request timed out")

    service = RAGAnswerService(FakePipeline([result()]), FailingLLM())

    response = await service.answer("Explain compound interest simply.")

    assert response.grounded is False
    assert response.fallback_category == "provider_failure"
    assert "temporarily unable" in response.answer.lower()
