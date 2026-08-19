from pydantic import BaseModel, Field


class IncomingWhatsAppMessage(BaseModel):
    message_id: str | None = None
    from_number: str
    to_number: str | None = None
    body: str
    profile_name: str | None = None
    num_media: str | None = "0"
    received_at: str | None = None
