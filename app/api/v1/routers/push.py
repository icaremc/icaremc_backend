from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MySettings
from app.core.security.deps import RequireAdmin
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import DoctorProfile, Notification, Profile

router = APIRouter(prefix="/push", tags=["push"])


class PushIn(BaseModel):
    user_id: UUID
    title: str
    body: str
    type: str = "generic"
    data: dict = Field(default_factory=dict)


async def send_fcm(token: str, title: str, body: str, data: dict | None = None) -> dict:
    if not MySettings.FCM_SERVER_KEY or not token:
        return {"ok": False, "skipped": True}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://fcm.googleapis.com/fcm/send",
            json={
                "to": token,
                "notification": {"title": title, "body": body},
                "data": {k: str(v) for k, v in (data or {}).items()},
            },
            headers={"Authorization": f"key={MySettings.FCM_SERVER_KEY}", "Content-Type": "application/json"},
        )
        return resp.json()


@router.post("/notify")
async def notify(body: PushIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    db.add(
        Notification(
            user_id=body.user_id,
            type=body.type,
            title=body.title,
            body=body.body,
            data=body.data,
        )
    )
    profile = (await db.execute(select(Profile).where(Profile.id == body.user_id))).scalar_one_or_none()
    token = profile.fcm_token if profile else None
    if token is None:
        doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == body.user_id))).scalar_one_or_none()
        token = doctor.fcm_token if doctor else None
    result = await send_fcm(token or "", body.title, body.body, body.data)
    await db.flush()
    return {"ok": True, "fcm": result}
