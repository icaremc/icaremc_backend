from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Notification


class NotificationRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Notification]: ...
    async def get_for_user(self, notification_id: UUID, user_id: UUID) -> Notification | None: ...
    async def flush(self) -> None: ...
    def add(self, obj: object) -> None: ...


class SqlAlchemyNotificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: UUID) -> list[Notification]:
        return list(
            (
                await self._db.execute(
                    select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def get_for_user(self, notification_id: UUID, user_id: UUID) -> Notification | None:
        return (
            await self._db.execute(
                select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
            )
        ).scalar_one_or_none()

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
