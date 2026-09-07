import asyncio
import logging
import re

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


class GroqRateLimitError(RuntimeError):
    """Raised after bounded retries are exhausted for a Groq 429 response."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _retry_after_seconds(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    if header:
        try:
            return max(0.0, float(header))
        except ValueError:
            pass

    match = re.search(
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
        response.text,
        re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


class GroqProvider:
    def __init__(self, max_retries: int | None = None):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = settings.GROQ_BASE_URL.rstrip("/")
        self.model = settings.GROQ_MODEL
        self.max_retries = (
            settings.EVAL_PROVIDER_MAX_RETRIES if max_retries is None else max_retries
        )

    async def generate(self, messages: list[dict]) -> str:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": settings.RAG_ANSWER_MAX_TOKENS,
            "temperature": settings.RAG_ANSWER_TEMPERATURE,
            "reasoning_effort": settings.GROQ_REASONING_EFFORT,
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code != 200:
                        logger.error(
                            "Groq API error: status=%s url=%s body=%s",
                            response.status_code,
                            url,
                            response.text[:500],
                        )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 401:
                    raise RuntimeError("Groq authentication failed") from exc
                if status == 429:
                    retry_after = _retry_after_seconds(exc.response)
                    if attempt < self.max_retries:
                        delay = retry_after or settings.EVAL_PROVIDER_MIN_RETRY_DELAY
                        delay = min(
                            max(delay, settings.EVAL_PROVIDER_MIN_RETRY_DELAY),
                            settings.EVAL_PROVIDER_MAX_RETRY_DELAY,
                        )
                        logger.warning(
                            "Groq rate limit hit; waiting %.2fs before retry %s/%s",
                            delay,
                            attempt + 1,
                            self.max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise GroqRateLimitError(
                        "Groq rate limit exceeded after bounded retries",
                        retry_after=retry_after,
                    ) from exc
                if status == 404:
                    raise RuntimeError(f"Groq model not found: {self.model}") from exc
                raise RuntimeError(f"Groq API error: {status}") from exc
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(settings.EVAL_PROVIDER_MIN_RETRY_DELAY)
                    continue
                raise RuntimeError("Groq request timed out") from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(settings.EVAL_PROVIDER_MIN_RETRY_DELAY)
                    continue
                raise RuntimeError("Groq network error") from exc
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError("Unexpected Groq response format") from exc

        raise RuntimeError("Groq request failed after retries")
