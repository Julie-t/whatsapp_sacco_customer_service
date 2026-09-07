import json
import logging
import re

from app.ai.llm import LLM
from app.ai.prompts import ROUTER_PROMPT
from app.schemas.intent import RequestTriageResult

logger = logging.getLogger(__name__)


def _parse_triage_response(raw_response: str) -> RequestTriageResult:
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))
    return RequestTriageResult.model_validate(payload)


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
            return _parse_triage_response(raw_response)
        except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as exc:
            logger.warning("Request triage failed safely: %s", exc)
            return RequestTriageResult.fallback()