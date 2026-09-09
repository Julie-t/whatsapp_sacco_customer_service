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


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("I want to make a withdrawal immediately.", "human_escalation"),
        ("Tell me about loans", "clarification"),
        ("What percentage of my money should go to emergency savings?", "guardrail"),
        ("How do I check my account balance?", "human_escalation"),
        ("Akaunti yangu imefungwa kwa nini?", "human_escalation"),
        ("How do I calculate my loan repayment?", None),
    ],
)
def test_deterministic_route_evaluation_failures(question, expected):
    triage = deterministic_route(question)
    assert _routed_behavior_for_test(triage, question) == expected


def _routed_behavior_for_test(triage, question):
    from evaluations.runner import _routed_behavior

    return _routed_behavior(triage, question)


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


# ---------------------------------------------------------------------------
# Grounding verifier: non-factual claim exemptions & paraphrase tolerance
# ---------------------------------------------------------------------------

class TestGroundingNonFactualExemptions:
    """Verify that introductory framing, safe disclaimers, and meta-commentary
    are exempt from grounding checks to avoid false-positive hallucination flags."""

    def _verify(self, answer, evidence, expected_claims=None):
        from evaluations.grounding import GroundingVerifier
        return GroundingVerifier().verify(answer, evidence, expected_claims)

    def test_introductory_framing_exempt(self):
        evidence = "A sample loan application may require an identification document, recent income evidence, a completed application form, and details of proposed guarantors."
        answer = "For a loan application you'll typically need: an identification document, recent income evidence, a completed application form, and details of proposed guarantors."
        result = self._verify(answer, evidence)
        assert result.supported, f"Introductory framing should be exempt, but got unsupported: {result.unsupported_claims}"

    def test_safe_disclaimer_exempt(self):
        evidence = "Illustrative daily transaction limit is KES 50,000 for digital channels."
        answer = "The daily limit is KES 50,000. Please check with your SACCO staff for the actual limit that applies to your account."
        result = self._verify(answer, evidence)
        # The disclaimer sentence should not cause a failure
        assert "Please check with your SACCO staff" not in result.unsupported_claims

    def test_meta_commentary_exempt(self):
        evidence = "Illustrative SACCO loan products include development loans for productive projects."
        answer = "A development loan is a type of SACCO loan intended to fund productive projects. This description comes from the SACCO's illustrative policy."
        result = self._verify(answer, evidence)
        assert "This description comes from the SACCO's illustrative policy." not in result.unsupported_claims

    def test_contact_staff_confirmation_exempt(self):
        evidence = "A sample loan application may require an identification document."
        answer = "You need an identification document. If you need confirmation of the exact requirements for your specific loan type, please contact SACCO staff."
        result = self._verify(answer, evidence)
        assert "please contact SACCO staff" not in " ".join(result.unsupported_claims).lower()

    def test_paraphrased_content_accepted_at_lower_threshold(self):
        """Synonym usage should not be flagged: 'earned in earlier periods' vs 'accumulated from previous periods'."""
        evidence = "Compound interest is interest earned on both principal and accumulated interest from previous periods."
        answer = "Compound interest is interest calculated on both the original amount and on interest that has already been earned in earlier periods."
        result = self._verify(answer, evidence)
        assert result.supported, f"Paraphrased content should be accepted, but got unsupported: {result.unsupported_claims}"

    def test_genuine_hallucination_still_caught(self):
        """Ensure real unsupported claims are still flagged despite the new exemptions."""
        evidence = "Loan applicants need an identification document and a completed application form."
        answer = "Applicants need an identification document and a 5 percent processing fee."
        result = self._verify(answer, evidence)
        assert not result.supported
        assert any("5 percent" in claim.lower() or "fee" in claim.lower() for claim in result.unsupported_claims)

    def test_framing_with_numbers_not_exempt(self):
        """Framing-like sentences containing numbers should still be grounded."""
        evidence = "Loan applicants need two guarantors."
        answer = "You'll typically need 3 guarantors for a loan application."
        result = self._verify(answer, evidence)
        # This should NOT be exempt because it contains a number claim
        assert not result.supported
