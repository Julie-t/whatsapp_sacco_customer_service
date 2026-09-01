import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)


class GroqProvider:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = settings.GROQ_BASE_URL.rstrip("/")
        self.model = settings.GROQ_MODEL

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
        }

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
                raise RuntimeError("Groq rate limit exceeded") from exc
            if status == 404:
                raise RuntimeError(f"Groq model not found: {self.model}") from exc
            raise RuntimeError(f"Groq API error: {status}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("Groq request timed out") from exc
        except httpx.RequestError as exc:
            raise RuntimeError("Groq network error") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected Groq response format") from exc