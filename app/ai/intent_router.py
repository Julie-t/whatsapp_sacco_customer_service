import json
import logging

from app.ai.nvidia import LLM
from app.ai.prompts import ROUTER_PROMPT
from app.schemas.intent import RequestTriageResult

logger = logging.getLogger(__name__)


class IntentRouter:
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or LLM()

    async def classify(self, message: str) -> RequestTriageResult:
        try:
            raw_response = await self.llm.generate(
                [
                    {"role": "system", "content": ROUTER_PROMPT},
                    {"role": "user", "content": message},
                ]
            )
            return RequestTriageResult.model_validate(json.loads(raw_response))
        except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
            logger.warning("Request triage failed safely: %s", exc)
            return RequestTriageResult.fallback()