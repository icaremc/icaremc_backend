from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import DoctorProfile, Profile


class PushRepository(Protocol):
    async def get_profile(self, user_id: UUID) -> Profile | None: ...
    async def get_doctor(self, user_id: UUID) -> DoctorProfile | None: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyPushRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_profile(self, user_id: UUID) -> Profile | None:
        return (await self._db.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()

    async def get_doctor(self, user_id: UUID) -> DoctorProfile | None:
        return (await self._db.execute(select(DoctorProfile).where(DoctorProfile.id == user_id))).scalar_one_or_none()

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
