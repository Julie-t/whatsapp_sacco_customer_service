import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _run_warmup():
    """Synchronous warmup of embedding models and singletons."""
    try:
        from app.ai.rag.pipeline import _default_embedding_provider
        provider = _default_embedding_provider()
        provider.embed_query("warmup")
    except Exception as exc:
        logger.warning("Startup embedding model warmup skipped or failed: %s", exc)

    try:
        from app.services.conversations.conversation_service import (
            _get_rag_answer_service,
            _get_query_rewriter,
            _get_education_service,
        )
        _get_rag_answer_service()
        _get_query_rewriter()
        _get_education_service()
    except Exception as exc:
        logger.warning("Conversation services warmup skipped or failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm models and services on startup with a strict timeout to ensure fast boot."""
    t0 = perf_counter()
    logger.info("Application starting up: running pre-warming routines...")
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_warmup), timeout=12.0)
        logger.info("Pre-warming routines completed in %.2fs.", perf_counter() - t0)
    except asyncio.TimeoutError:
        logger.warning("Startup pre-warming timed out after 12s; continuing boot without blocking.")
    except Exception as exc:
        logger.warning("Startup pre-warming encountered an error: %s", exc)

    logger.info("Total startup time: %.2fs. Application is ready to receive requests.", perf_counter() - t0)
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


@app.get("/")
def root():
    """Root landing: redirect to the interactive dashboard if available."""
    if dashboard_path.exists():
        return RedirectResponse(url="/dashboard")
    return {
        "status": "online",
        "service": "SACCO AI Companion & Admin Operations",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return empty response for browser favicon requests to avoid 404 noise."""
    return Response(status_code=204)


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
