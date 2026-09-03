from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.notifications.repository import SqlAlchemyNotificationRepository
from app.resources.notifications.service import NotificationService

router = APIRouter(tags=["mother"])


def get_notification_service(db: DbDep) -> NotificationService:
    return NotificationService(SqlAlchemyNotificationRepository(db))


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


@router.get("/notifications")
async def notifications(user: RequirePatient, svc: NotificationServiceDep) -> list[RowOut]:
    return await svc.list_for_user(user.id)


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: UUID, user: RequirePatient, svc: NotificationServiceDep) -> RowOut:
    return await svc.mark_read(notification_id, user.id)
