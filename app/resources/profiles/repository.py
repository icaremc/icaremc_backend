from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Profile
from typing import Protocol


class ProfileRepository(Protocol):
    async def get(self, user_id: UUID) -> Profile | None: ...
    async def flush(self) -> None: ...


class SqlAlchemyProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: UUID) -> Profile | None:
        return (await self._db.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()

    async def flush(self) -> None:
        await self._db.flush()
