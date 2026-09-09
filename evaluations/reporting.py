"""Evaluation report rendering and persistence."""

import json
from pathlib import Path


def write_report(report: dict[str, object], output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def render_report(report: dict[str, object]) -> str:
    metadata = report["metadata"]
    retrieval = report["retrieval"]
    answerability = report["answerability"]
    generated = report["generated_answers"]
    fallback = report["fallback"]
    execution = report.get("execution_breakdown", {})
    provider = report.get("provider", {})
    verification = report.get("verification", {})
    hallucinations = report.get("hallucinations", {})
    failures = report.get("failure_analysis", {})
    retrieval_errors = retrieval.get("error_analysis", {})
    
    lines = [
        "SACCO AI SYSTEM 6 EVALUATION",
        "=" * 32,
        f"Mode: {metadata.get('mode', 'UNKNOWN')}",
        f"Provider: {metadata.get('provider_name', 'unknown')} | Model: {metadata.get('model', 'unknown')}",
        f"Cases: {metadata['total_cases']} | Executed: {metadata['executed']} | Errors: {metadata['errors']}",
        "",
    ]
    
    # Execution breakdown
    if execution:
        lines.extend([
            "EXECUTION BREAKDOWN",
            f"Generated answers: {execution.get('generated_answers', 0)}",
            f"Knowledge-gap fallback: {execution.get('knowledge_gap', 0)}",
            f"Clarification: {execution.get('clarification', 0)}",
            f"Human escalation: {execution.get('human_escalation', 0)}",
            f"Guardrail: {execution.get('guardrail', 0)}",
            f"Provider failure: {execution.get('provider_failure', 0)}",
            "",
        ])

    lines.extend([
        "PROVIDER",
        f"Rate-limit failures: {provider.get('rate_limit_failures', 0)}",
        f"Timeout failures: {provider.get('timeout_failures', 0)}",
        f"Authentication failures: {provider.get('authentication_failures', 0)}",
        f"Other provider failures: {provider.get('other_provider_failures', 0)}",
        "",
    ])

    lines.extend([
        "VERIFICATION",
        f"Structured verification failures: {verification.get('structured_failures', 0)}",
        f"High-risk verification failures: {verification.get('high_risk_failures', 0)}",
        f"Conflicting evidence cases: {verification.get('conflicting_evidence', 0)}",
        "",
    ])
    
    # Retrieval
    lines.extend([
        "RETRIEVAL",
        f"Recall@1: {retrieval['recall_at_1']:.2%}",
        f"Recall@3: {retrieval['recall_at_3']:.2%}",
        f"Recall@5: {retrieval['recall_at_5']:.2%}",
        f"Expected answer cases: {retrieval.get('expected_answer_cases', 0)}",
        f"Cases with correct source in Top-5: {retrieval.get('cases_with_correct_source', 0)}",
        "",
        "RETRIEVAL ERROR ANALYSIS",
        f"Expected source not retrieved: {retrieval_errors.get('expected_source_not_retrieved', 0)}",
        f"Retrieved but ranked too low: {retrieval_errors.get('retrieved_but_ranked_too_low', 0)}",
        f"Retrieved but insufficient evidence: {retrieval_errors.get('retrieved_but_insufficient_evidence', 0)}",
        f"Query reformulation failures: {retrieval_errors.get('query_reformulation_failures', 0)}",
        f"Metadata/filter failures: {retrieval_errors.get('metadata_filter_failures', 0)}",
        f"Evaluation-source mismatches: {retrieval_errors.get('evaluation_source_mismatches', 0)}",
        "",
    ])
    
    # Answerability
    lines.extend([
        "ANSWERABILITY",
        f"Accuracy: {answerability['accuracy']:.2%} ({answerability.get('correct', 0)}/{answerability.get('total', 0)})",
        "",
    ])
    
    # Generated answers (only if there are generated answers)
    if execution.get('generated_answers', 0) > 0:
        lines.extend([
            "GENERATED ANSWERS",
            f"Cases generated: {generated.get('cases_generated', execution['generated_answers'])}",
            f"Groundedness: {generated['groundedness']:.2%} ({generated.get('groundedness_correct', 0)}/{generated['cases_generated']})",
            f"Relevance: {generated['relevance']:.2%} ({generated.get('relevance_correct', 0)}/{generated['cases_generated']})",
            f"Language correctness: {generated['language_correctness']:.2%} ({generated.get('language_correct', 0)}/{generated['cases_generated']})",
            "",
        ])
    
    # Fallback / Routing
    lines.extend([
        "FALLBACK / ROUTING",
        f"Accuracy: {fallback['accuracy']:.2%} ({fallback.get('correct', 0)}/{fallback.get('total', 0)})",
        "",
        "HALLUCINATIONS",
        f"Total: {hallucinations.get('total', 0)}",
        f"High-risk: {hallucinations.get('high_risk', 0)}",
        f"Medium-risk: {hallucinations.get('medium_risk', 0)}",
        f"Low-risk: {hallucinations.get('low_risk', 0)}",
        "",
        "FAILURE ANALYSIS",
        f"Retrieval failures: {failures.get('retrieval_failures', 0)}",
        f"Answerability failures: {failures.get('answerability_failures', 0)}",
        f"Hallucinations: {failures.get('hallucinations', 0)}",
        f"Wrong fallback: {failures.get('wrong_fallback', 0)}",
        f"Wrong routing: {failures.get('wrong_routing', 0)}",
        f"Irrelevant answers: {failures.get('irrelevant_answers', 0)}",
        f"Language failures: {failures.get('language_failures', 0)}",
        f"Provider failures: {failures.get('provider_failures', 0)}",
        f"Verification conflicts: {failures.get('conflicting_evidence', 0)}",
    ])
    lines.append(report.get("verdict", "SYSTEM 6 VERDICT: REVIEW"))
    
    return "\n".join(lines)


def render_case_answers(report: dict[str, object], mode: str, dataset: str) -> str:
    lines = [
        "",
        "RUN SETUP",
        f"Mode: {mode}",
        f"Dataset: {dataset}",
        "Answers are generated by the configured RAG pipeline and provider.",
        "",
        "CASE ANSWERS",
        "=" * 32,
    ]
    for case in report["case_results"]:
        sources = ", ".join(
            case.get("retrieval", {}).get("top_retrieved", [])
        ) or "none"
        answer = _sanitize_for_console(case.get("answer") or "(no answer)")
        lines.extend(
            [
                f"[{case['case_id']}] {case['question']}",
                f"Expected: {case['expected_behavior']} | Actual: {case.get('actual_behavior') or 'error'} | Passed: {case['passed']}",
                f"Answer: {answer}",
                f"Retrieved: {sources}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def _sanitize_for_console(text: str) -> str:
    """Replace problematic Unicode characters with ASCII equivalents.

    Groq and other LLMs commonly emit narrow no-break spaces, non-breaking
    hyphens, and smart quotes that Windows cp1252 cannot encode.
    """
    replacements = {
        "\u202f": " ",   # narrow no-break space
        "\u00a0": " ",   # non-breaking space
        "\u2011": "-",   # non-breaking hyphen
        "\u2013": "-",   # en dash
        "\u2014": "--",  # em dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text
