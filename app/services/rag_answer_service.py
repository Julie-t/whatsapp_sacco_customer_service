"""Retrieve evidence and generate a source-grounded answer.

Integrated RAG pipeline with:
- Conversation-aware query reformulation
- Retrieval confidence evaluation
- Answerability checking
- Intelligent fallback taxonomy
- Knowledge gap tracking
"""

import logging
from time import perf_counter
from typing import Optional

from app.ai.llm import LLM
from app.ai.providers.groq import GroqRateLimitError
from app.ai.rag.answerability import AnswerabilityChecker
from app.ai.rag.context import build_context
from app.ai.rag.models import RAGResult
from app.ai.rag.pipeline import RAGPipeline
from app.ai.rag.prompts import grounded_answer_messages
from app.ai.rag.query_rewriter import QueryRewriter
from app.config.settings import settings
from app.core.fallback import FallbackCategory, FallbackHandler, FallbackResponse
from app.core.metrics import record_provider_failure
from app.schemas.message import ConversationTurn
from app.schemas.rag_answer import RAGAnswerResponse, RAGAnswerSource
from app.services.knowledge_gap_service import KnowledgeGapService

logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = (
    "I couldn't find that information in the SACCO knowledge base. "
    "Please contact a SACCO representative for official assistance."
)


