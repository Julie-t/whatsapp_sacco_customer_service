import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.ai.providers.groq_audio import GroqAudioProvider
from app.config.settings import settings
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversations.conversation_service import handle_message_async
from app.services.conversations.response import GREETING_MESSAGE, MEDIA_NOT_SUPPORTED
from app.services.voice.voice_service import (
    NON_AUDIO_MEDIA_MESSAGE,
    VOICE_PROCESSING_ERROR_MESSAGE,
    VOICE_UNINTELLIGIBLE_MESSAGE,
    VoiceService,
    VoiceTranscriptionResult,
    is_audio_content_type,
)


# ---------------------------------------------------------------------------
# 1. MIME Type and Content Detection Tests
# ---------------------------------------------------------------------------
def test_is_audio_content_type():
    assert is_audio_content_type("audio/ogg") is True
    assert is_audio_content_type("audio/ogg; codecs=opus") is True
    assert is_audio_content_type("audio/mp4") is True
    assert is_audio_content_type("audio/amr") is True
    assert is_audio_content_type("audio/mpeg") is True
    assert is_audio_content_type("audio/wav") is True

    # Non-audio formats
    assert is_audio_content_type("image/jpeg") is False
    assert is_audio_content_type("image/png") is False
    assert is_audio_content_type("application/pdf") is False
    assert is_audio_content_type("text/plain") is False
    assert is_audio_content_type("") is False
    assert is_audio_content_type(None) is False


# ---------------------------------------------------------------------------
# 2. GroqAudioProvider Unit Tests
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_groq_audio_provider_transcribe_success():
    provider = GroqAudioProvider(api_key="test-key", model="whisper-large-v3-turbo")

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "text": "Nataka kujua kuhusu mikopo ya dharura",
        "language": "sw",
        "duration": 3.42,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response

        result = await provider.transcribe(
            audio_bytes=b"fake-audio-bytes",
            filename="voice_note.ogg",
            content_type="audio/ogg; codecs=opus",
            prompt="Test prompt",
        )

        assert result["text"] == "Nataka kujua kuhusu mikopo ya dharura"
        assert result["language"] == "sw"
        assert result["duration"] == 3.42

        # Verify call arguments
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["model"] == "whisper-large-v3-turbo"
        assert kwargs["data"]["prompt"] == "Test prompt"
        assert "file" in kwargs["files"]


@pytest.mark.anyio
async def test_groq_audio_provider_uses_default_sacco_prompt_bias():
    provider = GroqAudioProvider(api_key="test-key")

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"text": "Habari SACCO", "language": "sw"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response

        await provider.transcribe(
            audio_bytes=b"fake-audio",
            prompt=None,  # triggers settings.VOICE_PROMPT_BIAS
        )

        _, kwargs = mock_post.call_args
        # Should include Kenyan SACCO Sheng & Swahili bias
        assert "Sheng" in kwargs["data"]["prompt"]
        assert "chama" in kwargs["data"]["prompt"]
        assert "mkopo" in kwargs["data"]["prompt"]


# ---------------------------------------------------------------------------
# 3. VoiceService Unit Tests
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_voice_service_rejects_non_audio():
    service = VoiceService()
    message = IncomingWhatsAppMessage(
        from_number="+254700000000",
        media_url="https://api.twilio.com/media/image1",
        media_content_type="image/jpeg",
        num_media="1",
    )

    result = await service.process_voice_message(message)
    assert result.success is False
    assert result.user_fallback_message == NON_AUDIO_MEDIA_MESSAGE


@pytest.mark.anyio
async def test_voice_service_download_size_exceeded():
    service = VoiceService()

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "audio/ogg"}
    # Greater than max allowed bytes
    fake_response.content = b"x" * (settings.MAX_AUDIO_SIZE_BYTES + 10)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = fake_response

        with pytest.raises(ValueError, match="exceeds limit"):
            await service.download_media("https://api.twilio.com/media/toolarge")


