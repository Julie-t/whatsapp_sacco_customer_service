"""Deterministic formatting of retrieved evidence for grounded generation."""

from collections.abc import Iterable
import re

from app.ai.rag.models import RAGResult


_STOPWORDS = {
    "a", "an", "and", "are", "can", "do", "for", "how", "i", "is", "my",
    "of", "on", "the", "to", "what", "where", "which", "with",
}


def select_context(query: str, results: Iterable[RAGResult], max_results: int = 3) -> list[RAGResult]:
    """Select evidence that has both retrieval confidence and query alignment."""
    candidates = list(results)
    if not candidates:
        return []
    query_terms = _terms(query)

    # Keep operational questions anchored to the requested object/action.
    query_lower = query.lower()
    anchor_groups: list[set[str]] = []
    if "guarantor" in query_lower:
        anchor_groups.append({"guarantor"})
    if "defer" in query_lower or "deferral" in query_lower:
        anchor_groups.append({"defer", "deferral", "postpone", "moratorium"})
    if anchor_groups:
        anchored = [
            result
            for result in candidates
            if all(
                any(term in _terms(f"{result.title} {result.topic} {result.content}") for term in group)
                for group in anchor_groups
            )
        ]
        if anchored:
            candidates = anchored

    def ranking_key(result: RAGResult) -> tuple[float, float, float]:
        document_text = f"{result.title} {result.topic} {result.content}"
        overlap = len(query_terms & _terms(document_text)) / len(query_terms) if query_terms else 0.0
        return (overlap, result.score, -len(document_text))

    return sorted(candidates, key=ranking_key, reverse=True)[:max_results]


def _terms(text: str) -> set[str]:
    return {
        token[:-1] if token.endswith("s") and len(token) > 4 else token
        for token in re.findall(r"[a-zA-Z]+", text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def build_context(results: Iterable[RAGResult]) -> str:
    """Format retrieval evidence without adding facts or fallback content."""
    sections = []
    for index, result in enumerate(results, start=1):
        synthetic = result.metadata.get("is_test_data", False)
        sections.append(
            "\n".join(
                [
                    f"--- SOURCE {index} ---",
                    f"Document ID: {result.document_id}",
                    f"Chunk ID: {result.chunk_id}",
                    f"Title: {result.title}",
                    f"Source: {result.source}",
                    f"Similarity score: {result.score:.6f}",
                    f"SACCO ID: {result.sacco_id}",
                    f"Language: {result.language}",
                    f"Content type: {result.content_type}",
                    f"Topic: {result.topic}",
                    f"Synthetic/demo data: {synthetic}",
                    f"Content: {result.content}",
                    f"--- END SOURCE {index} ---",
                ]
            )
        )
    return "\n\n".join(sections)