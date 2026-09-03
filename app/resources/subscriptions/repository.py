from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import AppSubscription, CareSubscription


class SubscriptionRepository(Protocol):
    async def active_app(self, user_id: UUID) -> AppSubscription | None: ...
    async def list_care(self, user_id: UUID) -> list[CareSubscription]: ...


class SqlAlchemySubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def active_app(self, user_id: UUID) -> AppSubscription | None:
        return (
            await self._db.execute(
                select(AppSubscription).where(AppSubscription.patient_id == user_id, AppSubscription.status == "active")
            )
        ).scalar_one_or_none()

    async def list_care(self, user_id: UUID) -> list[CareSubscription]:
        return list(
            (await self._db.execute(select(CareSubscription).where(CareSubscription.patient_id == user_id))).scalars().all()
        )
