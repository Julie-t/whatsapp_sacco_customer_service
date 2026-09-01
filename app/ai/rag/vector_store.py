"""Qdrant vector store adapter.

A thin, provider-specific adapter that isolates all Qdrant interactions behind
a small interface used by the retriever and ingestion pipeline. The collection
name, URL and vector size are configurable; nothing here is hardcoded to a
specific SACCO.

Cosine similarity is used. When ``QDRANT_URL`` is empty an in-memory client is
used, which keeps tests and lightweight local runs free of external services.
"""

import logging
import uuid
from typing import Any, Iterable

from app.ai.rag.models import RAGChunk
from app.config.settings import settings

logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    """Raised for unrecoverable Qdrant interaction failures."""


def _build_filter(filters: dict[str, Any] | None):
    """Translate a flat metadata filter dict into a Qdrant Filter.

    Each key maps to a metadata field. A scalar value becomes a
    ``MatchValue``; a list value becomes a ``MatchAny`` (useful for fields
    such as ``goals`` or ``audience``). Unknown/empty values are ignored so
    adding new filterable fields never requires touching this code.
    """
    if not filters:
        return None

    from qdrant_client import models

    conditions = []
    for key, value in filters.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple, set)):
            if not value:
                continue
            conditions.append(
                models.FieldCondition(key=key, match=models.MatchAny(any=list(value)))
            )
        else:
            conditions.append(
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
            )

    if not conditions:
        return None
    return models.Filter(must=conditions)


class QdrantVectorStore:
    def __init__(
        self,
        collection_name: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        vector_size: int | None = None,
    ):
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.url = url if url is not None else settings.QDRANT_URL
        self.api_key = api_key if api_key is not None else settings.QDRANT_API_KEY
        self._vector_size = vector_size
        self._client = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            if self.url:
                logger.info("Connecting to Qdrant at %s", self.url)
                self._client = QdrantClient(url=self.url, api_key=self.api_key or None)
            else:
                logger.info("Using in-memory Qdrant instance")
                self._client = QdrantClient(location=":memory:")
        return self._client

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Qdrant health check failed: %s", exc)
            return False

    def ensure_collection(self, vector_size: int | None = None) -> None:
        """Create the collection if it does not exist.

        If it already exists with a different vector size (e.g. model swap)
        it is recreated so dimensionality stays consistent.
        """
        from qdrant_client import models

        size = vector_size or self._vector_size
        if size is None:
            raise VectorStoreError("vector_size must be provided to create a collection")

        existing = self.client.collection_exists(self.collection_name)
        if existing:
            info = self.client.get_collection(self.collection_name)
            current = info.config.params.vectors.size
            if current == size:
                return
            logger.warning(
                "Recreating collection %s: vector size %s -> %s",
                self.collection_name,
                current,
                size,
            )
            self.client.delete_collection(self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=size, distance=models.Distance.COSINE
            ),
        )
        logger.info("Created collection %s (dim=%s)", self.collection_name, size)

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def upsert(self, items: Iterable[tuple[RAGChunk, list[float]]]) -> int:
        from qdrant_client import models

        points = []
        for chunk, vector in items:
            # Qdrant point IDs must be integers or UUIDs. The human-readable
            # deterministic chunk ID remains in the payload and API response.
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        **chunk.metadata,
                        "document_id": chunk.document_id,
                        "chunk_id": chunk.chunk_id,
                        "chunk_index": chunk.chunk_index,
                        "title": chunk.title,
                        "content": chunk.content,
                        "source": chunk.source,
                        "content_type": chunk.content_type,
                        "sacco_id": chunk.sacco_id,
                        "language": chunk.language,
                        "topic": chunk.topic,
                        "audience": chunk.audience,
                        "goals": chunk.goals,
                        "effective_date": chunk.effective_date,
                    },
                )
            )
        if not points:
            return 0
        self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def delete_by_document_id(self, document_id: str) -> int:
        from qdrant_client import models

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    )
                ]
            ),
        )
        return 1

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------
    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_filter = _build_filter(filters)
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        ).points
        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "document_id": payload.get("document_id"),
                    "chunk_id": payload.get("chunk_id"),
                    "title": payload.get("title", ""),
                    "content": payload.get("content", ""),
                    "score": float(hit.score),
                    "source": payload.get("source", ""),
                    "sacco_id": payload.get("sacco_id", ""),
                    "language": payload.get("language", ""),
                    "topic": payload.get("topic", ""),
                    "content_type": payload.get("content_type", ""),
                    "metadata": {
                        k: value
                        for k, value in payload.items()
                        if k
                        not in {
                            "document_id",
                            "chunk_id",
                            "chunk_index",
                            "title",
                            "content",
                            "source",
                            "content_type",
                            "sacco_id",
                            "language",
                            "topic",
                        }
                    },
                }
            )
        return results