@pytest.mark.anyio
async def test_voice_service_transcription_success():
    mock_provider = MagicMock(spec=GroqAudioProvider)
    mock_provider.transcribe = AsyncMock(
        return_value={
            "text": "Nataka kuangalia account balance yangu",
            "language": "sw",
            "duration": 2.5,
        }
    )

    service = VoiceService(audio_provider=mock_provider)

    with patch.object(
        service,
        "download_media",
        new_callable=AsyncMock,
        return_value=(b"fake-audio-bytes", "audio/ogg"),
    ):
        message = IncomingWhatsAppMessage(
            from_number="+254700000000",
            media_url="https://api.twilio.com/media/audio1",
            media_content_type="audio/ogg; codecs=opus",
            num_media="1",
        )

        result = await service.process_voice_message(message)

        assert result.success is True
        assert result.text == "Nataka kuangalia account balance yangu"
        assert result.language == "sw"
        assert result.duration == 2.5


@pytest.mark.anyio
async def test_voice_service_empty_transcription_fallback():
    mock_provider = MagicMock(spec=GroqAudioProvider)
    mock_provider.transcribe = AsyncMock(return_value={"text": "   ", "language": "en"})

    service = VoiceService(audio_provider=mock_provider)

    with patch.object(
        service,
        "download_media",
        new_callable=AsyncMock,
        return_value=(b"silent-audio", "audio/ogg"),
    ):
        message = IncomingWhatsAppMessage(
            from_number="+254700000000",
            media_url="https://api.twilio.com/media/silent1",
            media_content_type="audio/ogg",
            num_media="1",
        )

        result = await service.process_voice_message(message)

        assert result.success is False
        assert result.user_fallback_message == VOICE_UNINTELLIGIBLE_MESSAGE


@pytest.mark.anyio
async def test_voice_service_download_failure_fallback():
    service = VoiceService()

    with patch.object(
        service,
        "download_media",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("Network failed"),
    ):
        message = IncomingWhatsAppMessage(
            from_number="+254700000000",
            media_url="https://api.twilio.com/media/fail",
            media_content_type="audio/ogg",
            num_media="1",
        )

        result = await service.process_voice_message(message)

        assert result.success is False
        assert result.user_fallback_message == VOICE_PROCESSING_ERROR_MESSAGE


# ---------------------------------------------------------------------------
# 4. End-to-End Orchestrator Integration Tests
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_handle_message_async_with_voice_greeting():
    """Verify voice note with 'Habari' transcribes and returns greeting response."""
    mock_voice_service = MagicMock(spec=VoiceService)
    mock_voice_service.process_voice_message = AsyncMock(
        return_value=VoiceTranscriptionResult(
            success=True,
            text="Habari",
            language="sw",
            duration=1.2,
        )
    )

    incoming = IncomingWhatsAppMessage(
        from_number="+254700000000",
        body="",
        num_media="1",
        media_url="https://api.twilio.com/media/voice1",
        media_content_type="audio/ogg",
    )

    response = await handle_message_async(
        incoming,
        voice_service=mock_voice_service,
    )

    # Greeting should be returned
    assert "Karibu" in response
    assert incoming.is_voice is True
    assert incoming.body == "Habari"


@pytest.mark.anyio
async def test_handle_message_async_with_voice_transcription_failure():
    """Verify failed voice note transcription returns the multilingual fallback message."""
    mock_voice_service = MagicMock(spec=VoiceService)
    mock_voice_service.process_voice_message = AsyncMock(
        return_value=VoiceTranscriptionResult(
            success=False,
            user_fallback_message=VOICE_UNINTELLIGIBLE_MESSAGE,
        )
    )

    incoming = IncomingWhatsAppMessage(
        from_number="+254700000000",
        body="",
        num_media="1",
        media_url="https://api.twilio.com/media/muffled",
        media_content_type="audio/ogg",
    )

    response = await handle_message_async(
        incoming,
        voice_service=mock_voice_service,
    )

    assert "Samahani, sikuweza kusikia sauti yako vizuri" in response
