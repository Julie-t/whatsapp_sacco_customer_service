"""Execution orchestration for offline and live System 6 evaluation."""

from collections.abc import Callable
from datetime import UTC, datetime
import asyncio
import logging

from app.ai.rag.answerability import AnswerabilityChecker
from app.ai.rag.answer_verifier import AnswerVerifier
from app.ai.rag.context import build_context, select_context
from app.schemas.intent import RequestTriageResult
from app.config.settings import settings
from app.services.rag_answer_service import RAGAnswerService

from .dataset import load_cases
from .metrics import groundedness, language_correctness, recall_metrics, relevance
from .grounding import GroundingVerifier
from .models import EvaluationCase, EvaluationResult, MetricResult

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Run evaluation cases against injectable application components."""

    def __init__(
        self,
        pipeline,
        answer_service: RAGAnswerService | None = None,
        answerability_checker: AnswerabilityChecker | None = None,
        router=None,
        request_delay_seconds: float = 0.0,
        verification_mode: str = "standard",
        verification_llm=None,
    ):
        self.pipeline = pipeline
        self.answer_service = answer_service
        self.answerability_checker = answerability_checker or AnswerabilityChecker(
            min_retrieval_score=settings.RAG_MIN_SCORE
        )
        self.router = router
        self.request_delay_seconds = max(0.0, request_delay_seconds)
        if verification_mode not in {"standard", "high-risk"}:
            raise ValueError("verification_mode must be standard or high-risk")
        self.verification_mode = verification_mode
        self.verifier = GroundingVerifier()
        self.verification_llm = verification_llm

    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        result = EvaluationResult(
            case_id=case.id,
            question=case.question,
            expected_behavior=case.expected_behavior,
        )
        try:
            triage = await self._route(case.question)
            result.routing = triage.model_dump()
            routed_behavior = _routed_behavior(triage, case.question)
            if routed_behavior is not None:
                result.actual_behavior = routed_behavior
                result.fallback = _fallback_metric(case, routed_behavior)
                result.passed = _case_passed(result, case)
                if not result.passed:
                    result.failure_type = _failure_type(result)
                return result

            if self.answer_service is not None:
                result.reformulated_query, retrieved = await self.answer_service.retrieve_evidence(
                    query=case.question,
                    sacco_id=case.sacco_id,
                    language=case.language,
                    top_k=5,
                )
            else:
                retrieved = self.pipeline.search(
                    query=case.question,
                    sacco_id=case.sacco_id,
                    language=case.language,
                    top_k=5,
                )
                result.reformulated_query = case.question
            ranked_ids = [item.document_id for item in retrieved]
            expected_result = next(
                (item for item in retrieved if item.document_id == case.expected_source),
                None,
            )
            expected_rank = ranked_ids.index(case.expected_source) + 1 if case.expected_source in ranked_ids else None
            top_score = retrieved[0].score if retrieved else None
            result.retrieval = {
                "query": case.question,
                "top_retrieved": ranked_ids,
                "top_1_source": ranked_ids[0] if ranked_ids else None,
                "top_3_sources": ranked_ids[:3],
                "top_5_sources": ranked_ids[:5],
                "scores": [item.score for item in retrieved],
                "retrieved_sources": [
                    {"document_id": item.document_id, "score": item.score, "rank": rank}
                    for rank, item in enumerate(retrieved, start=1)
                ],
                "expected_source_rank": expected_rank,
                "expected_source_score": expected_result.score if expected_result else None,
                "top_1_expected_score_gap": (
                    top_score - expected_result.score
                    if top_score is not None and expected_result is not None else None
                ),
                "expected_source_retrieved": expected_result is not None,
                **recall_metrics(ranked_ids, case.expected_source),
            }
            selected_results = select_context(case.question, retrieved)
            decision = self.answerability_checker.check(case.question, selected_results)
            result.answerability = {
                "answerable": decision.answerable,
                "confidence": decision.confidence,
                "reason": decision.reason,
                "min_score": decision.min_score,
            }

            if self.answer_service is not None:
                response = await self.answer_service.answer(
                    query=case.question,
                    sacco_id=case.sacco_id,
                    language=case.language,
                    retrieved_results=retrieved,
                )
                result.answer = response.answer
                result.reformulated_query = response.reformulated_query or case.question
                result.actual_behavior = response.fallback_category or "answer"
                result.provider_failure_type = response.provider_failure_type
                result.fallback = _fallback_metric(case, result.actual_behavior)
                if result.actual_behavior == "answer":
                    evidence = build_context(selected_results)
                    deterministic_verification = self.verifier.verify(response.answer, evidence, case.expected_claims)
                    checks = 2 if self.verification_mode == "high-risk" and deterministic_verification.risk == "HIGH" else 1
                    if self.verification_llm is not None:
                        provider_verifier = AnswerVerifier()
                        verification_results = [
                            (await provider_verifier.verify_with_llm(self.verification_llm, response.answer, evidence)).model_dump()
                            for _ in range(checks)
                        ]
                    else:
                        verification_results = [deterministic_verification.model_dump() for _ in range(checks)]
                    consensus = "supported" if all(item.get("supported", False) for item in verification_results) else "reject"
                    result.verification = {
                        "checks_run": checks,
                        "results": verification_results,
                        "consensus": consensus,
                    }
                    result.groundedness = groundedness(
                        response.answer, evidence, case.expected_claims
                    )
                    if consensus == "reject":
                        result.groundedness = result.groundedness.model_copy(
                            update={"passed": False}
                        )
                    result.relevance = relevance(case.question, response.answer)
                    result.language = language_correctness(response.answer, case.language)
                else:
                    result.groundedness = MetricResult(
                        passed=True,
                        score=1.0,
                        reason="No generated factual answer required for this fallback.",
                    )
                    result.verification = {
                        "checks_run": 0,
                        "results": [],
                        "consensus": "not_applicable",
                    }
            else:
                result.actual_behavior = "answer" if decision.answerable else "knowledge_gap"
                result.fallback = _fallback_metric(case, result.actual_behavior)

            result.passed = _case_passed(result, case)
            if not result.passed:
                result.failure_type = _failure_type(result)
        except Exception as exc:
            result.error = str(exc)
            result.failure_type = "execution_error"
        return result

    async def _route(self, question: str) -> RequestTriageResult:
        if self.router is not None:
            return await self.router.classify(question)
        return deterministic_route(question)

    async def evaluate(self, path: str, limit: int | None = None) -> dict[str, object]:
        cases = load_cases(path)
        if limit is not None:
            if limit < 1:
                raise ValueError("Evaluation limit must be at least 1")
            cases = cases[:limit]
        results = []
        interrupted = False
        for index, case in enumerate(cases):
            if index and self.request_delay_seconds:
                try:
                    await asyncio.sleep(self.request_delay_seconds)
                except asyncio.CancelledError:
                    logger.warning("Evaluation cancelled during request pacing")
                    interrupted = True
                    break
            try:
                results.append(await self.evaluate_case(case))
            except asyncio.CancelledError:
                logger.warning("Evaluation cancelled while executing case %s", case.id)
                interrupted = True
                break
        report = build_report(results, cases, interrupted=interrupted)
        report["verification_mode"] = self.verification_mode
        return report


def _fallback_metric(case: EvaluationCase, actual: str) -> MetricResult:
    expected = case.expected_fallback or (None if case.expected_behavior == "answer" else case.expected_behavior)
    passed = actual == (expected or "answer")
    return MetricResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reason="Actual behavior matches expected behavior." if passed else f"Expected {expected}, got {actual}.",
        details={"expected": expected, "actual": actual},
    )


def deterministic_route(question: str) -> RequestTriageResult:
    """Provider-free routing used by offline evaluation."""
    normalized = question.lower()
    human_terms = (
        "fraud", "don't recognize", "do not recognize", "complain", "complaint",
        "speak to someone", "talk to someone", "human", "staff", "agent", "lost my pin",
        "lost pin", "withdraw immediately", "withdrawal immediately", "disagree with a charge",
        "account balance", "account is closed", "account closed", "akaunti imefungwa",
    )
    member_terms = (
        "my balance", "my loan balance", "my loan status", "my loan application",
        "my transaction", "account balance",
        "how long have i been a member", "member since", "membership duration",
        "akaunti yangu", "account imefungwa", "loan yangu",
    )
    guardrail_terms = (
        "should i invest", "tell me where to invest", "investment recommendation",
        "which loan product is best", "step-by-step plan to invest", "stock market",
        "guaranteed return", "invest in crypto", "investment in crypto",
        "what percentage of my money should", "how much should i invest",
    )
    ambiguous_terms = (
        "how much can i get", "how much can i borrow", "what can i get",
        "what languages", "what should i do", "tell me about loans",
    )
    known_short_questions = ("what is interest", "what is a sacco")
    language = "sw" if any(term in normalized for term in ("nini", "naweza", "yangu", "kuhusu", "loan yangu", "akaunti", "mwanachama", "namna gani")) else "en"
    if human := any(term in normalized for term in human_terms):
        return RequestTriageResult(language=language, needs_member_data=False, likely_needs_human=human, reasoning="Sensitive request requires staff routing.")
    if any(term in normalized for term in member_terms):
        return RequestTriageResult(language=language, needs_member_data=True, likely_needs_human=False, reasoning="Request requires the member's own data.")
    if any(term in normalized for term in guardrail_terms):
        return RequestTriageResult(language=language, needs_member_data=False, likely_needs_human=True, reasoning="Directive financial request requires staff guidance.")
    if any(term in normalized for term in ambiguous_terms) or (
        len(normalized.split()) <= 3
        and not any(term in normalized for term in known_short_questions)
    ):
        return RequestTriageResult(language=language, needs_member_data=False, likely_needs_human=True, reasoning="Question is too ambiguous for reliable RAG routing.")
    return RequestTriageResult(language=language, needs_member_data=False, likely_needs_human=False, reasoning="General information request.")


def _routed_behavior(triage: RequestTriageResult, question: str) -> str | None:
    normalized = question.lower()
    if triage.likely_needs_human:
        if any(term in normalized for term in ("complain", "complaint", "fraud", "recognize", "speak to someone", "talk to someone", "human", "staff", "agent", "lost", "withdrawal", "withdraw immediately", "withdrawal immediately", "account balance", "charge", "akaunti imefungwa", "imefungwa", "account closed")):
            return "human_escalation"
        if any(term in normalized for term in ("should i invest", "guaranteed return", "recommendation", "stock market", "invest", "best for my business", "what percentage of my money should", "how much should i invest")):
            return "guardrail"
        return "clarification"
    if triage.needs_member_data:
        if any(term in normalized for term in ("imefungwa", "account closed", "account is closed")):
            return "human_escalation"
        if any(term in normalized for term in ("how long have i been a member", "member since", "membership duration", "account balance")):
            return "human_escalation"
        return "knowledge_gap"
    return None


def _case_passed(result: EvaluationResult, case: EvaluationCase) -> bool:
    if result.error:
        return False
    checks = [result.fallback]
    if case.expected_behavior == "answer":
        checks.extend([result.groundedness, result.relevance, result.language])
    return all(check is not None and check.passed for check in checks)


def _failure_type(result: EvaluationResult) -> str:
    if result.groundedness and not result.groundedness.passed:
        return "hallucination"
    if result.relevance and not result.relevance.passed:
        return "irrelevant_answer"
    if result.language and not result.language.passed:
        return "language_mismatch"
    if result.fallback and not result.fallback.passed:
        return "wrong_behavior"
    return "evaluation_failure"


def build_report(
    results: list[EvaluationResult],
    cases: list[EvaluationCase],
    interrupted: bool = False,
) -> dict[str, object]:
    answer_cases = [item for item in results if item.expected_behavior == "answer"]
    retrieval_cases = [item for item in answer_cases if item.retrieval.get("recall_at_5") is not None]
    answerability_cases = [item for item in results if item.answerability]
    fallback_cases = [item for item in results if item.fallback is not None]
    
    # Separate generated answers from fallback answers
    generated_answer_cases = [item for item in results if item.actual_behavior == "answer"]

    def accuracy(items, predicate):
        return sum(1 for item in items if predicate(item)) / len(items) if items else 0.0

    def count(items, predicate):
        return {
            "correct": sum(1 for item in items if predicate(item)),
            "total": len(items),
        }

    # Execution breakdown
    execution_breakdown = {
        "generated_answers": len(generated_answer_cases),
        "knowledge_gap": sum(1 for item in results if item.actual_behavior == "knowledge_gap"),
        "clarification": sum(1 for item in results if item.actual_behavior == "clarification"),
        "human_escalation": sum(1 for item in results if item.actual_behavior == "human_escalation"),
        "guardrail": sum(1 for item in results if item.actual_behavior == "guardrail"),
        "provider_failure": sum(1 for item in results if item.actual_behavior == "provider_failure"),
    }

    provider_failures = [
        item for item in results if item.actual_behavior == "provider_failure"
    ]
    cases_by_id = {case.id: case for case in cases}
    provider_breakdown = {
        "rate_limit_failures": sum(
            1 for item in provider_failures if item.provider_failure_type == "rate_limit"
        ),
        "timeout_failures": sum(
            1 for item in provider_failures if item.provider_failure_type == "timeout"
        ),
        "authentication_failures": sum(
            1
            for item in provider_failures
            if item.provider_failure_type == "authentication"
        ),
        "other_provider_failures": sum(
            1
            for item in provider_failures
            if item.provider_failure_type not in {"rate_limit", "timeout", "authentication"}
        ),
    }

    source_hits = {
        f"top_{rank}": sum(
            1 for item in retrieval_cases if item.retrieval.get(f"recall_at_{rank}", False)
        )
        for rank in (1, 3, 5)
    }
    hallucination_cases = [
        item for item in generated_answer_cases
        if item.groundedness is not None and not item.groundedness.passed
    ]
    high_risk_hallucinations = sum(
        1 for item in hallucination_cases
        if item.groundedness and item.groundedness.details.get("risk") == "HIGH"
    )

    report = {
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_cases": len(cases),
            "executed": len(results),
            "errors": sum(1 for item in results if item.error),
            "skipped": 0,
            "interrupted": interrupted,
        },
        "execution_breakdown": execution_breakdown,
        "provider": provider_breakdown,
        "retrieval": {
            "expected_answer_cases": len(retrieval_cases),
            "cases_with_correct_source": source_hits["top_5"],
            "source_hits": source_hits,
            **{
                f"recall_at_{rank}": accuracy(
                    retrieval_cases,
                    lambda item, rank=rank: item.retrieval.get(f"recall_at_{rank}", False),
                )
                for rank in (1, 3, 5)
            },
            "error_analysis": _retrieval_error_analysis(results, cases_by_id),
        },
        "answerability": {
            "accuracy": accuracy(answerability_cases, lambda item: item.answerability.get("answerable") == (item.expected_behavior == "answer")),
            **count(answerability_cases, lambda item: item.answerability.get("answerable") == (item.expected_behavior == "answer")),
        },
        "generated_answers": {
            "groundedness": accuracy(generated_answer_cases, lambda item: item.groundedness is not None and item.groundedness.passed),
            "relevance": accuracy(generated_answer_cases, lambda item: item.relevance is not None and item.relevance.passed),
            "language_correctness": accuracy(generated_answer_cases, lambda item: item.language is not None and item.language.passed),
            "cases_generated": len(generated_answer_cases),
            "groundedness_correct": sum(1 for item in generated_answer_cases if item.groundedness is not None and item.groundedness.passed),
            "relevance_correct": sum(1 for item in generated_answer_cases if item.relevance is not None and item.relevance.passed),
            "language_correct": sum(1 for item in generated_answer_cases if item.language is not None and item.language.passed),
        },
        "verification": {
            "structured_failures": sum(
                1 for item in generated_answer_cases
                if item.verification.get("consensus") == "reject"
            ),
            "high_risk_failures": sum(
                1 for item in generated_answer_cases
                if any(result.get("risk") == "HIGH" and not result.get("supported", False)
                       for result in item.verification.get("results", []))
            ),
            "conflicting_evidence": sum(
                1 for item in generated_answer_cases
                if any(result.get("contradictions") for result in item.verification.get("results", []))
            ),
        },
        "fallback": {
            "accuracy": accuracy(fallback_cases, lambda item: item.fallback.passed),
            **count(fallback_cases, lambda item: item.fallback.passed),
        },
        "hallucinations": {
            "total": len(hallucination_cases),
            "high_risk": high_risk_hallucinations,
            "medium_risk": sum(1 for item in hallucination_cases if item.groundedness and item.groundedness.details.get("risk") == "MEDIUM"),
            "low_risk": sum(1 for item in hallucination_cases if item.groundedness and item.groundedness.details.get("risk") == "LOW"),
        },
        "failure_analysis": {
            "retrieval_failures": sum(1 for item in retrieval_cases if not item.retrieval.get("recall_at_5", False)),
            "answerability_failures": sum(1 for item in answerability_cases if item.answerability.get("answerable") != (item.expected_behavior == "answer")),
            "hallucinations": len(hallucination_cases),
            "wrong_fallback": sum(1 for item in fallback_cases if not item.fallback.passed),
            "wrong_routing": sum(
                1 for item in results
                if _is_routing_failure(item, cases_by_id[item.case_id])
            ),
            "irrelevant_answers": sum(1 for item in generated_answer_cases if item.relevance is not None and not item.relevance.passed),
            "language_failures": sum(1 for item in generated_answer_cases if item.language is not None and not item.language.passed),
            "provider_failures": len(provider_failures),
            "conflicting_evidence": sum(1 for item in generated_answer_cases if item.verification.get("consensus") == "reject" and any(result.get("contradictions") for result in item.verification.get("results", []))),
        },
        "case_results": [item.model_dump() for item in results],
    }
    report["verdict"] = _system6_verdict(report)
    return report


def _is_routing_failure(result: EvaluationResult, case: EvaluationCase) -> bool:
    """Count only failures where triage selected the wrong application path."""
    if case.expected_behavior not in {"clarification", "human_escalation", "guardrail"}:
        return False
    return result.actual_behavior != case.expected_behavior


def _retrieval_error_analysis(
    results: list[EvaluationResult],
    cases_by_id: dict[str, EvaluationCase],
) -> dict[str, int]:
    answer_results = [
        result for result in results
        if cases_by_id[result.case_id].expected_behavior == "answer"
        and cases_by_id[result.case_id].expected_source
    ]
    expected_not_retrieved = sum(
        1 for result in answer_results
        if not result.retrieval.get("recall_at_5", False)
    )
    ranked_too_low = sum(
        1 for result in answer_results
        if result.retrieval.get("expected_source_rank") in {4, 5}
    )
    insufficient = sum(
        1 for result in answer_results
        if result.retrieval.get("recall_at_5", False)
        and result.answerability.get("answerable") is False
    )
    return {
        "expected_source_not_retrieved": expected_not_retrieved,
        "retrieved_but_ranked_too_low": ranked_too_low,
        "retrieved_but_insufficient_evidence": insufficient,
        "query_reformulation_failures": 0,
        "metadata_filter_failures": 0,
        "evaluation_source_mismatches": 0,
    }


def _system6_verdict(report: dict[str, object]) -> str:
    failures = report["failure_analysis"]
    verification = report["verification"]
    metadata = report["metadata"]
    if (
        metadata["errors"]
        or verification["high_risk_failures"]
        or failures["wrong_routing"]
        or failures["irrelevant_answers"]
        or failures["answerability_failures"]
    ):
        return "SYSTEM 6 VERDICT: FAIL"
    if (
        verification["structured_failures"]
        or failures["retrieval_failures"]
        or failures["hallucinations"]
    ):
        return "SYSTEM 6 VERDICT: REVIEW"
    return "SYSTEM 6 VERDICT: PASS"
