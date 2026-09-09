import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MySettings, EnvironmentOptions
from app.persistence.sqlalchemy.models import OtpChallenge
from app.core.services.sms import AfroMessageService

sms_service = AfroMessageService(
    api_key=MySettings.AFROMESSAGE_API_KEY,
    sender_name=MySettings.AFRO_MESSAGE_SENDER_NAME,
    identifier_id=MySettings.AFRO_MESSAGE_IDENTIFIER_ID,
)


def normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "251" + digits[1:]
    return digits


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def send_otp(db: AsyncSession, *, phone: str, purpose: str, message_template: str = "Your verification code is: {code}") -> str:
    phone = normalize_phone(phone)
    code = (
        MySettings.SMS_OTP_DEV_CODE
        if MySettings.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT
        else f"{secrets.randbelow(1_000_000):06d}"
    )
    challenge = OtpChallenge(
        phone=phone,
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(challenge)
    await db.flush()

    message = message_template.format(code=code)
    await sms_service.send_sms(to=phone, message=message)
    return code if MySettings.ENVIRONMENT == EnvironmentOptions.DEVELOPMENT else ""


async def verify_otp(db: AsyncSession, *, phone: str, purpose: str, code: str) -> bool:
    phone = normalize_phone(phone)
    result = await db.execute(
        select(OtpChallenge)
        .where(
            OtpChallenge.phone == phone,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
            OtpChallenge.expires_at > datetime.now(UTC),
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    challenge = result.scalar_one_or_none()
    if challenge is None or challenge.code_hash != _hash_code(code):
        return False
    challenge.consumed_at = datetime.now(UTC)
    await db.flush()
    return True
