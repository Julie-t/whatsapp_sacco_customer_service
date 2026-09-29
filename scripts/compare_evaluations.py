#!/usr/bin/env python
"""Compare two compatible System 6 evaluation snapshots."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluations.comparison import compare_reports, render_comparison
from evaluations.history import load_baseline, load_snapshots


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    root = Path(__file__).parent.parent
    history_dir = root / "evaluations" / "results" / "history"
    parser = argparse.ArgumentParser(description="Compare System 6 evaluation snapshots")
    parser.add_argument("--current", type=Path, help="Current report or historical snapshot")
    parser.add_argument("--previous", type=Path, help="Previous report or historical snapshot")
    parser.add_argument("--baseline", action="store_true", help="Compare current against the active baseline")
    args = parser.parse_args()

    current = _load(args.current) if args.current else (load_snapshots(history_dir)[-1] if load_snapshots(history_dir) else None)
    if current is None:
        parser.error("No current evaluation snapshot is available")
    if args.baseline:
        previous = load_baseline(history_dir)
    elif args.previous:
        previous = _load(args.previous)
    else:
        snapshots = load_snapshots(history_dir)
        previous = snapshots[-2] if len(snapshots) > 1 else None
    comparison = compare_reports(current, previous) if previous else {"compatible": False, "reason": "no previous snapshot", "metrics": []}
    print(render_comparison(comparison, current, previous))
    return 0 if comparison.get("compatible") else 1


if __name__ == "__main__":
    raise SystemExit(main())
