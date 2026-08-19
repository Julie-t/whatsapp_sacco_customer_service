import json
import logging

from app.ai.nvidia import LLM
from app.ai.prompts import INTENT_CLASSIFIER_PROMPT
from app.schemas.intent import IntentResult

logger = logging.getLogger(__name__)


class IntentRouter:
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or LLM()

    async def classify(self, message: str) -> IntentResult:
        try:
            raw_response = await self.llm.generate(
                [
                    {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                    {"role": "user", "content": message},
                ]
            )
            return IntentResult.model_validate(json.loads(raw_response))
        except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
            logger.warning("Intent classification failed safely: %s", exc)
            return IntentResult.fallback()