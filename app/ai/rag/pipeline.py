"""Thin application-level RAG pipeline wrapper.

Exposes a single ``search(query, ...)`` operation that wires the embedding
provider -> vector store -> retriever. No LLM generation happens here.
"""

import logging
from typing import Any

from app.ai.rag.embeddings import EmbeddingProvider, SentenceTransformerEmbeddingProvider
from app.ai.rag.models import RAGResult
from app.ai.rag.retriever import Retriever
from app.ai.rag.vector_store import QdrantVectorStore
from app.config.settings import settings

logger = logging.getLogger(__name__)


def _default_embedding_provider() -> EmbeddingProvider:
    return SentenceTransformerEmbeddingProvider(model_name=settings.EMBEDDING_MODEL)


class RAGPipeline:
    def __init__(
        self,
        retriever: Retriever | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
    ):
        if retriever is not None:
            self.retriever = retriever
        else:
            provider = embedding_provider or _default_embedding_provider()
            store = vector_store or QdrantVectorStore()
            self.retriever = Retriever(provider, store)

    def search(
        self,
        query: str,
        sacco_id: str | None = None,
        language: str | None = None,
        content_type: str | None = None,
        topic: str | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[RAGResult]:
        merged = dict(filters or {})
        if sacco_id is not None:
            merged["sacco_id"] = sacco_id
        if language is not None:
            merged["language"] = language
        if content_type is not None:
            merged["content_type"] = content_type
        if topic is not None:
            merged["topic"] = topic

        return self.retriever.search(
            query, filters=merged or None, top_k=top_k, min_score=min_score
        )