class RAGAnswerService:
    """Enhanced RAG answer service with query reformulation, confidence, and fallback logic."""

    def __init__(
        self,
        pipeline: RAGPipeline,
        llm: LLM,
        query_rewriter: Optional[QueryRewriter] = None,
        answerability_checker: Optional[AnswerabilityChecker] = None,
        knowledge_gap_service: Optional[KnowledgeGapService] = None,
    ):
        """Initialize service with required components.

        Args:
            pipeline: RAG retrieval pipeline.
            llm: LLM for generating answers.
            query_rewriter: Optional query reformulation component.
            answerability_checker: Optional answerability evaluator.
            knowledge_gap_service: Optional knowledge gap tracker.
        """
        self.pipeline = pipeline
        self.llm = llm
        self.query_rewriter = query_rewriter or QueryRewriter(llm)
        self.answerability_checker = answerability_checker or AnswerabilityChecker(
            min_retrieval_score=settings.RAG_MIN_SCORE
        )
        self.knowledge_gap_service = knowledge_gap_service or KnowledgeGapService()

    async def answer(
        self,
        query: str,
        sacco_id: str | None = None,
        language: str | None = None,
        content_type: str | None = None,
        topic: str | None = None,
        top_k: int | None = None,
        conversation_history: list[dict] | None = None,
        retrieved_results: list[RAGResult] | None = None,
    ) -> RAGAnswerResponse:
        """Generate a grounded answer to a query.

        Pipeline:
        1. Reformulate query using conversation history
        2. Retrieve relevant evidence
        3. Check answerability
        4. Generate answer or fallback
        5. Track knowledge gaps

        Args:
            query: The user's question.
            sacco_id: SACCO context.
            language: Language filter.
            content_type: Content type filter.
            topic: Topic filter.
            top_k: Number of results.
            conversation_history: Optional prior turns for reformulation.

        Returns:
            RAGAnswerResponse with answer or fallback.
        """
        # Step 1: Query reformulation
        rewrite_started = perf_counter()
        reformulated_query = query
        if conversation_history:
            conversation_turns = [
                ConversationTurn(role=turn.get("role", "user"), content=turn.get("content", ""))
                for turn in conversation_history
            ]
            reformulated_query = await self.query_rewriter.rewrite(
                latest_message=query,
                conversation_history=conversation_turns,
            )
        else:
            # Simple heuristic: check if message looks self-contained
            if not self.query_rewriter._is_self_contained(query):
                logger.debug("Query appears context-dependent but no history provided")

        logger.info("Query reformulation latency: %.3fs", perf_counter() - rewrite_started)

        # Step 2: Retrieval
        retrieval_started = perf_counter()
        results = retrieved_results if retrieved_results is not None else self.pipeline.search(
            query=reformulated_query,
            sacco_id=sacco_id,
            language=language,
            content_type=content_type,
            topic=topic,
            top_k=top_k,
        )
        retrieval_latency = perf_counter() - retrieval_started
        logger.info("RAG retrieval latency: %.3fs | results=%d", retrieval_latency, len(results))

        # Step 3: Answerability check
        decision = self.answerability_checker.check(query, results)
        logger.info(
            "Answerability check: %s (confidence: %.2f)",
            decision.answerable,
            decision.confidence,
        )

        # Extract retrieval confidence
        retrieval_confidence = min([r.score for r in results]) if results else 0.0

        # Step 4: Decide what to do
        if not results:
            # No results - knowledge gap with the explicit no-context contract.
            fallback = FallbackHandler.knowledge_gap(
                query=query,
                suggestion="You can reach out to a SACCO representative who may have more detailed information.",
                metadata={"reformulated_query": reformulated_query},
            )
            logger.info("No retrieval results - knowledge gap fallback")

            # Record knowledge gap
            await self._record_knowledge_gap(
                query=query,
                sacco_id=sacco_id,
                language=language,
                top_retrieval_score=None,
                fallback_reason=FallbackCategory.KNOWLEDGE_GAP,
            )

            return RAGAnswerResponse(
                query=query,
                reformulated_query=reformulated_query,
                answer=NO_CONTEXT_ANSWER,
                sources=[],
                grounded=False,
                no_context=True,
                retrieval_confidence=0.0,
                answerability_confidence=0.0,
                fallback_category=fallback.category,
            )

        if not decision.answerable:
            # Results retrieved but not answerable
            fallback = FallbackHandler.knowledge_gap(
                query=query,
                suggestion="Please try rephrasing your question, or a SACCO representative can help.",
                metadata={
                    "reason": decision.reason,
                    "confidence": decision.confidence,
                    "top_score": retrieval_confidence,
                },
            )
            logger.info("Low answerability (%.2f) - knowledge gap fallback", decision.confidence)

            # Record knowledge gap
            await self._record_knowledge_gap(
                query=query,
                sacco_id=sacco_id,
                language=language,
                top_retrieval_score=retrieval_confidence,
                fallback_reason=FallbackCategory.KNOWLEDGE_GAP,
            )

            return RAGAnswerResponse(
                query=query,
                reformulated_query=reformulated_query,
                answer=fallback.user_message,
                sources=[],
                grounded=False,
                no_context=False,
                retrieval_confidence=retrieval_confidence,
                answerability_confidence=decision.confidence,
                fallback_category=fallback.category,
            )

        # Step 5: Generate answer
        context = build_context(results)
        generation_started = perf_counter()
        try:
            answer = await self.llm.generate(grounded_answer_messages(query, context))
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            record_provider_failure("Groq LLM", "generate", type(exc).__name__)
            fallback = FallbackHandler.provider_failure(
                service_name="Groq LLM",
                error=str(exc),
            )
            return RAGAnswerResponse(
                query=query,
                reformulated_query=reformulated_query,
                answer=fallback.user_message,
                sources=[],
                grounded=False,
                no_context=False,
                retrieval_confidence=retrieval_confidence,
                answerability_confidence=decision.confidence,
                fallback_category=fallback.category,
            )

        logger.info("LLM generation latency: %.3fs", perf_counter() - generation_started)

        # Build sources
        sources = [
            RAGAnswerSource(
                document_id=result.document_id,
                chunk_id=result.chunk_id,
                title=result.title,
                source=result.source,
                score=result.score,
            )
            for result in results
        ]

        logger.info(
            "RAG answer generated successfully | results=%d confidence=%.2f",
            len(results),
            decision.confidence,
        )

        return RAGAnswerResponse(
            query=query,
            reformulated_query=reformulated_query,
            answer=answer,
            sources=sources,
            grounded=True,
            no_context=False,
            retrieval_confidence=retrieval_confidence,
            answerability_confidence=decision.confidence,
            fallback_category=None,
        )

    async def _record_knowledge_gap(
        self,
        query: str,
        sacco_id: str | None,
        language: str | None,
        top_retrieval_score: float | None,
        fallback_reason: FallbackCategory,
    ) -> None:
        """Record a knowledge gap event.

        Args:
            query: The user's query.
            sacco_id: SACCO context.
            language: Language used.
            top_retrieval_score: Best retrieval score if available.
            fallback_reason: Why the query couldn't be answered.
        """
        try:
            await self.knowledge_gap_service.record_gap(
                query=query,
                sacco_id=sacco_id or "unknown",
                language=language or "en",
                top_retrieval_score=top_retrieval_score,
                fallback_reason=fallback_reason,
            )
        except Exception as exc:
            logger.warning("Failed to record knowledge gap: %s", exc)
