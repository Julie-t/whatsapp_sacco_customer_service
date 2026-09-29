import json
from pathlib import Path

import pytest

from evaluations.comparison import compare_reports
from evaluations.history import load_snapshots, run_metadata, save_snapshot, set_baseline


def report(tmp_path: Path) -> dict:
    dataset = tmp_path / "dataset.json"
    dataset.write_text('{"cases": []}', encoding="utf-8")
    value = {
        "metadata": {"total_cases": 2, "executed": 2},
        "retrieval": {"recall_at_1": 0.5, "expected_answer_cases": 2},
        "answerability": {"accuracy": 0.5, "total": 2},
        "generated_answers": {"groundedness": 1.0, "relevance": 0.5, "language_correctness": 1.0, "cases_generated": 1},
        "fallback": {"accuracy": 0.5, "total": 2},
        "hallucinations": {"total": 1, "high_risk": 0},
    }
    value["run"] = run_metadata(value, root=tmp_path, dataset=dataset, mode="offline", provider="None", model="offline")
    return value


def test_snapshot_history_is_immutable_and_loadable(tmp_path):
    history = tmp_path / "history"
    snapshot = report(tmp_path)
    path = save_snapshot(snapshot, history)
    assert path.exists()
    assert len(load_snapshots(history)) == 1
    with pytest.raises(FileExistsError):
        save_snapshot(snapshot, history)


def test_baseline_cannot_be_replaced_silently(tmp_path):
    history = tmp_path / "history"
    snapshot = report(tmp_path)
    set_baseline(snapshot, history)
    with pytest.raises(FileExistsError):
        set_baseline(snapshot, history)


def test_comparison_tracks_deltas_and_denominators(tmp_path):
    previous = report(tmp_path)
    current = report(tmp_path)
    current["retrieval"]["recall_at_1"] = 0.75
    comparison = compare_reports(current, previous)
    metric = next(item for item in comparison["metrics"] if item["name"] == "Recall@1")
    assert metric["status"] == "IMPROVED"
    assert metric["current_denominator"] == 2
    assert metric["previous_denominator"] == 2


def test_offline_and_live_runs_are_not_comparable(tmp_path):
    previous = report(tmp_path)
    current = report(tmp_path)
    current["run"]["mode"] = "live"
    comparison = compare_reports(current, previous)
    assert comparison["compatible"] is False
