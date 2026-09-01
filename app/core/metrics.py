"""Small process-local operational counters for MVP monitoring."""

from collections import Counter
from threading import Lock

_provider_failures = Counter()
_knowledge_gaps = Counter()
_lock = Lock()


def record_provider_failure(provider: str, operation: str, failure_type: str) -> None:
    with _lock:
        _provider_failures[(provider, operation, failure_type)] += 1


def record_knowledge_gap(sacco_id: str, language: str) -> None:
    with _lock:
        _knowledge_gaps[(sacco_id, language)] += 1


def snapshot() -> dict[str, list[dict[str, object]]]:
    with _lock:
        return {
            "provider_failures": [
                {"provider": p, "operation": o, "failure_type": f, "count": count}
                for (p, o, f), count in _provider_failures.items()
            ],
            "knowledge_gaps": [
                {"sacco_id": s, "language": language, "count": count}
                for (s, language), count in _knowledge_gaps.items()
            ],
        }