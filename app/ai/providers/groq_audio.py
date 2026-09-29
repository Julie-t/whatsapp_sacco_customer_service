import asyncio
import logging
from typing import Any

import httpx

from app.config.settings import settings
from app.ai.providers.groq import GroqRateLimitError, _is_tpd_exhausted, _retry_after_seconds

logger = logging.getLogger(__name__)


class GroqAudioProvider:
    """Async client for Groq Audio Speech-to-Text using Whisper models.

    Specifically supports whisper-large-v3-turbo with trilingual prompt biasing
    for Swahili, Sheng, and English code-switching.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int | None = None,
    ):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.base_url = (base_url or settings.GROQ_BASE_URL).rstrip("/")
        self.model = model or settings.GROQ_AUDIO_MODEL
        self.max_retries = (
            settings.EVAL_PROVIDER_MAX_RETRIES if max_retries is None else max_retries
        )

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg",
        content_type: str = "audio/ogg",
        prompt: str | None = None,
        language: str | None = None,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Transcribe audio bytes using Groq Whisper.

        Args:
            audio_bytes: Raw binary content of the audio file.
            filename: Name of the file, e.g. "voice_note.ogg".
            content_type: MIME type, e.g. "audio/ogg", "audio/mp4".
            prompt: Contextual biasing prompt to prime vocabulary (Sheng, Swahili, SACCO terms).
            language: Optional ISO 639-1 language code (e.g. 'sw', 'en').
                      If None, Whisper auto-detects language dynamically.
            temperature: Sampling temperature (0.0 for deterministic transcription).

        Returns:
            Dictionary containing at minimum 'text', and optionally 'language', 'duration', etc.
        """
        api_key = self.api_key or settings.GROQ_API_KEY
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        url = f"{self.base_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        # Form data fields
        data: dict[str, Any] = {
            "model": self.model,
            "response_format": "verbose_json",
            "temperature": str(temperature),
        }

        effective_prompt = prompt if prompt is not None else settings.VOICE_PROMPT_BIAS
        if effective_prompt:
            data["prompt"] = effective_prompt

        if language:
            data["language"] = language

        # Clean content-type (strip parameters like codecs=opus for the upload header if needed)
        clean_content_type = content_type.split(";")[0].strip() if content_type else "audio/ogg"

        files = {
            "file": (filename, audio_bytes, clean_content_type),
        }

        timeout = httpx.Timeout(settings.VOICE_TRANSCRIBE_TIMEOUT_SECONDS, connect=10.0)

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        data=data,
                        files=files,
                        headers=headers,
                    )

                    if response.status_code != 200:
                        logger.error(
                            "Groq Audio API error: status=%s url=%s body=%s",
                            response.status_code,
                            url,
                            response.text[:500],
                        )

                    response.raise_for_status()
                    result = response.json()
                    logger.info(
                        "Groq audio transcription succeeded: model=%s language=%s duration=%.2fs",
                        self.model,
                        result.get("language"),
                        result.get("duration", 0.0),
                    )
                    return result

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 429:
                    if _is_tpd_exhausted(exc.response):
                        logger.error("Groq rate limit: TPD exhausted on audio transcription.")
                        raise GroqRateLimitError(
                            "Groq audio daily token limit reached",
                            limit_type="TPD",
                        ) from exc

                    delay = _retry_after_seconds(exc.response)
                    if delay is None:
                        delay = min(
                            settings.EVAL_PROVIDER_MAX_RETRY_DELAY,
                            settings.EVAL_PROVIDER_MIN_RETRY_DELAY * (2**attempt),
                        )
                    if attempt < self.max_retries:
                        logger.warning(
                            "Groq 429 rate limit hit on audio, retrying in %.2fs (attempt %d/%d)",
                            delay,
                            attempt + 1,
                            self.max_retries,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise GroqRateLimitError(
                        "Groq audio rate limit exceeded",
                        retry_after=delay,
                        limit_type="RPM_OR_TPM",
                    ) from exc

                # For 4xx errors other than 429, don't retry blindly
                if 400 <= status_code < 500:
                    logger.error("Groq audio transcription client error %d: %s", status_code, exc.response.text)
                    raise

                if attempt < self.max_retries:
                    delay = min(
                        settings.EVAL_PROVIDER_MAX_RETRY_DELAY,
                        settings.EVAL_PROVIDER_MIN_RETRY_DELAY * (2**attempt),
                    )
                    logger.warning(
                        "Groq audio HTTP error %s, retrying in %.2fs (attempt %d/%d)",
                        status_code,
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            except (httpx.RequestError, asyncio.TimeoutError) as exc:
                if attempt < self.max_retries:
                    delay = min(
                        settings.EVAL_PROVIDER_MAX_RETRY_DELAY,
                        settings.EVAL_PROVIDER_MIN_RETRY_DELAY * (2**attempt),
                    )
                    logger.warning(
                        "Groq audio request error: %s, retrying in %.2fs (attempt %d/%d)",
                        exc,
                        delay,
                        attempt + 1,
                        self.max_retries,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise
