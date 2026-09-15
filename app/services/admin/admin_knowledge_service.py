"""Admin Knowledge Service: Manages SACCO policy drafts, approval lifecycle, and Qdrant RAG sync."""

import logging
import uuid
from typing import Optional

from app.ai.rag.embeddings import SentenceTransformerEmbeddingProvider
from app.ai.rag.ingestion import DocumentIngestor, IngestionReport
from app.ai.rag.models import RAGDocument
from app.ai.rag.vector_store import QdrantVectorStore
from app.config.settings import settings
from app.database.admin_repository import AdminRepository
from app.models.admin import KnowledgeDocument, KnowledgeDocumentStatus
from app.schemas.admin import KnowledgeDocumentCreate, KnowledgeDocumentUpdate

logger = logging.getLogger(__name__)


class AdminKnowledgeService:
    def __init__(
        self,
        repo: Optional[AdminRepository] = None,
        embedding_provider: Optional[SentenceTransformerEmbeddingProvider] = None,
        vector_store: Optional[QdrantVectorStore] = None,
    ):
        self.repo = repo or AdminRepository()
        self._provider = embedding_provider
        self._store = vector_store

    def _get_ingestor(self) -> DocumentIngestor:
        provider = self._provider or SentenceTransformerEmbeddingProvider(settings.EMBEDDING_MODEL)
        store = self._store or QdrantVectorStore()
        return DocumentIngestor(provider, store)

    def create_draft(
        self,
        doc_in: KnowledgeDocumentCreate,
        created_by: str,
        sacco_id: str = "demo_sacco",
    ) -> KnowledgeDocument:
        """Create a new SACCO policy document in draft state."""
        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        doc = self.repo.create_knowledge_document(
            id=doc_id,
            title=doc_in.title,
            category=doc_in.category,
            content=doc_in.content,
            sacco_id=sacco_id,
            created_by=created_by,
            effective_date=doc_in.effective_date,
        )
        self.repo.record_audit(
            action="create_draft",
            resource_type="knowledge_document",
            resource_id=doc_id,
            admin_id=created_by,
            sacco_id=sacco_id,
            details={"title": doc_in.title, "category": doc_in.category},
        )
        return doc

    def list_documents(
        self,
        sacco_id: str = "demo_sacco",
        status: Optional[KnowledgeDocumentStatus] = None,
    ) -> list[KnowledgeDocument]:
        return self.repo.list_knowledge_documents(sacco_id=sacco_id, status=status)

    def get_document(self, doc_id: str, sacco_id: str = "demo_sacco") -> Optional[KnowledgeDocument]:
        return self.repo.get_knowledge_document(doc_id=doc_id, sacco_id=sacco_id)

    def approve_and_ingest(
        self,
        doc_id: str,
        approved_by: str,
        sacco_id: str = "demo_sacco",
    ) -> Optional[KnowledgeDocument]:
        """Mark document approved and immediately synchronize embeddings into Qdrant."""
        doc = self.repo.get_knowledge_document(doc_id=doc_id, sacco_id=sacco_id)
        if not doc:
            return None

        # 1. Update database record to approved
        approved_doc = self.repo.mark_document_approved(
            doc_id=doc_id,
            approved_by=approved_by,
            sacco_id=sacco_id,
        )
        if not approved_doc:
            return None

        # 2. Ingest into Qdrant Vector Store
        try:
            rag_doc = RAGDocument(
                document_id=approved_doc.id,
                title=approved_doc.title,
                content=approved_doc.content,
                category=approved_doc.category,
                sacco_id=sacco_id,
                effective_date=approved_doc.effective_date.isoformat(),
            )
            ingestor = self._get_ingestor()
            report = IngestionReport()
            ingestor.ingest_document(rag_doc, report)
            logger.info(
                "Document %s approved and ingested: %s chunks upserted to Qdrant",
                doc_id,
                report.vectors_upserted,
            )
        except Exception as exc:
            logger.warning("Failed to upsert approved doc %s to Qdrant: %s", doc_id, exc)

        # 3. Audit log
        self.repo.record_audit(
            action="approve_and_ingest",
            resource_type="knowledge_document",
            resource_id=doc_id,
            admin_id=approved_by,
            sacco_id=sacco_id,
            details={"title": approved_doc.title, "status": "approved"},
        )
        return approved_doc
