import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

from app.config.settings import settings
from app.schemas.message import IncomingWhatsAppMessage
from app.services.conversation_service import handle_message_async
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)
router = APIRouter()

_whatsapp_service = WhatsAppService()


def _validate_twilio_request(request: Request, body_bytes: bytes) -> bool:
    if not settings.twilio_validate_signature:
        return True

    if not settings.twilio_auth_token:
        return True

    validator = RequestValidator(settings.twilio_auth_token)
    url = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    parsed = parse_qs(body_bytes.decode("utf-8"), keep_blank_values=True)
    params = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    return validator.validate(url, params, signature)


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    body_bytes = await request.body()
    if not _validate_twilio_request(request, body_bytes):
        logger.warning("Invalid Twilio webhook signature")
        return Response(content="", status_code=403)

    form = await request.form()
    from_number = form.get("From", "")
    to_number = form.get("To", "")
    body = form.get("Body", "")
    profile_name = form.get("ProfileName", "")
    num_media = form.get("NumMedia", "0")

    incoming = IncomingWhatsAppMessage(
        from_number=from_number,
        to_number=to_number,
        body=body,
        profile_name=profile_name or None,
        num_media=num_media,
    )

    response_body = await handle_message_async(incoming)
    twiml = _whatsapp_service.build_twiml_response(response_body)
    return Response(content=twiml, media_type="application/xml")
