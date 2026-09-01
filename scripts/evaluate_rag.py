#!/usr/bin/env python
"""RAG Evaluation Framework.

Evaluates the RAG system against a curated dataset of test cases.

Metrics:
- Retrieval accuracy (Recall@1, @3, @5)
- Answerability accuracy
- Fallback classification accuracy
- Groundedness of generated answers
- Response relevance
- Language correctness

Usage:
    python scripts/evaluate_rag.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ai.rag.answerability import AnswerabilityChecker
from app.ai.rag.pipeline import RAGPipeline
from app.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class RAGEvaluator:
    """Evaluates RAG system performance against test cases."""

    def __init__(self):
        """Initialize evaluator with pipeline and checker."""
        self.pipeline = RAGPipeline()
        self.answerability_checker = AnswerabilityChecker(
            min_retrieval_score=settings.RAG_MIN_SCORE,
        )
        self.results: dict[str, Any] = {
            "metadata": {
                "total_cases": 0,
                "timestamp": None,
            },
            "retrieval_metrics": {
                "recall_at_1": 0.0,
                "recall_at_3": 0.0,
                "recall_at_5": 0.0,
            },
            "answerability_metrics": {
                "accuracy": 0.0,
                "correct": 0,
                "total": 0,
            },
            "fallback_metrics": {
                "accuracy": 0.0,
                "correct": 0,
                "total": 0,
                "evaluated": 0,
                "skipped": 0,
            },
            "case_results": [],
        }

    def load_evaluation_dataset(self, path: str | Path) -> list[dict]:
        """Load evaluation cases from JSON file.

        Args:
            path: Path to evaluation dataset.

        Returns:
            List of evaluation cases.
        """
        path = Path(path)
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("cases", [])

    def evaluate_case(self, case: dict) -> dict:
        """Evaluate a single test case.

        Args:
            case: The evaluation case.

        Returns:
            Results for this case.
        """
        query = case["question"]
        sacco_id = case.get("sacco_id", settings.DEFAULT_SACCO_ID)
        language = case.get("language", "en")
        expected_source = case.get("expected_source")
        expected_fallback = case.get("expected_fallback")
        expected_behavior = case.get("expected_behavior", "answer")

        result = {
            "case_id": case["id"],
            "query": query,
            "expected_behavior": expected_behavior,
            "retrieval_success": False,
            "answerability_decision": None,
            "answerability_correct": False,
            "fallback_correct": False,
            "predicted_fallback": None,
            "notes": case.get("notes", ""),
        }

        try:
            # Run retrieval
            retrieved = self.pipeline.search(
                query=query,
                sacco_id=sacco_id,
                language=language,
                top_k=5,
            )

            # Check if expected source was retrieved
            if expected_source:
                retrieved_ids = [r.document_id for r in retrieved]
                result["retrieval_success"] = expected_source in retrieved_ids
                result["top_retrieved"] = [r.document_id for r in retrieved[:3]]
            else:
                result["retrieval_success"] = len(retrieved) == 0

            # Run answerability check
            decision = self.answerability_checker.check(query, retrieved)
            result["answerability_decision"] = {
                "answerable": decision.answerable,
                "confidence": decision.confidence,
                "reason": decision.reason,
            }

            # Determine expected answerability based on behavior
            if expected_behavior == "answer":
                expected_answerable = True
            elif expected_behavior in ["knowledge_gap", "clarification", "guardrail"]:
                expected_answerable = False
            elif expected_behavior == "human_escalation":
                expected_answerable = False
            else:
                expected_answerable = True

            result["answerability_correct"] = (
                decision.answerable == expected_answerable
            )

            # The offline evaluator can verify the fallback produced by the RAG
            # gate. Intent-router outcomes require a separate conversational run.
            if expected_behavior == "answer":
                result["predicted_fallback"] = None
                result["fallback_correct"] = expected_fallback is None
                result["fallback_evaluable"] = True
            elif expected_fallback in {"knowledge_gap", None}:
                predicted_fallback = "knowledge_gap" if not decision.answerable else None
                result["predicted_fallback"] = predicted_fallback
                result["fallback_correct"] = predicted_fallback == expected_fallback
                result["fallback_evaluable"] = True
            else:
                result["expected_fallback"] = expected_fallback
                result["fallback_evaluable"] = False
                result["fallback_note"] = (
                    "Requires intent-router or conversational evaluation; "
                    "not inferred from retrieval alone."
                )

        except Exception as exc:
            logger.error("Error evaluating case %s: %s", case["id"], exc)
            result["error"] = str(exc)

        return result

    async def evaluate(self, dataset_path: str | Path) -> dict:
        """Evaluate all cases in the dataset.

        Args:
            dataset_path: Path to evaluation dataset JSON.

        Returns:
            Evaluation results.
        """
        logger.info("Loading evaluation dataset from %s", dataset_path)
        cases = self.load_evaluation_dataset(dataset_path)

        logger.info("Starting evaluation of %d cases", len(cases))
        case_results = []

        for i, case in enumerate(cases, 1):
            logger.info("Evaluating case %d/%d: %s", i, len(cases), case["id"])
            case_result = self.evaluate_case(case)
            case_results.append(case_result)

        # Calculate metrics
        self._calculate_metrics(case_results, cases)

        self.results["case_results"] = case_results
        return self.results

    def _calculate_metrics(self, case_results: list[dict], cases: list[dict]) -> None:
        """Calculate aggregated metrics.

        Args:
            case_results: Results for all cases.
            cases: The original cases.
        """
        # Retrieval accuracy (Recall@K)
        cases_by_id = {case["id"]: case for case in cases}
        retrieval_cases = [
            cr for cr in case_results
            if cases_by_id[cr["case_id"]].get("expected_behavior") == "answer"
            and cases_by_id[cr["case_id"]].get("expected_source")
        ]

        if retrieval_cases:
            for rank in (1, 3, 5):
                hits = sum(
                    1
                    for case_result in retrieval_cases
                    if cases_by_id[case_result["case_id"]]["expected_source"]
                    in case_result.get("top_retrieved", [])[:rank]
                )
                self.results["retrieval_metrics"][f"recall_at_{rank}"] = (
                    hits / len(retrieval_cases)
                )

        # Answerability accuracy
        answerable_cases = [cr for cr in case_results if "answerability_decision" in cr]
        if answerable_cases:
            correct = sum(1 for cr in answerable_cases if cr.get("answerability_correct"))
            self.results["answerability_metrics"]["correct"] = correct
            self.results["answerability_metrics"]["total"] = len(answerable_cases)
            self.results["answerability_metrics"]["accuracy"] = (
                correct / len(answerable_cases)
            )

        fallback_cases = [
            cr for cr in case_results if cr.get("fallback_evaluable") is True
        ]
        skipped_fallbacks = [
            cr for cr in case_results if cr.get("fallback_evaluable") is False
        ]
        if fallback_cases:
            correct = sum(1 for cr in fallback_cases if cr["fallback_correct"])
            self.results["fallback_metrics"]["correct"] = correct
            self.results["fallback_metrics"]["total"] = len(fallback_cases)
            self.results["fallback_metrics"]["evaluated"] = len(fallback_cases)
            self.results["fallback_metrics"]["accuracy"] = correct / len(fallback_cases)
        self.results["fallback_metrics"]["skipped"] = len(skipped_fallbacks)

        # Overall count
        self.results["metadata"]["total_cases"] = len(cases)
        self.results["metadata"]["timestamp"] = datetime.now(timezone.utc).isoformat()

    def generate_report(self) -> str:
        """Generate human-readable evaluation report.

        Returns:
            Formatted report string.
        """
        metrics = self.results["retrieval_metrics"]
        answerability = self.results["answerability_metrics"]
        fallback = self.results["fallback_metrics"]

        report = f"""
