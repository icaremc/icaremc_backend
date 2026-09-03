from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Pregnancy, PregnancyLog


class PregnancyRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Pregnancy]: ...
    async def get_for_user(self, pregnancy_id: UUID, user_id: UUID) -> Pregnancy | None: ...
    async def list_logs(self, user_id: UUID, pregnancy_id: UUID | None) -> list[PregnancyLog]: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyPregnancyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: UUID) -> list[Pregnancy]:
        return list((await self._db.execute(select(Pregnancy).where(Pregnancy.user_id == user_id))).scalars().all())

    async def get_for_user(self, pregnancy_id: UUID, user_id: UUID) -> Pregnancy | None:
        return (
            await self._db.execute(
                select(Pregnancy).where(Pregnancy.id == pregnancy_id, Pregnancy.user_id == user_id)
            )
        ).scalar_one_or_none()

    async def list_logs(self, user_id: UUID, pregnancy_id: UUID | None) -> list[PregnancyLog]:
        q = (
            select(PregnancyLog)
            .join(Pregnancy, Pregnancy.id == PregnancyLog.pregnancy_id)
            .where(Pregnancy.user_id == user_id)
        )
        if pregnancy_id:
            q = q.where(PregnancyLog.pregnancy_id == pregnancy_id)
        return list((await self._db.execute(q)).scalars().all())

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
