from uuid import UUID

from app.api.v1.schemas import RowOut
from app.persistence.sqlalchemy.models import (
    Child,
    ChildGrowthMeasurement,
    ChildMilestoneCheck,
    ChildVaccineRecord,
)
from app.resources.children.repository import ChildrenRepository
from app.resources.children.schemas import ChildIn, MeasurementIn, MilestoneIn, VaccineIn
from app.resources.errors import not_found
from app.resources.serialize import require_row, to_rows


class ChildrenService:
    def __init__(self, repo: ChildrenRepository) -> None:
        self._repo = repo

    async def list_children(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_children(user_id))

    async def create_child(self, user_id: UUID, body: ChildIn) -> RowOut:
        row = Child(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def patch_child(self, child_id: UUID, user_id: UUID, body: ChildIn) -> RowOut:
        row = await self._repo.get_child(child_id, user_id)
        if row is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self._repo.flush()
        return require_row(row)

    async def add_measurement(self, user_id: UUID, body: MeasurementIn) -> RowOut:
        data = body.model_dump()
        if data.get("measured_on") is None:
            data.pop("measured_on", None)
        row = ChildGrowthMeasurement(
            user_id=user_id, **{k: v for k, v in data.items() if v is not None or k == "child_local_id"}
        )
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_measurements(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_measurements(user_id, child_local_id))

    async def add_milestone(self, user_id: UUID, body: MilestoneIn) -> RowOut:
        row = ChildMilestoneCheck(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_milestones(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_milestones(user_id, child_local_id))

    async def upsert_vaccine(self, user_id: UUID, body: VaccineIn) -> RowOut:
        existing = await self._repo.get_vaccine(user_id, body.child_local_id, body.vaccine_key)
        if existing:
            for key, value in body.model_dump().items():
                setattr(existing, key, value)
            await self._repo.flush()
            return require_row(existing)
        row = ChildVaccineRecord(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_vaccines(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_vaccines(user_id, child_local_id))

    async def list_followups(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_followups(user_id, child_local_id))
