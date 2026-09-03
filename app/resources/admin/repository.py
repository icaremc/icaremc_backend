from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class AdminRepository(Protocol):
    @property
    def session(self) -> AsyncSession: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyAdminRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.session = db

    def add(self, obj: object) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        await self.session.flush()
