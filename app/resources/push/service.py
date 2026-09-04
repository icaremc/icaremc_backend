from app.api.v1.schemas import PushOut
from app.persistence.sqlalchemy.models import Notification
from app.resources.push.fcm import send_fcm
from app.resources.push.repository import PushRepository
from app.resources.push.schemas import PushIn


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
