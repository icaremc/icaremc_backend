from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import AppSetting


class SettingsRepository(Protocol):
    async def get(self, setting_id: str) -> AppSetting | None: ...


class SqlAlchemySettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, setting_id: str) -> AppSetting | None:
        return (await self._db.execute(select(AppSetting).where(AppSetting.id == setting_id))).scalar_one_or_none()
