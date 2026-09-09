"""Context-aware comparisons between evaluation snapshots."""

from __future__ import annotations

from typing import Any


METRICS = (
    ("Recall@1", ("retrieval", "recall_at_1"), "higher"),
    ("Recall@3", ("retrieval", "recall_at_3"), "higher"),
    ("Recall@5", ("retrieval", "recall_at_5"), "higher"),
    ("Answerability", ("answerability", "accuracy"), "higher"),
    ("Groundedness", ("generated_answers", "groundedness"), "higher"),
    ("Relevance", ("generated_answers", "relevance"), "higher"),
    ("Language correctness", ("generated_answers", "language_correctness"), "higher"),
    ("Routing/fallback", ("fallback", "accuracy"), "higher"),
    ("Hallucinations", ("hallucinations", "total"), "lower"),
    ("High-risk hallucinations", ("hallucinations", "high_risk"), "lower"),
)


def compatibility(current: dict[str, Any], previous: dict[str, Any], *, generated: bool = False) -> tuple[bool, str]:
    current_run = current.get("run", {})
    previous_run = previous.get("run", {})
    for field in ("mode", "dataset_case_count", "dataset_version"):
        if current_run.get(field) != previous_run.get(field):
            return False, f"{field} differs"
    if generated and (
        current_run.get("provider") != previous_run.get("provider")
        or current_run.get("model") != previous_run.get("model")
    ):
        return False, "provider or model differs"
    return True, "compatible"


def _value(report: dict[str, Any], section: str, field: str) -> tuple[float | int | None, int | None]:
    section_data = report.get(section, {})
    value = section_data.get(field)
    if value is None:
        return None, None
    if section == "generated_answers":
        denominator = section_data.get("cases_generated")
    elif section == "answerability":
        denominator = section_data.get("total")
    elif section == "retrieval":
        denominator = section_data.get("expected_answer_cases")
    elif section == "fallback":
        denominator = section_data.get("total")
    else:
        denominator = report.get("metadata", {}).get("executed")
    return value, denominator


def compare_reports(current: dict[str, Any], previous: dict[str, Any], *, allow_mode_mismatch: bool = False) -> dict[str, Any]:
    """Compare metrics only when their evaluation context is compatible."""
    same, reason = compatibility(current, previous, generated=False)
    if not same and not allow_mode_mismatch:
        return {"compatible": False, "reason": reason, "metrics": []}
    metrics = []
    for label, (section, field), direction in METRICS:
        current_value, current_denominator = _value(current, section, field)
        previous_value, previous_denominator = _value(previous, section, field)
        if current_value is None or previous_value is None:
            continue
        delta = current_value - previous_value
        if isinstance(current_value, float) or isinstance(previous_value, float):
            display_delta = delta * 100
            status = "IMPROVED" if (delta > 0 and direction == "higher") or (delta < 0 and direction == "lower") else "REGRESSED" if delta else "UNCHANGED"
        else:
            display_delta = delta
            status = "IMPROVED" if (delta > 0 and direction == "higher") or (delta < 0 and direction == "lower") else "REGRESSED" if delta else "UNCHANGED"
        metrics.append({
            "name": label,
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "delta_display": display_delta,
            "status": status,
            "direction": direction,
            "current_denominator": current_denominator,
            "previous_denominator": previous_denominator,
        })
    return {"compatible": same or allow_mode_mismatch, "reason": reason, "metrics": metrics}


def render_comparison(comparison: dict[str, Any], current: dict[str, Any], previous: dict[str, Any] | None) -> str:
    lines = ["SYSTEM 6 EVALUATION COMPARISON", "=" * 31]
    if previous is None:
        return "\n".join(lines + ["No compatible previous evaluation found."])
    current_run = current.get("run", {})
    previous_run = previous.get("run", {})
    lines.extend([
        f"Current: {current_run.get('run_id', 'unknown')} | {current_run.get('mode', 'unknown')} | {current_run.get('dataset_case_count', '?')} cases",
        f"Previous: {previous_run.get('run_id', 'unknown')} | {previous_run.get('mode', 'unknown')} | {previous_run.get('dataset_case_count', '?')} cases",
        "",
    ])
    if not comparison.get("compatible"):
        lines.append(f"Comparison unavailable: {comparison.get('reason', 'incompatible context')}.")
        return "\n".join(lines)
    lines.append("METRIC CHANGES")
    lines.append("--------------")
    for metric in comparison.get("metrics", []):
        if isinstance(metric["current"], float):
            current_text = f"{metric['current']:.2%}"
            previous_text = f"{metric['previous']:.2%}"
            delta_text = f"{metric['delta_display']:+.2f} pp"
        else:
            current_text = str(metric["current"])
            previous_text = str(metric["previous"])
            delta_text = f"{metric['delta_display']:+g}"
        lines.extend([metric["name"], f"{previous_text} -> {current_text}", f"Delta {delta_text}", metric["status"], ""])
    return "\n".join(lines).rstrip()
