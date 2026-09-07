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


async def run(dataset: Path, output: Path, live: bool, show_answers: bool, limit: int | None, verification_mode: str) -> int:
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
    report["metadata"]["mode"] = "LIVE" if live else "OFFLINE / DETERMINISTIC"
    report["metadata"]["provider_name"] = "Groq" if live else "None"
    report["metadata"]["model"] = settings.GROQ_MODEL if live else "Offline deterministic generator"
    write_report(report, output)
    print(render_report(report))
    if show_answers:
        mode = "live" if live else "offline"
        print(render_case_answers(report, mode, str(dataset)))
    print(f"JSON report: {output}")
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
    args = parser.parse_args()
    return asyncio.run(run(args.dataset, args.output, args.live, args.show_answers, args.limit, args.verification_mode))


if __name__ == "__main__":
    raise SystemExit(main())
