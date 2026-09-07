"""Load and validate evaluation datasets."""

import json
from pathlib import Path

from .models import EvaluationCase


def load_cases(path: str | Path) -> list[EvaluationCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("Evaluation dataset must contain a cases list")
    cases = [EvaluationCase.model_validate(case) for case in payload["cases"]]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique")
    return cases
