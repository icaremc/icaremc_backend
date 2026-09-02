import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MySettings, EnvironmentOptions
from app.persistence.sqlalchemy.models import OtpChallenge


def normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0") and len(digits) == 10:
        digits = "251" + digits[1:]
    return digits


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def send_otp(db: AsyncSession, *, phone: str, purpose: str) -> str:
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

    if MySettings.SMS_API_BASE_URL:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{MySettings.SMS_API_BASE_URL.rstrip('/')}/sms/send-otp",
                json={"phone": phone, "code": code},
                headers={"Authorization": f"Bearer {MySettings.SMS_API_KEY}"} if MySettings.SMS_API_KEY else {},
            )
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
