from fastapi.testclient import TestClient

from app.ai.rag.chunking import chunk_document
from app.ai.rag.embeddings import MockEmbeddingProvider
from app.ai.rag.ingestion import DocumentIngestor
from app.ai.rag.models import RAGDocument
from app.ai.rag.pipeline import RAGPipeline
from app.ai.rag.retriever import Retriever
from app.ai.rag.vector_store import QdrantVectorStore
from app.main import app


def make_documents() -> list[RAGDocument]:
    return [
        RAGDocument(
            document_id="compound",
            title="Compound Interest",
            content="Compound interest grows when interest is calculated on principal and accumulated interest.",
            source="synthetic test data",
            sacco_id="demo_sacco",
            language="en",
            topic="compound_interest",
        ),
        RAGDocument(
            document_id="loan",
            title="Loan Repayment",
            content="Loan repayment uses scheduled instalments that return principal and interest.",
            source="synthetic test data",
            sacco_id="demo_sacco",
            language="en",
            topic="loan_repayment",
        ),
        RAGDocument(
            document_id="membership_sw",
            title="SACCO Membership",
            content="Uanachama wa SACCO unaeleza kujiunga na ushirika na kushiriki kama mwanachama.",
            source="synthetic test data",
            sacco_id="demo_sacco",
            language="sw",
            topic="membership",
        ),
        RAGDocument(
            document_id="english_only",
            title="English Savings",
            content="Savings are funds set aside for future needs.",
            source="synthetic test data",
            sacco_id="demo_sacco",
            language="en",
            topic="savings",
        ),
    ]


def make_pipeline() -> RAGPipeline:
    provider = MockEmbeddingProvider(dimension=128)
    store = QdrantVectorStore(collection_name="test_rag_collection")
    ingestor = DocumentIngestor(provider, store)
    ingestor.ingest_documents(make_documents())
    return RAGPipeline(retriever=Retriever(provider, store, min_score=0.2))


def test_chunking_preserves_metadata_and_ids_are_deterministic():
    document = RAGDocument(
        document_id="doc_001",
        title="Long test document",
        content="one two three four five six seven eight nine ten eleven twelve",
        sacco_id="demo_sacco",
        language="en",
    )
    first = chunk_document(document, chunk_size=30, chunk_overlap=5, chunk_min_size=8)
    second = chunk_document(document, chunk_size=30, chunk_overlap=5, chunk_min_size=8)

    assert first
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert all(chunk.sacco_id == "demo_sacco" for chunk in first)
    assert all(chunk.document_id == "doc_001" for chunk in first)


def test_embeddings_have_consistent_dimension_and_batch_support():
    provider = MockEmbeddingProvider(dimension=32)
    vectors = provider.embed_documents(["compound interest", "loan repayment"])

    assert len(vectors) == 2
    assert all(len(vector) == provider.dimension() for vector in vectors)
    assert len(provider.embed_query("compound interest")) == provider.dimension()


def test_vector_store_insert_and_search():
    provider = MockEmbeddingProvider(dimension=64)
    store = QdrantVectorStore(collection_name="test_vector_store")
    ingestor = DocumentIngestor(provider, store)
    ingestor.ingest_documents(make_documents()[:2])

    hits = store.search(provider.embed_query("compound interest"), top_k=2)

    assert hits
    assert hits[0]["document_id"] == "compound"
    assert hits[0]["chunk_id"] == "compound_chunk_00"


def test_retrieval_ranks_relevant_documents_first():
    pipeline = make_pipeline()

    assert pipeline.search("What is compound interest?")[0].document_id == "compound"
    assert pipeline.search("How does loan repayment work?")[0].document_id == "loan"


def test_metadata_filtering_excludes_other_languages():
    pipeline = make_pipeline()

    results = pipeline.search("SACCO membership", language="sw")

    assert results
    assert all(result.language == "sw" for result in results)


def test_empty_retrieval_returns_no_fabricated_content():
    pipeline = make_pipeline()

    assert pipeline.search("quantum spaceship metallurgy", min_score=0.2) == []


def test_search_endpoint_returns_structured_results(monkeypatch):
    import app.api.routes.rag as rag_route

    monkeypatch.setattr(rag_route, "_pipeline", make_pipeline())
    client = TestClient(app)

    response = client.post(
        "/rag/search",
        json={"query": "What is compound interest?", "sacco_id": "demo_sacco", "top_k": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "What is compound interest?"
    assert body["results"][0]["document_id"] == "compound"
