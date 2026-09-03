from uuid import UUID

from app.api.v1.schemas import RowOut
from app.persistence.sqlalchemy.models import Pregnancy, PregnancyLog
from app.resources.errors import not_found
from app.resources.pregnancies.repository import PregnancyRepository
from app.resources.pregnancies.schemas import PregnancyIn, PregnancyLogIn
from app.resources.serialize import require_row, to_rows


class PregnancyService:
    def __init__(self, repo: PregnancyRepository) -> None:
        self._repo = repo

    async def list_pregnancies(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_for_user(user_id))

    async def create_pregnancy(self, user_id: UUID, body: PregnancyIn) -> RowOut:
        row = Pregnancy(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def create_log(self, user_id: UUID, body: PregnancyLogIn) -> RowOut:
        preg = await self._repo.get_for_user(body.pregnancy_id, user_id)
        if preg is None:
            raise not_found("Pregnancy not found")
        row = PregnancyLog(**body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_logs(self, user_id: UUID, pregnancy_id: UUID | None) -> list[RowOut]:
        return to_rows(await self._repo.list_logs(user_id, pregnancy_id))
