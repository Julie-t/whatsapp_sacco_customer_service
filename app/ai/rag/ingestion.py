"""Ingestion pipeline.

Document -> validate -> chunk -> embed (batch) -> attach metadata -> upsert.

Ingestion is idempotent: chunk IDs are derived deterministically from the
document ID and chunk index, and upsert overwrites any previously stored point
with the same ID. Re-running ingestion therefore never creates duplicate chunks.
"""

import json
import logging
from pathlib import Path
from typing import Iterable

from app.ai.rag.chunking import chunk_document
from app.ai.rag.embeddings import EmbeddingProvider
from app.ai.rag.models import RAGChunk, RAGDocument
from app.ai.rag.vector_store import QdrantVectorStore
from app.config.settings import settings

logger = logging.getLogger(__name__)


class IngestionReport:
    def __init__(self):
        self.documents_processed = 0
        self.chunks_created = 0
        self.embeddings_generated = 0
        self.vectors_upserted = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "documents_processed": self.documents_processed,
            "chunks_created": self.chunks_created,
            "embeddings_generated": self.embeddings_generated,
            "vectors_upserted": self.vectors_upserted,
        }


class DocumentIngestor:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
    ):
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        # Ensure the collection exists with the right dimensionality before
        # ingestion begins.
        self.vector_store.ensure_collection(self.embedding_provider.dimension())

    # ------------------------------------------------------------------
    def ingest_document(self, document: RAGDocument, report: IngestionReport) -> list[RAGChunk]:
        chunks = chunk_document(document)
        if not chunks:
            logger.warning("Skipping empty document %s", document.document_id)
            return []

        report.documents_processed += 1
        report.chunks_created += len(chunks)

        # Batch embed all chunk texts.
        texts = [c.content for c in chunks]
        vectors = self.embedding_provider.embed_documents(texts)
        report.embeddings_generated += len(vectors)

        upserted = self.vector_store.upsert(zip(chunks, vectors))
        report.vectors_upserted += upserted
        return chunks

    def ingest_documents(self, documents: Iterable[RAGDocument]) -> IngestionReport:
        report = IngestionReport()
        for document in documents:
            self.ingest_document(document, report)
        logger.info("Ingestion complete: %s", report.as_dict())
        return report

    # ------------------------------------------------------------------
    def ingest_from_json(self, path: str | Path) -> IngestionReport:
        documents = self.load_documents(path)
        return self.ingest_documents(documents)

    @staticmethod
    def load_documents(path: str | Path) -> list[RAGDocument]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Document source not found: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        # Accept either a bare list or {"documents": [...]}.
        if isinstance(raw, dict) and "documents" in raw:
            items = raw["documents"]
        elif isinstance(raw, list):
            items = raw
        else:
            raise ValueError("Unsupported document file format; expected a list of documents.")

        documents: list[RAGDocument] = []
        for item in items:
            if isinstance(item, RAGDocument):
                documents.append(item)
            else:
                values = dict(item)
                values.setdefault("sacco_id", settings.DEFAULT_SACCO_ID)
                documents.append(RAGDocument(**values))
        return documents
