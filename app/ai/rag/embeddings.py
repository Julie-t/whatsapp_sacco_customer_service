"""Embedding provider abstraction.

The retriever/vector store depend only on :class:`EmbeddingProvider`. The
concrete implementation may be a local sentence-transformers model, a remote
API, or a deterministic mock for offline tests. This module is intentionally
NOT coupled to NVIDIA.
"""

from abc import ABC, abstractmethod
from typing import List

import logging

logger = logging.getLogger(__name__)

Vector = List[float]


class EmbeddingProvider(ABC):
    """Application-level abstraction for turning text into vectors."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of produced vectors."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[Vector]:
        """Embed a batch of documents."""

    @abstractmethod
    def embed_query(self, text: str) -> Vector:
        """Embed a single query."""

    # Convenience helper shared by all providers.
    def embed(self, text: str) -> Vector:
        return self.embed_query(text)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers embedding provider.

    The model is loaded lazily on first use so importing this module never
    triggers a download. After the model is available everything runs locally
    with no network dependency.
    """

    def __init__(self, model_name: str, device: str | None = None, cache_folder: str | None = None):
        self.model_name = model_name
        self.device = device
        self.cache_folder = cache_folder
        self._model = None
        self._dimension: int | None = None

    def _ensure_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - dependency optional
            raise RuntimeError(
                "sentence-transformers is not installed. Install it to use "
                "SentenceTransformerEmbeddingProvider."
            ) from exc

        logger.info("Loading embedding model: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name, device=self.device, cache_folder=self.cache_folder)
        self._dimension = int(self._model.get_sentence_embedding_dimension())

    def dimension(self) -> int:
        self._ensure_model()
        return self._dimension  # type: ignore[return-value]

    def embed_documents(self, texts: List[str]) -> List[Vector]:
        self._ensure_model()
        embeddings = self._model.encode(  # type: ignore[union-attr]
            texts, convert_to_numpy=True, normalize_embeddings=True
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> Vector:
        return self.embed_documents([text])[0]


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, offline embedding provider for tests and local dev.

    It builds a bag-of-words vector over hashed token positions and L2
    normalizes it. Cosine similarity therefore correlates with lexical
    overlap, which is enough to exercise chunking, retrieval, filtering and
    ranking without downloading any model.
    """

    def __init__(self, dimension: int = 384, seed: int = 0):
        self._dimension = dimension
        self._seed = seed

    def dimension(self) -> int:
        return self._dimension

    _STOPWORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in",
        "on", "for", "and", "or", "with", "what", "how", "does", "do", "did",
        "my", "your", "our", "their", "this", "that", "it", "at", "by", "from",
        "as", "i", "you", "we", "they", "he", "she", "me", "us",
    }

    def _embed(self, text: str) -> Vector:
        import hashlib
        import re

        vector = [0.0] * self._dimension
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            if token in self._STOPWORDS or len(token) < 3:
                continue
            digest = hashlib.md5((str(self._seed) + token).encode("utf-8")).digest()
            idx = int.from_bytes(digest[:8], "big") % self._dimension
            vector[idx] += 1.0
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    def embed_documents(self, texts: List[str]) -> List[Vector]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> Vector:
        return self._embed(text)
