from fastapi import FastAPI

from app.api.routes import ai as ai_router
from app.api.routes import whatsapp as whatsapp_router

app = FastAPI(title="SACCO AI Companion")

app.include_router(whatsapp_router.router)
app.include_router(ai_router.router)


@app.get("/health")
def health():
    return {"status": "healthy"}
