import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.ai.providers.nvidia import NVIDIAProvider
from app.ai.nvidia import LLM
from app.schemas.ai import AICompletionRequest

client = TestClient(app)


def test_ai_endpoint_returns_200_with_mocked_provider():
    with patch.object(NVIDIAProvider, "generate", return_value="A SACCO is a member-owned savings cooperative."):
        response = client.post("/ai/test", json={"message": "What is a SACCO?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "SACCO" in data["response"]


def test_ai_endpoint_missing_api_key_returns_500(monkeypatch):
    monkeypatch.setattr("app.ai.providers.nvidia.settings.NVIDIA_API_KEY", "")
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_authentication_failure(monkeypatch):
    async def fail_auth(*args, **kwargs):
        raise RuntimeError("NVIDIA authentication failed")

    monkeypatch.setattr("app.ai.nvidia.NVIDIAProvider.generate", fail_auth)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_rate_limit(monkeypatch):
    async def rate_limited(*args, **kwargs):
        raise RuntimeError("NVIDIA rate limit exceeded")

    monkeypatch.setattr("app.ai.nvidia.NVIDIAProvider.generate", rate_limited)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_timeout(monkeypatch):
    async def timeout(*args, **kwargs):
        raise RuntimeError("NVIDIA request timed out")

    monkeypatch.setattr("app.ai.nvidia.NVIDIAProvider.generate", timeout)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_unexpected_response_format(monkeypatch):
    async def bad_format(*args, **kwargs):
        raise RuntimeError("Unexpected NVIDIA response format")

    monkeypatch.setattr("app.ai.nvidia.NVIDIAProvider.generate", bad_format)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_network_error(monkeypatch):
    async def network_error(*args, **kwargs):
        raise RuntimeError("NVIDIA network error")

    monkeypatch.setattr("app.ai.nvidia.NVIDIAProvider.generate", network_error)
    response = client.post("/ai/test", json={"message": "Explain SACCOs"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_ai_endpoint_request_schema():
    response = client.post("/ai/test", json={"message": "Hello"})
    assert response.status_code in (200, 500)


def test_ai_endpoint_missing_message():
    response = client.post("/ai/test", json={})
    assert response.status_code == 422
