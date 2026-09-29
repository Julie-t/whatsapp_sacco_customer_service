import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.ai.providers.groq_audio import GroqAudioProvider
from app.config.settings import settings
from app.schemas.message import IncomingWhatsAppMessage

logger = logging.getLogger(__name__)

# User-facing fallback messages (Bilingual Kiswahili & English)
VOICE_UNINTELLIGIBLE_MESSAGE = (
    "Samahani, sikuweza kusikia sauti yako vizuri. "
    "Tafadhali jaribu kurekodi tena au andika ujumbe wako kwa maneno.\n\n"
    "Sorry, I couldn't hear your voice note clearly. "
    "Please try recording again or type your message."
)

VOICE_PROCESSING_ERROR_MESSAGE = (
    "Samahani, kumetokea hitilafu ya kiufundi wakati wa kusikiliza ujumbe wako wa sauti. "
    "Tafadhali andika ujumbe wako kwa maneno au ujaribu tena baadaye.\n\n"
    "Sorry, there was an issue processing your voice note. "
    "Please type your message or try again in a moment."
)

NON_AUDIO_MEDIA_MESSAGE = (
    "Samahani, kwa sasa naweza kusaidia kwa ujumbe wa maandishi na sauti (voice notes) pekee. "
    "Tafadhali uliza swali lako kwa sauti au uandike.\n\n"
    "I currently only support text and voice note messages. "
    "Please send your question as a voice note or text."
)


@dataclass
class VoiceTranscriptionResult:
    """Result of audio download and transcription."""

    success: bool
    text: str = ""
    language: str | None = None
    duration: float | None = None
    user_fallback_message: str | None = None
    error_detail: str | None = None


def is_audio_content_type(content_type: str | None) -> bool:
    """Check if the MIME type represents an audio file."""
    if not content_type:
        return False
    lower = content_type.lower()
    return (
        lower.startswith("audio/")
        or "audio" in lower
        or "ogg" in lower
        or "amr" in lower
        or "mp4" in lower
    )


class VoiceService:
    """Service for handling WhatsApp voice messages.

    Coordinates:
    1. Authenticated media download from Twilio
    2. Audio validation (MIME, size)
    3. Whisper transcription with Groq (whisper-large-v3-turbo)
    4. Code-switched Swahili, Sheng, and English vocabulary handling
    """

    def __init__(self, audio_provider: GroqAudioProvider | None = None):
        self._audio_provider = audio_provider or GroqAudioProvider()

    async def download_media(
        self,
        media_url: str,
        expected_content_type: str | None = None,
    ) -> tuple[bytes, str]:
        """Download media file from Twilio.

        Args:
            media_url: Direct media URL provided in Twilio webhook payload.
            expected_content_type: MediaContentType reported by Twilio.

        Returns:
            Tuple of (file_bytes, content_type)
        """
        auth = None
        if settings.twilio_account_sid and settings.twilio_auth_token:
            auth = (settings.twilio_account_sid, settings.twilio_auth_token)

        timeout = httpx.Timeout(settings.VOICE_DOWNLOAD_TIMEOUT_SECONDS, connect=5.0)

        # Twilio redirects to Amazon S3 signed URLs, so follow_redirects=True is required
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(media_url, auth=auth)
            response.raise_for_status()

            content_type = response.headers.get("content-type") or expected_content_type or "audio/ogg"
            data = response.content

            if len(data) > settings.MAX_AUDIO_SIZE_BYTES:
                raise ValueError(
                    f"Audio file size ({len(data)} bytes) exceeds limit of {settings.MAX_AUDIO_SIZE_BYTES} bytes"
                )

            return data, content_type

    async def process_voice_message(
        self,
        message: IncomingWhatsAppMessage,
    ) -> VoiceTranscriptionResult:
        """Process an incoming WhatsApp message with voice/audio media.

        Transcribes the audio into text using whisper-large-v3-turbo with
        Kenyan SACCO, Swahili, and Sheng context biasing.
        """
        if not settings.VOICE_ENABLED:
            logger.warning("Voice processing attempted but VOICE_ENABLED is False")
            return VoiceTranscriptionResult(
                success=False,
                user_fallback_message=VOICE_PROCESSING_ERROR_MESSAGE,
                error_detail="VOICE_ENABLED is False",
            )

        if not message.media_url:
            return VoiceTranscriptionResult(
                success=False,
                user_fallback_message=VOICE_PROCESSING_ERROR_MESSAGE,
                error_detail="No media_url provided",
            )

        # Validate that the media is indeed audio
        if not is_audio_content_type(message.media_content_type):
            logger.info(
                "Incoming media is non-audio: content_type=%s",
                message.media_content_type,
            )
            return VoiceTranscriptionResult(
                success=False,
                user_fallback_message=NON_AUDIO_MEDIA_MESSAGE,
                error_detail=f"Unsupported media type: {message.media_content_type}",
            )

        # 1. Download audio file
        try:
            audio_bytes, content_type = await self.download_media(
                message.media_url,
                expected_content_type=message.media_content_type,
            )
        except Exception as exc:
            logger.exception("Failed to download voice media from %s: %s", message.media_url, exc)
            return VoiceTranscriptionResult(
                success=False,
                user_fallback_message=VOICE_PROCESSING_ERROR_MESSAGE,
                error_detail=f"Download error: {exc}",
            )

        # 2. Transcribe via Groq Whisper
        try:
            # Determine appropriate file extension for Whisper API upload
            extension = "ogg"
            if "mp4" in content_type:
                extension = "mp4"
            elif "amr" in content_type:
                extension = "amr"
            elif "wav" in content_type:
                extension = "wav"
            elif "mpeg" in content_type or "mp3" in content_type:
                extension = "mp3"

            filename = f"voice_note.{extension}"

            result = await self._audio_provider.transcribe(
                audio_bytes=audio_bytes,
                filename=filename,
                content_type=content_type,
                prompt=settings.VOICE_PROMPT_BIAS,
            )

            raw_text = (result.get("text") or "").strip()

            if not raw_text:
                logger.warning("Whisper returned empty transcription for voice from %s", message.from_number)
                return VoiceTranscriptionResult(
                    success=False,
                    user_fallback_message=VOICE_UNINTELLIGIBLE_MESSAGE,
                    error_detail="Empty transcription",
                )

            logger.info(
                "Successfully transcribed voice message from %s: text=%r language=%s",
                message.from_number,
                raw_text[:100],
                result.get("language"),
            )

            return VoiceTranscriptionResult(
                success=True,
                text=raw_text,
                language=result.get("language"),
                duration=result.get("duration"),
            )

        except Exception as exc:
            logger.exception("Whisper transcription failed for voice from %s: %s", message.from_number, exc)
            return VoiceTranscriptionResult(
                success=False,
                user_fallback_message=VOICE_PROCESSING_ERROR_MESSAGE,
                error_detail=f"Transcription error: {exc}",
            )
