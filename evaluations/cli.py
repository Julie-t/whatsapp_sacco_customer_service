"""Command-line entry point for System 6 evaluation."""

import argparse
import asyncio
import re
from pathlib import Path

from app.ai.llm import LLM
from app.ai.intent_router import IntentRouter
from app.ai.rag.pipeline import RAGPipeline
from app.services.rag_answer_service import RAGAnswerService
from app.config.settings import settings

from .offline import seed_demo_store
from .comparison import compare_reports, render_comparison
from .history import load_baseline, load_snapshots, run_metadata, save_snapshot, set_baseline
from .reporting import render_case_answers, render_report, write_report
from .runner import EvaluationRunner


class OfflineLLM:
    """Deterministic generator used to keep normal evaluation provider-free."""

    async def generate(self, messages: list[dict[str, str]]) -> str:
        context = messages[0].get("content", "")
        query = messages[1].get("content", "") if len(messages) > 1 else ""
        blocks = re.findall(r"Content:\s*(.*?)\s*--- END SOURCE", context, flags=re.DOTALL)
        if blocks:
            query_terms = _offline_terms(query)
            return max(
                blocks,
                key=lambda block: len(query_terms & _offline_terms(block)),
            ).strip()
        return "The requested information was not found in the retrieved context."


def _offline_terms(text: str) -> set[str]:
    stopwords = {"a", "an", "and", "are", "can", "do", "for", "how", "i", "is", "my", "of", "the", "to", "what", "with"}
    return {
        token[:-1] if token.endswith("s") and len(token) > 4 else token
        for token in re.findall(r"[a-zA-Z]+", text.lower())
        if token not in stopwords and len(token) > 2
    }


async def run(dataset: Path, output: Path, live: bool, show_answers: bool, limit: int | None, verification_mode: str, is_baseline: bool = False, replace_baseline: bool = False) -> int:
    history_dir = output.parent / "history"
    if is_baseline and history_dir.joinpath("baseline.json").exists() and not replace_baseline:
        print("An active baseline already exists. Use --replace-baseline to replace it.")
        return 2
    if live:
        pipeline = RAGPipeline()
        llm = LLM()
    else:
        in_memory_store = seed_demo_store()
        pipeline = RAGPipeline(vector_store=in_memory_store)
        llm = OfflineLLM()
    service = RAGAnswerService(pipeline, llm)
    router = IntentRouter(llm) if live else None
    report = await EvaluationRunner(
        pipeline,
        service,
        router=router,
        verification_llm=llm if live else None,
        request_delay_seconds=settings.EVAL_REQUEST_DELAY_SECONDS if live else 0.0,
        verification_mode=verification_mode,
    ).evaluate(str(dataset), limit=limit)
    mode = "live" if live else "offline"
    provider = "Groq" if live else "None"
    model = settings.GROQ_MODEL if live else "offline-deterministic"
    report["metadata"]["mode"] = mode
    report["metadata"]["provider_name"] = provider
    report["metadata"]["model"] = model
    report["metadata"]["generated_answer_metrics"] = (
        "LIVE LLM QUALITY" if live else "DETERMINISTIC SMOKE TEST - NOT REPRESENTATIVE OF LIVE LLM QUALITY"
    )
    report["run"] = run_metadata(
        report,
        root=output.parent.parent.parent,
        dataset=dataset,
        mode=mode,
        provider=provider,
        model=model,
        is_baseline=is_baseline,
    )
    snapshots = load_snapshots(history_dir)
    previous = snapshots[-1] if snapshots else None
    baseline = load_baseline(history_dir)
    report["comparison"] = {
        "previous": compare_reports(report, previous) if previous else None,
        "baseline": compare_reports(report, baseline) if baseline else None,
    }
    write_report(report, output)
    snapshot = save_snapshot(report, history_dir)
    if is_baseline:
        set_baseline(report, history_dir, replace=replace_baseline)
    print(render_report(report))
    if show_answers:
        mode = "live" if live else "offline"
        print(render_case_answers(report, mode, str(dataset)))
    print(f"JSON report: {output}")
    if previous:
        print(render_comparison(report["comparison"]["previous"], report, previous))
    print(f"Historical snapshot: {snapshot}")
    return 0 if report["metadata"]["errors"] == 0 else 1


def main() -> int:
    root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Evaluate System 6 RAG behavior")
    parser.add_argument("--dataset", type=Path, default=root / "data/evaluation/rag_eval.json")
    parser.add_argument("--output", type=Path, default=root / "evaluations/results/latest_report.json")
    parser.add_argument("--live", action="store_true", help="Use the configured LLM provider")
    parser.add_argument("--limit", type=int, help="Evaluate only the first N cases")
    parser.add_argument(
        "--verification-mode",
        choices=("standard", "high-risk"),
        default="standard",
        help="Run one check normally or two checks for high-risk generated answers",
    )
    parser.add_argument(
        "--show-answers",
        action="store_true",
        help="Print setup and each generated answer in the CLI",
    )
    parser.add_argument("--baseline", action="store_true", help="Mark this run as the active comparison baseline")
    parser.add_argument("--replace-baseline", action="store_true", help="Replace an existing active baseline")
    args = parser.parse_args()
    return asyncio.run(run(args.dataset, args.output, args.live, args.show_answers, args.limit, args.verification_mode, args.baseline, args.replace_baseline))


if __name__ == "__main__":
    raise SystemExit(main())
