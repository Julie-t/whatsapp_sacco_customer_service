from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from app.config.settings import settings


class WhatsAppService:
    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_whatsapp_from
        self.client = Client(self.account_sid, self.auth_token)

    def send_text(self, to_number: str, body: str):
        if not self.account_sid or not self.auth_token or not self.from_number:
            raise RuntimeError("Twilio credentials are not configured")

        self.client.messages.create(
            from_=f"whatsapp:{self.from_number}",
            to=f"whatsapp:{to_number}",
            body=body,
        )

    def build_twiml_response(self, body: str) -> str:
        response = MessagingResponse()
        response.message(body)
        return str(response)
