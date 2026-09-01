from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """A single turn in a conversation (user or assistant message)."""

    role: str  # "user" or "assistant"
    content: str


class IncomingWhatsAppMessage(BaseModel):
    message_id: str | None = None
    from_number: str
    to_number: str | None = None
    body: str
    profile_name: str | None = None
    num_media: str | None = "0"
    received_at: str | None = None
