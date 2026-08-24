"""Deterministic character-based chunking with overlap.

Strategy
--------
Documents are split into overlapping windows of ``chunk_size`` characters
(default 1000) with ``chunk_overlap`` characters (default 200) of shared
context between consecutive windows. The split is purely positional, so the
same input always produces the same chunk boundaries and therefore the same
deterministic ``chunk_id`` values. Repeated ingestion never produces random
output.

A trailing window that is smaller than ``chunk_min_size`` (default 200) is
merged back into the previous chunk to avoid tiny fragments.

Metadata from the source document is copied verbatim into every chunk.
"""

import logging

from app.ai.rag.models import RAGChunk, RAGDocument
from app.config.settings import settings

logger = logging.getLogger(__name__)


def _split_text(text: str, chunk_size: int, chunk_overlap: int, chunk_min_size: int) -> list[str]:
    text = text or ""
    stripped = text.strip()
    if not stripped:
        return []

    if len(stripped) <= chunk_size:
        return [stripped]

    step = max(1, chunk_size - chunk_overlap)
    windows: list[str] = []
    start = 0
    while start < len(stripped):
        end = min(start + chunk_size, len(stripped))
        windows.append(stripped[start:end].strip())
        if end >= len(stripped):
            break
        start += step

    # Merge a tiny trailing window into the previous one.
    if len(windows) >= 2 and len(windows[-1]) < chunk_min_size:
        merged = (windows[-2] + " " + windows[-1]).strip()
        windows = windows[:-2] + [merged]

    return [w for w in windows if w]


def chunk_document(
    document: RAGDocument,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    chunk_min_size: int | None = None,
) -> list[RAGChunk]:
    """Split a document into deterministic, metadata-preserving chunks."""
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
    chunk_min_size = chunk_min_size or settings.RAG_CHUNK_MIN_SIZE

    windows = _split_text(document.content, chunk_size, chunk_overlap, chunk_min_size)

    if not windows:
        logger.warning("Document %s produced no chunks (empty content).", document.document_id)
        return []

    chunks: list[RAGChunk] = []
    for index, window in enumerate(windows):
        chunks.append(
            RAGChunk(
                chunk_id=f"{document.document_id}_chunk_{index:02d}",
                document_id=document.document_id,
                chunk_index=index,
                title=document.title,
                content=window,
                source=document.source,
                content_type=document.content_type,
                sacco_id=document.sacco_id,
                language=document.language,
                topic=document.topic,
                audience=document.audience,
                goals=list(document.goals),
                effective_date=document.effective_date,
                metadata=dict(document.metadata),
            )
        )
    return chunks
