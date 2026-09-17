import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from pathlib import Path
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)
# Reload triggered to load updated environment configuration


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm models and services on startup to eliminate cold-start latency for webhooks."""
    try:
        from app.ai.rag.pipeline import _default_embedding_provider
        logger.info("Pre-warming embedding model on startup...")
        provider = _default_embedding_provider()
        provider.embed_query("warmup")
        logger.info("Embedding model warmed up successfully.")

        from app.services.conversations.conversation_service import (
            _get_rag_answer_service,
            _get_query_rewriter,
            _get_education_service,
        )
        _get_rag_answer_service()
        _get_query_rewriter()
        _get_education_service()
        logger.info("Conversation services pre-warmed.")
    except Exception as exc:
        logger.warning("Startup model warmup skipped or failed: %s", exc)
    yield


app = FastAPI(title="SACCO AI Companion & Admin Operations", lifespan=lifespan)

from app.api.routes import admin as admin_router
from app.api.routes import ai as ai_router
from app.api.routes import education as education_router
from app.api.routes import goals as goals_router
from app.api.routes import intelligence as intelligence_router
from app.api.routes import member_auth as member_auth_router
from app.api.routes import members as members_router
from app.api.routes import proactive as proactive_router
from app.api.routes import rag as rag_router
from app.api.routes import sacco_sandbox as sacco_sandbox_router
from app.api.routes import whatsapp as whatsapp_router
from app.database.connection import get_connection
from app.core.metrics import snapshot


app.include_router(whatsapp_router.router)
app.include_router(ai_router.router)
app.include_router(rag_router.router)
app.include_router(members_router.router)
app.include_router(goals_router.router)
app.include_router(education_router.router)
app.include_router(proactive_router.router)
app.include_router(intelligence_router.router)
app.include_router(admin_router.router)
app.include_router(member_auth_router.router)
app.include_router(sacco_sandbox_router.router)

dashboard_path = Path(__file__).parent / "static" / "dashboard"
if dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")



@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/readiness")
def readiness():
    """Report whether required persistent dependencies are reachable."""
    checks = {"database": "ok"}
    try:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        checks["database"] = "unavailable"
    status = "ready" if checks["database"] == "ok" else "not_ready"
    response = {"status": status, "checks": checks}
    if status != "ready":
        return JSONResponse(status_code=503, content=response)
    return response


@app.get("/metrics")
def metrics():
    """Return process-local counters for lightweight operational monitoring."""
    return snapshot()
