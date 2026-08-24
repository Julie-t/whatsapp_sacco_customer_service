"""Retriever: query -> embedding -> vector search -> structured results.

This module returns *evidence* (retrieved chunks with scores), never answers.
It does not call NVIDIA or any LLM. Metadata filtering is passed straight
through to the vector store, so adding filterable fields requires no change
here.
"""

import logging
import time
from typing import Any

from app.ai.rag.embeddings import EmbeddingProvider
from app.ai.rag.models import RAGResult
from app.ai.rag.vector_store import QdrantVectorStore
from app.config.settings import settings

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        top_k: int | None = None,
        min_score: float | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.top_k = top_k or settings.RAG_TOP_K
        self.min_score = min_score if min_score is not None else settings.RAG_MIN_SCORE
        # Make sure the collection exists with the embedding dimension.
        self.vector_store.ensure_collection(self.embedding_provider.dimension())

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RAGResult]:
        top_k = top_k or self.top_k
        threshold = min_score if min_score is not None else self.min_score
        total_start = time.perf_counter()

        embed_start = time.perf_counter()
        query_vector = self.embedding_provider.embed_query(query)
        embed_latency = time.perf_counter() - embed_start

        retrieve_start = time.perf_counter()
        raw = self.vector_store.search(query_vector, top_k=top_k, filters=filters)
        retrieve_latency = time.perf_counter() - retrieve_start

        total_latency = time.perf_counter() - total_start

        results = [RAGResult(**item) for item in raw]
        if threshold > 0.0:
            results = [r for r in results if r.score > threshold]

        logger.info(
            "RAG retrieval | query=%r results=%d embed=%.3fs retrieve=%.3fs total=%.3fs",
            query[:80],
            len(results),
            embed_latency,
            retrieve_latency,
            total_latency,
        )
        return results
