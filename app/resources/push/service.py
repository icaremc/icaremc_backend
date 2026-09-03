from uuid import UUID

import httpx

from app.api.v1.schemas import PushOut
from app.config import MySettings
from app.persistence.sqlalchemy.models import Notification
from app.resources.push.repository import PushRepository
from app.resources.push.schemas import PushIn


async def send_fcm(token: str, title: str, body: str, data: dict[str, object] | None = None) -> dict[str, object]:
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
        payload = resp.json()
        return payload if isinstance(payload, dict) else {"response": payload}


class PushService:
    def __init__(self, repo: PushRepository) -> None:
        self._repo = repo

    async def notify(self, body: PushIn) -> PushOut:
        self._repo.add(
            Notification(
                user_id=body.user_id,
                type=body.type,
                title=body.title,
                body=body.body,
                data=body.data,
            )
        )
        profile = await self._repo.get_profile(body.user_id)
        token = profile.fcm_token if profile else None
        if token is None:
            doctor = await self._repo.get_doctor(body.user_id)
            token = doctor.fcm_token if doctor else None
        result = await send_fcm(token or "", body.title, body.body, body.data)
        await self._repo.flush()
        return PushOut(fcm=result)
