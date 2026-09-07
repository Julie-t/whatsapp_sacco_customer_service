import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.ai.providers.groq import GroqProvider, GroqRateLimitError
from app.ai.llm import LLM
from app.schemas.ai import AICompletionRequest

client = TestClient(app)


def test_ai_endpoint_returns_200_with_mocked_provider():
    with patch.object(GroqProvider, "generate", return_value="A SACCO is a member-owned savings cooperative."):
        response = client.post("/ai/test", json={"message": "What is a SACCO?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "SACCO" in data["response"]


def test_ai_endpoint_missing_api_key_returns_500(monkeypatch):
    monkeypatch.setattr("app.ai.providers.groq.settings.GROQ_API_KEY", "")
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_authentication_failure(monkeypatch):
    async def fail_auth(*args, **kwargs):
        raise RuntimeError("Groq authentication failed")

    monkeypatch.setattr("app.ai.providers.groq.GroqProvider.generate", fail_auth)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_rate_limit(monkeypatch):
    async def rate_limited(*args, **kwargs):
        raise RuntimeError("Groq rate limit exceeded")

    monkeypatch.setattr("app.ai.providers.groq.GroqProvider.generate", rate_limited)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_timeout(monkeypatch):
    async def timeout(*args, **kwargs):
        raise RuntimeError("Groq request timed out")

    monkeypatch.setattr("app.ai.providers.groq.GroqProvider.generate", timeout)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_unexpected_response_format(monkeypatch):
    async def bad_format(*args, **kwargs):
        raise RuntimeError("Unexpected Groq response format")

    monkeypatch.setattr("app.ai.providers.groq.GroqProvider.generate", bad_format)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_network_error(monkeypatch):
    async def network_error(*args, **kwargs):
        raise RuntimeError("Groq network error")

    monkeypatch.setattr("app.ai.providers.groq.GroqProvider.generate", network_error)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


@pytest.mark.anyio
async def test_groq_provider_retries_on_rate_limit(monkeypatch):
    provider = GroqProvider()
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = str(self._payload)

        def raise_for_status(self):
            if self.status_code != 200:
                raise httpx.HTTPStatusError(
                    "rate limited",
                    request=httpx.Request("POST", "https://example.com"),
                    response=httpx.Response(self.status_code, request=httpx.Request("POST", "https://example.com")),
                )

        def json(self):
            return self._payload

    async def fake_post(self, url, json, headers):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.HTTPStatusError(
                "429",
                request=httpx.Request("POST", url),
                response=httpx.Response(429, request=httpx.Request("POST", url)),
            )
        return FakeResponse(200, {"choices": [{"message": {"content": "Recovered answer"}}]})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("app.config.settings.settings.GROQ_API_KEY", "key")

    result = await provider.generate([{"role": "user", "content": "Hi"}])

    assert result == "Recovered answer"
    assert calls["count"] == 2


@pytest.mark.anyio
async def test_groq_provider_uses_configured_generation_payload(monkeypatch):
    provider = GroqProvider()
    request = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Configured answer"}}]}

    async def fake_post(self, url, json, headers):
        request.update(json)
        return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("app.config.settings.settings.GROQ_API_KEY", "key")

    result = await provider.generate([{"role": "user", "content": "Hi"}])

    assert result == "Configured answer"
    assert request == {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 500,
        "temperature": 0.2,
        "reasoning_effort": "low",
    }


@pytest.mark.anyio
async def test_groq_provider_uses_provider_retry_timing(monkeypatch):
    provider = GroqProvider(max_retries=1)
    delays = []
    calls = {"count": 0}

    async def fake_sleep(delay):
        delays.append(delay)

    async def fake_post(self, url, json, headers):
        calls["count"] += 1
        response = httpx.Response(
            429,
            headers={"retry-after": "4.5"},
            text="Please try again later",
            request=httpx.Request("POST", url),
        )
        raise httpx.HTTPStatusError("429", request=response.request, response=response)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("app.config.settings.settings.GROQ_API_KEY", "key")

    with pytest.raises(GroqRateLimitError):
        await provider.generate([{"role": "user", "content": "Hi"}])

    assert calls["count"] == 2
    assert delays == [4.5]


@pytest.mark.anyio
async def test_groq_provider_rate_limit_retries_are_bounded(monkeypatch):
    provider = GroqProvider(max_retries=2)
    calls = {"count": 0}

    async def fake_sleep(delay):
        return None

    async def fake_post(self, url, json, headers):
        calls["count"] += 1
        response = httpx.Response(
            429,
            text="Please try again in 2s.",
            request=httpx.Request("POST", url),
        )
        raise httpx.HTTPStatusError("429", request=response.request, response=response)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("app.config.settings.settings.GROQ_API_KEY", "key")

    with pytest.raises(GroqRateLimitError):
        await provider.generate([{"role": "user", "content": "Hi"}])

    assert calls["count"] == 3


@pytest.mark.anyio
async def test_groq_provider_retry_sleep_cancellation_propagates(monkeypatch):
    provider = GroqProvider(max_retries=1)

    async def fake_sleep(delay):
        raise asyncio.CancelledError

    async def fake_post(self, url, json, headers):
        response = httpx.Response(
            429,
            text="Please try again in 2s.",
            request=httpx.Request("POST", url),
        )
        raise httpx.HTTPStatusError("429", request=response.request, response=response)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("app.config.settings.settings.GROQ_API_KEY", "key")

    with pytest.raises(asyncio.CancelledError):
        await provider.generate([{"role": "user", "content": "Hi"}])


def test_ai_endpoint_request_schema():
    response = client.post("/ai/test", json={"message": "Hello"})
    assert response.status_code in (200, 500)


def test_ai_endpoint_missing_message():
    response = client.post("/ai/test", json={})
    assert response.status_code == 422
