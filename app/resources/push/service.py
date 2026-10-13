from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Notification
from app.resources.push.fcm import send_fcm
from app.resources.push.repository import PushRepository, SqlAlchemyPushRepository
from app.resources.push.schemas import PushIn, PushOut


async def dispatch_notification(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    body: str,
    type: str = "generic",
    data: dict[str, object] | None = None,
    is_urgent: bool = True,
) -> tuple[Notification, dict[str, Any]]:
    """Dispatches an in-app and push notification to a user or doctor.

    1. Enriches data payload with click_action and type.
    2. Persists an in-app Notification record in the database for inbox history.
    3. Checks user's notifications_enabled preference.
    4. If is_urgent=True and notifications_enabled, sends real-time FCM push notification.
    """
    repo = SqlAlchemyPushRepository(db)
    payload_data = dict(data or {})
    if "type" not in payload_data:
        payload_data["type"] = type
    if "click_action" not in payload_data:
        payload_data["click_action"] = "FLUTTER_NOTIFICATION_CLICK"

    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        data=payload_data,
    )
    repo.add(notif)

    fcm_result: dict[str, Any] = {"ok": False, "skipped": True}

    profile = await repo.get_profile(user_id)
    token = None
    enabled = True

    if profile:
        token = profile.fcm_token
        enabled = profile.notifications_enabled is not False
    else:
        doctor = await repo.get_doctor(user_id)
        if doctor:
            token = doctor.fcm_token
            enabled = doctor.notifications_enabled is not False

    if is_urgent and enabled and token:
        fcm_result = await send_fcm(token, title, body, payload_data)
    elif not enabled:
        fcm_result = {"ok": False, "skipped": True, "reason": "notifications_disabled_by_user"}
    elif not token:
        fcm_result = {"ok": False, "skipped": True, "reason": "no_device_token"}

    await repo.flush()
    return notif, fcm_result


class PushService:
    def __init__(self, repo: PushRepository) -> None:
        self._repo = repo

    async def notify(self, body: PushIn) -> PushOut:
        # If repo is SqlAlchemyPushRepository, use the unified dispatch_notification
        if hasattr(self._repo, "_db") and isinstance(getattr(self._repo, "_db"), AsyncSession):
            _, result = await dispatch_notification(
                db=getattr(self._repo, "_db"),
                user_id=body.user_id,
                title=body.title,
                body=body.body,
                type=body.type,
                data=body.data,
                is_urgent=True,
            )
            return PushOut(fcm=result)

        # Fallback for mock repositories
        profile = await self._repo.get_profile(body.user_id)
        token = profile.fcm_token if profile else None
        if token is None:
            doctor = await self._repo.get_doctor(body.user_id)
            token = doctor.fcm_token if doctor else None

        self._repo.add(
            Notification(
                user_id=body.user_id,
                type=body.type,
                title=body.title,
                body=body.body,
                data=body.data,
            )
        )
        result = await send_fcm(token or "", body.title, body.body, body.data)
        await self._repo.flush()
        return PushOut(fcm=result)
