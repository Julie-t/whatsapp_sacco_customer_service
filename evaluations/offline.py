"""Offline evaluation utilities including demo-data seeding."""

from pathlib import Path

from app.ai.rag.embeddings import SentenceTransformerEmbeddingProvider
from app.ai.rag.ingestion import DocumentIngestor
from app.ai.rag.vector_store import QdrantVectorStore
from app.config.settings import settings


def seed_demo_store(demo_data_path: str | Path = "data/processed/rag_test_data.json") -> QdrantVectorStore:
    """Load demo SACCO documents into an in-memory Qdrant store for offline evaluation.
    
    Returns the populated store ready for retrieval.
    """
    store = QdrantVectorStore(url="")
    provider = SentenceTransformerEmbeddingProvider(settings.EMBEDDING_MODEL)
    ingestor = DocumentIngestor(provider, store)
    ingestor.ingest_from_json(demo_data_path)
    return store
