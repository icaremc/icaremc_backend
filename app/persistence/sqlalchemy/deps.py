from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy import connection


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with connection.async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Official FastAPI skill: prefer Annotated[..., Depends(...)] aliases for reuse.
DbDep = Annotated[AsyncSession, Depends(get_db)]
