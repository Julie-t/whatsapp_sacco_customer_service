"""Persistent, immutable evaluation-run history."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


HISTORY_VERSION = "6.3"


def git_metadata(root: Path) -> dict[str, str | None]:
    """Return git commit and branch when the evaluation runs inside a repository."""
    def git_value(*args: str) -> str | None:
        try:
            value = subprocess.run(
                ["git", *args],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
        return value or None

    return {"git_commit": git_value("rev-parse", "HEAD"), "git_branch": git_value("branch", "--show-current")}


def dataset_version(path: Path) -> str | None:
    """Hash the dataset bytes so comparisons do not rely on a filename alone."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def run_metadata(
    report: dict[str, Any],
    *,
    root: Path,
    dataset: Path,
    mode: str,
    provider: str,
    model: str,
    is_baseline: bool = False,
) -> dict[str, Any]:
    timestamp = datetime.now(UTC)
    run_id = timestamp.strftime("%Y%m%d_%H%M%S_%f")
    metadata = report.setdefault("metadata", {})
    metadata.update({"mode": mode, "provider_name": provider, "model": model})
    git = git_metadata(root)
    return {
        "run_id": run_id,
        "timestamp": timestamp.isoformat(),
        "mode": mode,
        "provider": provider,
        "model": model,
        "dataset_path": str(dataset.resolve()),
        "dataset_case_count": metadata.get("total_cases", 0),
        "dataset_version": dataset_version(dataset),
        "git_commit": git["git_commit"],
        "git_branch": git["git_branch"],
        "python_version": platform.python_version() or sys.version.split()[0],
        "evaluation_version": HISTORY_VERSION,
        "is_baseline": is_baseline,
        "generated_answer_metrics": metadata.get("generated_answer_metrics"),
    }


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_") or "unknown"


def snapshot_path(history_dir: Path, run: dict[str, Any]) -> Path:
    return history_dir / f"{run['run_id']}_{_slug(run['mode'])}_{_slug(run['model'])}.json"


def save_snapshot(report: dict[str, Any], history_dir: Path) -> Path:
    """Write one run once; never replace an existing historical snapshot."""
    history_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(history_dir, report["run"])
    if path.exists():
        raise FileExistsError(f"Evaluation snapshot already exists: {path}")
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8", newline="\n")
    return path


def load_snapshots(history_dir: Path) -> list[dict[str, Any]]:
    snapshots = []
    for path in sorted(history_dir.glob("*.json")):
        if path.name in {"baseline.json"}:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("run", {}).get("run_id"):
            snapshots.append(data)
    return sorted(snapshots, key=lambda item: item["run"].get("timestamp", ""))


def baseline_path(history_dir: Path) -> Path:
    return history_dir / "baseline.json"


def set_baseline(snapshot: dict[str, Any], history_dir: Path, replace: bool = False) -> None:
    """Set the active baseline without silently replacing one."""
    path = baseline_path(history_dir)
    if path.exists() and not replace:
        raise FileExistsError(f"An active baseline already exists: {path}. Use --replace-baseline.")
    history_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8", newline="\n")


def load_baseline(history_dir: Path) -> dict[str, Any] | None:
    path = baseline_path(history_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
