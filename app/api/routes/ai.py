import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.ai.llm import LLM
from app.ai.intent_router import IntentRouter
from app.ai.prompts import SYSTEM_PROMPT
from app.schemas.ai import AICompletionRequest, AICompletionResponse
from app.schemas.intent import RequestTriageResult

logger = logging.getLogger(__name__)
router = APIRouter()

_llm = LLM()
_intent_router = IntentRouter(llm=_llm)


@router.post("/ai/intent", response_model=RequestTriageResult)
async def classify_intent(request: AICompletionRequest):
    return await _intent_router.classify(request.message)


@router.post("/ai/test", response_model=AICompletionResponse)
async def test_ai_completion(request: AICompletionRequest):
    try:
        reply = await _llm.generate(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request.message},
            ]
        )
        return AICompletionResponse(response=reply)
    except RuntimeError as exc:
        logger.error("AI completion failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "AI service is temporarily unavailable."},
        )
