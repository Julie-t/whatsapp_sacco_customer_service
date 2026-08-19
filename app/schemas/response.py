from pydantic import BaseModel


class OutgoingWhatsAppResponse(BaseModel):
    body: str
