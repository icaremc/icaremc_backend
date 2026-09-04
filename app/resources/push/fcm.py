import httpx

from app.config import MySettings


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
