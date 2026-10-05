from fastapi import APIRouter

import asyncio

from app.core.security.deps import RequireAny
from app.core.services.sms_otp import sms_service, normalize_phone
from app.resources.sms.schemas import SendSmsIn, SendSmsOut, SendBulkSmsIn

router = APIRouter(prefix="/sms", tags=["sms"])


@router.post("/send")
async def send_sms(body: SendSmsIn, user: RequireAny) -> SendSmsOut:
    phone = normalize_phone(body.phone)
    await sms_service.send_sms(to=phone, message=body.message)
    return SendSmsOut(status="ok")


@router.post("/bulk-send")
async def send_bulk_sms(body: SendBulkSmsIn, user: RequireAny) -> SendSmsOut:
    phones = [normalize_phone(p) for p in body.phones]
    
    # Send bulk SMS using the AfroMessage bulk endpoint
    await sms_service.send_bulk_sms(to=phones, message=body.message)
    
    return SendSmsOut(status="ok")