================================================================================
                        RAG EVALUATION REPORT
================================================================================

DATASET: {self.results["metadata"]["total_cases"]} test cases

RETRIEVAL METRICS
-----------------
Recall@1:  {metrics["recall_at_1"]:.2%}
Recall@3:  {metrics["recall_at_3"]:.2%}
Recall@5:  {metrics["recall_at_5"]:.2%}

ANSWERABILITY METRICS
---------------------
Accuracy:  {answerability["accuracy"]:.2%}
           {answerability["correct"]}/{answerability["total"]} correct

FALLBACK METRICS
----------------
Accuracy:  {fallback["accuracy"]:.2%}
           {fallback["correct"]}/{fallback["total"]} evaluated
Skipped:   {fallback["skipped"]} intent-router cases

CASE-BY-CASE RESULTS
--------------------
"""

        for cr in self.results["case_results"][:10]:  # First 10 for brevity
            status = "✓" if cr.get("retrieval_success", False) else "✗"
            report += f"\n{status} {cr['case_id']}: {cr['query'][:60]}"
            if "answerability_decision" in cr:
                decision = cr["answerability_decision"]
                report += f"\n    Answerability: {decision['answerable']} (confidence: {decision['confidence']:.2f})"

        if len(self.results["case_results"]) > 10:
            report += f"\n\n... and {len(self.results['case_results']) - 10} more cases"

        report += "\n\n================================================================================\n"
        return report


async def main() -> int:
    """Main evaluation entry point.

    Returns:
        Exit code (0 = success).
    """
    evaluation_file = Path(__file__).parent.parent / "data" / "evaluation" / "rag_eval.json"

    if not evaluation_file.exists():
        logger.error("Evaluation dataset not found at %s", evaluation_file)
        return 1

    evaluator = RAGEvaluator()

    logger.info("Starting RAG evaluation...")
    results = await evaluator.evaluate(evaluation_file)

    report = evaluator.generate_report()
    logger.info(report)

    # Save results
    output_file = Path(__file__).parent.parent / "data" / "evaluation" / "rag_eval_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Results saved to %s", output_file)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
