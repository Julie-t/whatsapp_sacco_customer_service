"""Deterministic formatting of retrieved evidence for grounded generation."""

from collections.abc import Iterable

from app.ai.rag.models import RAGResult


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