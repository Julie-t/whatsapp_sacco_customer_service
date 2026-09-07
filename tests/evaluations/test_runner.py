import asyncio

import pytest

from app.ai.rag.models import RAGResult
from app.services.rag_answer_service import RAGAnswerService
from evaluations.runner import EvaluationRunner, build_report, deterministic_route
from evaluations.models import EvaluationCase, EvaluationResult, MetricResult


class FakePipeline:
    def __init__(self, results):
        self.results = results

    def search(self, **kwargs):
        return self.results


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer

    async def generate(self, messages):
        return self.answer


def result(content: str, score: float = 0.9) -> RAGResult:
    return RAGResult(
        document_id="loan_requirements",
        chunk_id="loan_requirements_0",
        title="Loan requirements",
        content=content,
        score=score,
        source="test",
        sacco_id="demo_sacco",
        language="en",
        topic="loans",
        content_type="policy",
    )


@pytest.mark.anyio
async def test_runner_flags_unsupported_generated_claim():
    evidence = "Loan applicants need an identification document and a completed application form."
    case = EvaluationCase(
        id="hallucination",
        question="What documents do I need for a loan?",
        expected_behavior="answer",
        expected_source="loan_requirements",
        expected_claims=["Applicants need an identification document and a 5 percent fee."],
    )
    service = RAGAnswerService(FakePipeline([result(evidence)]), FakeLLM("Applicants need an identification document and a 5 percent fee."))
    evaluated = await EvaluationRunner(service.pipeline, service).evaluate_case(case)

    assert evaluated.passed is False
    assert evaluated.failure_type == "hallucination"
    assert evaluated.groundedness.details["unsupported_claims"]


@pytest.mark.anyio
async def test_runner_accepts_grounded_generated_claim():
    evidence = "Loan applicants need an identification document and a completed application form."
    case = EvaluationCase(
        id="grounded",
        question="What documents do I need for a loan?",
        expected_behavior="answer",
        expected_source="loan_requirements",
        expected_claims=["Applicants need an identification document and a completed application form."],
    )
    service = RAGAnswerService(FakePipeline([result(evidence)]), FakeLLM(evidence))
    evaluated = await EvaluationRunner(service.pipeline, service).evaluate_case(case)

    assert evaluated.passed is True
    assert evaluated.groundedness.passed is True


@pytest.mark.anyio
async def test_runner_applies_evaluation_pacing(monkeypatch, tmp_path):
    service = RAGAnswerService(
        FakePipeline([result("Loan applicants need identification documents.")]),
        FakeLLM("Grounded answer"),
    )
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    runner = EvaluationRunner(service.pipeline, service, request_delay_seconds=2.5)

    dataset = tmp_path / "cases.json"
    dataset.write_text(
        '{"cases": ['
        '{"id":"paced","question":"What documents do I need for a loan?",'
        '"expected_behavior":"answer","expected_source":"loan_requirements"},'
        '{"id":"paced-2","question":"What documents do I need for a loan?",'
        '"expected_behavior":"answer","expected_source":"loan_requirements"}'
        ']}',
        encoding="utf-8",
    )

    await runner.evaluate(str(dataset))

    assert delays == [2.5]


def test_report_separates_provider_failures_from_generated_answers():
    generated = EvaluationResult(
        case_id="generated",
        question="What is a loan?",
        expected_behavior="answer",
        actual_behavior="answer",
        groundedness=MetricResult(passed=True, score=1.0, reason="ok"),
        relevance=MetricResult(passed=True, score=1.0, reason="ok"),
        language=MetricResult(passed=True, score=1.0, reason="ok"),
    )
    rate_limited = EvaluationResult(
        case_id="rate-limited",
        question="What is a loan?",
        expected_behavior="answer",
        actual_behavior="provider_failure",
        provider_failure_type="rate_limit",
    )

    report = build_report(
        [generated, rate_limited],
        [
            EvaluationCase(
                id="generated",
                question="What is a loan?",
                expected_behavior="answer",
            ),
            EvaluationCase(
                id="rate-limited",
                question="What is a loan?",
                expected_behavior="answer",
            ),
        ],
    )

    assert report["execution_breakdown"]["generated_answers"] == 1
    assert report["provider"]["rate_limit_failures"] == 1
    assert report["generated_answers"]["groundedness"] == 1.0


@pytest.mark.parametrize(
    ("question", "member_data", "human"),
    [
        ("I don't recognize a transaction.", False, True),
        ("I want to complain about a charge.", False, True),
        ("I want to speak to someone.", False, True),
        ("What is my loan balance?", True, False),
        ("What is compound interest?", False, False),
        ("Akaunti yangu imefungwa kwa nini?", True, False),
        ("How long have I been a member?", True, False),
    ],
)
def test_deterministic_route_sensitive_cases(question, member_data, human):
    result = deterministic_route(question)

    assert result.needs_member_data is member_data
    assert result.likely_needs_human is human


def test_report_excludes_routed_fallbacks_from_answerability():
    routed = EvaluationResult(
        case_id="route",
        question="I want to speak to someone.",
        expected_behavior="human_escalation",
        actual_behavior="human_escalation",
        fallback=MetricResult(passed=True, score=1.0, reason="ok"),
    )
    generated = EvaluationResult(
        case_id="answer",
        question="What is a loan?",
        expected_behavior="answer",
        actual_behavior="answer",
        answerability={"answerable": True},
        fallback=MetricResult(passed=True, score=1.0, reason="ok"),
        groundedness=MetricResult(passed=True, score=1.0, reason="ok"),
        relevance=MetricResult(passed=True, score=1.0, reason="ok"),
        language=MetricResult(passed=True, score=1.0, reason="ok"),
    )

    report = build_report(
        [routed, generated],
        [
            EvaluationCase(id="route", question=routed.question, expected_behavior="human_escalation"),
            EvaluationCase(id="answer", question=generated.question, expected_behavior="answer"),
        ],
    )

    assert report["answerability"]["correct"] == 1
    assert report["answerability"]["total"] == 1


def test_report_includes_retrieval_debug_fields():
    evaluated = EvaluationResult(
        case_id="debug",
        question="What is a loan?",
        expected_behavior="answer",
        retrieval={
            "top_retrieved": ["loan"],
            "scores": [0.9],
            "recall_at_5": True,
            "expected_source_rank": 1,
        },
    )
    report = build_report(
        [evaluated],
        [EvaluationCase(id="debug", question=evaluated.question, expected_behavior="answer", expected_source="loan")],
    )

    assert "error_analysis" in report["retrieval"]
