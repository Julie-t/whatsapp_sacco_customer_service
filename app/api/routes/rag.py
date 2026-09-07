import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.ai.llm import LLM
from app.ai.rag.pipeline import RAGPipeline
from app.schemas.rag_answer import RAGAnswerRequest, RAGAnswerResponse
from app.services.rag_answer_service import RAGAnswerService
from app.schemas.rag import RAGSearchRequest, RAGSearchResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Development/testing-only retrieval endpoint. Intentionally does NOT generate
# answers; it returns ranked evidence from the vector store.
#
# The pipeline is constructed lazily on first request so importing this router
# never triggers a heavy embedding-model download (which would otherwise break
# unrelated tests and cold imports).
_pipeline: RAGPipeline | None = None
_answer_service: RAGAnswerService | None = None


def _get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


def _get_answer_service() -> RAGAnswerService:
    global _answer_service
    if _answer_service is None:
        _answer_service = RAGAnswerService(_get_pipeline(), LLM())
    return _answer_service


@router.post("/rag/search", response_model=RAGSearchResponse)
def rag_search(request: RAGSearchRequest) -> RAGSearchResponse:
    results = _get_pipeline().search(
        query=request.query,
        sacco_id=request.sacco_id,
        language=request.language,
        content_type=request.content_type,
        topic=request.topic,
        top_k=request.top_k,
        min_score=request.min_score,
        filters=request.filters,
    )
    return RAGSearchResponse(
        query=request.query,
        results=[r.model_dump() for r in results],
    )


@router.post("/rag/answer", response_model=RAGAnswerResponse)
async def rag_answer(request: RAGAnswerRequest) -> RAGAnswerResponse:
    try:
        return await _get_answer_service().answer(
            query=request.query,
            sacco_id=request.sacco_id,
            language=request.language,
            content_type=request.content_type,
            topic=request.topic,
            top_k=request.top_k,
            conversation_history=request.conversation_history,
        )
    except Exception as exc:
        logger.error("Grounded RAG answer failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "provider_failure",
                    "message": "The AI service is temporarily unavailable.",
                }
            },
        )
