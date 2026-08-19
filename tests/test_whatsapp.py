import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversation_service import handle_message


client = TestClient(app)


def _post_whatsapp(body: str, num_media: str = "0"):
    return client.post(
        "/webhooks/whatsapp",
        data={
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+254711111111",
            "Body": body,
            "NumMedia": num_media,
        },
    )


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_greeting_hello_returns_welcome():
    response = _post_whatsapp("Hello")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    body = response.text
    assert "Karibu" in body
    assert "Financial education" in body


def test_greeting_habari_returns_welcome():
    response = _post_whatsapp("Habari")
    assert response.status_code == 200
    assert "Karibu" in response.text


def test_menu_help_returns_welcome():
    response = _post_whatsapp("HELP")
    assert response.status_code == 200
    assert "Karibu" in response.text


def test_unknown_message_returns_fallback():
    response = _post_whatsapp("Something random")
    assert response.status_code == 200
    assert "AI assistant capabilities are being introduced" in response.text


def test_whitespace_normalization():
    response = _post_whatsapp("   hello   ")
    assert response.status_code == 200
    assert "Karibu" in response.text


def test_missing_body_returns_fallback():
    response = client.post(
        "/webhooks/whatsapp",
        data={
            "From": "whatsapp:+254700000000",
            "To": "whatsapp:+254711111111",
            "NumMedia": "0",
        },
    )
    assert response.status_code == 200
    assert "AI assistant capabilities are being introduced" in response.text


def test_route_returns_twiml_xml():
    response = _post_whatsapp("Hello")
    assert response.status_code == 200
    assert '<?xml version="1.0" encoding="UTF-8"?>' in response.text
    assert "<Response>" in response.text
    assert "<Message>" in response.text


def test_conversation_service_greeting():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="Hello")
    response = handle_message(message)
    assert "Karibu" in response


def test_conversation_service_menu():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="help")
    response = handle_message(message)
    assert "Karibu" in response


def test_conversation_service_unknown():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="random")
    response = handle_message(message)
    assert "AI assistant capabilities are being introduced" in response


def test_conversation_service_empty_body_without_media():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="")
    response = handle_message(message)
    assert "AI assistant capabilities are being introduced" in response


def test_conversation_service_empty_body_with_media():
    message = IncomingWhatsAppMessage(from_number="+254700000000", body="", num_media="1")
    response = handle_message(message)
    assert "media messages" in response.lower()
