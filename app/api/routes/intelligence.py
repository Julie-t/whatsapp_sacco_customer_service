"""API routes for SACCO management intelligence and news ingestion."""

from typing import Optional
from fastapi import APIRouter, Query, status

from app.database.engagement_repository import EngagementRepository
from app.models.engagement import FinancialNewsArticle, NewsCategory
from app.schemas.engagement import (
    KnowledgeGapIntelligenceSummary,
    NewsArticleCreate,
    NewsArticleRead,
)
from app.services.rag.knowledge_gap_intelligence_service import KnowledgeGapIntelligenceService
from app.services.rag.postgres_knowledge_gap_repository import PostgresKnowledgeGapRepository

router = APIRouter(prefix="/intelligence", tags=["SACCO Intelligence"])


def get_engagement_repo() -> EngagementRepository:
    return EngagementRepository()


def get_intelligence_service() -> KnowledgeGapIntelligenceService:
    repo = PostgresKnowledgeGapRepository()
    return KnowledgeGapIntelligenceService(gap_repo=repo)


@router.get(
    "/knowledge-gaps/summary",
    response_model=KnowledgeGapIntelligenceSummary,
    summary="Get executive summary of top member confusion topics and actionable recommendations",
)
async def get_knowledge_gaps_summary(
    sacco_id: str = Query("demo_sacco", description="Target SACCO ID"),
    limit: int = Query(100, ge=1, le=500, description="Max gaps to analyze"),
):
    svc = get_intelligence_service()
    return await svc.generate_summary(sacco_id=sacco_id, limit=limit)


@router.post(
    "/news/ingest",
    response_model=NewsArticleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and approve a trusted financial news article",
)
def ingest_news_article(article_in: NewsArticleCreate):
    repo = get_engagement_repo()
    article = FinancialNewsArticle(
        id=article_in.id or "",
        source=article_in.source,
        title=article_in.title,
        content=article_in.content,
        summary=article_in.summary,
        category=article_in.category,
        url=article_in.url,
        published_at=article_in.published_at,
        expiry_at=article_in.expiry_at,
        is_approved=article_in.is_approved,
    )
    saved = repo.add_article(article)
    return saved


@router.get(
    "/news",
    response_model=list[NewsArticleRead],
    summary="List active, unexpired approved financial news articles",
)
def list_active_news(category: Optional[str] = Query(None, description="Filter by category")):
    repo = get_engagement_repo()
    return repo.list_active_articles(category=category)
