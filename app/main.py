from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import ai as ai_router
from app.api.routes import rag as rag_router
from app.api.routes import whatsapp as whatsapp_router
from app.database.connection import get_connection
from app.core.metrics import snapshot

app = FastAPI(title="SACCO AI Companion")

app.include_router(whatsapp_router.router)
app.include_router(ai_router.router)
app.include_router(rag_router.router)


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
