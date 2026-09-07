"""Ingest the synthetic RAG test dataset into Qdrant."""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ai.rag.embeddings import SentenceTransformerEmbeddingProvider
from app.ai.rag.ingestion import DocumentIngestor
from app.ai.rag.vector_store import QdrantVectorStore
from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("data/processed/rag_test_data.json"),
        help="JSON document file (synthetic test data by default)",
    )
    args = parser.parse_args()

    provider = SentenceTransformerEmbeddingProvider(settings.EMBEDDING_MODEL)
    store = QdrantVectorStore()
    report = DocumentIngestor(provider, store).ingest_from_json(args.path)

    for label, value in report.as_dict().items():
        print(f"{label.replace('_', ' ').title()}: {value}")


if __name__ == "__main__":
    main()
