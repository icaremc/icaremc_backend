from fastapi import APIRouter

from app.core.security.deps import RequireAny
from app.core.services.sms_otp import sms_service, normalize_phone
from app.resources.sms.schemas import SendSmsIn, SendSmsOut

router = APIRouter(prefix="/sms", tags=["sms"])


@router.post("/send")
async def send_sms(body: SendSmsIn, user: RequireAny) -> SendSmsOut:
    phone = normalize_phone(body.phone)
    await sms_service.send_sms(to=phone, message=body.message)
    return SendSmsOut(status="ok")
