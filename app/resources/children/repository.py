from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    Child,
    ChildFollowupVisit,
    ChildGrowthMeasurement,
    ChildMilestoneCheck,
    ChildVaccineRecord,
)


class ChildrenRepository(Protocol):
    async def list_children(self, user_id: UUID) -> list[Child]: ...
    async def get_child(self, child_id: UUID, user_id: UUID) -> Child | None: ...
    async def list_measurements(self, user_id: UUID, child_local_id: str) -> list[ChildGrowthMeasurement]: ...
    async def list_milestones(self, user_id: UUID, child_local_id: str) -> list[ChildMilestoneCheck]: ...
    async def list_vaccines(self, user_id: UUID, child_local_id: str) -> list[ChildVaccineRecord]: ...
    async def get_vaccine(self, user_id: UUID, child_local_id: str, vaccine_key: str) -> ChildVaccineRecord | None: ...
    async def list_followups(self, user_id: UUID, child_local_id: str) -> list[ChildFollowupVisit]: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyChildrenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_children(self, user_id: UUID) -> list[Child]:
        return list((await self._db.execute(select(Child).where(Child.user_id == user_id))).scalars().all())

    async def get_child(self, child_id: UUID, user_id: UUID) -> Child | None:
        return (
            await self._db.execute(select(Child).where(Child.id == child_id, Child.user_id == user_id))
        ).scalar_one_or_none()

    async def list_measurements(self, user_id: UUID, child_local_id: str) -> list[ChildGrowthMeasurement]:
        return list(
            (
                await self._db.execute(
                    select(ChildGrowthMeasurement).where(
                        ChildGrowthMeasurement.user_id == user_id,
                        ChildGrowthMeasurement.child_local_id == child_local_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    async def list_milestones(self, user_id: UUID, child_local_id: str) -> list[ChildMilestoneCheck]:
        return list(
            (
                await self._db.execute(
                    select(ChildMilestoneCheck).where(
                        ChildMilestoneCheck.user_id == user_id,
                        ChildMilestoneCheck.child_local_id == child_local_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    async def list_vaccines(self, user_id: UUID, child_local_id: str) -> list[ChildVaccineRecord]:
        return list(
            (
                await self._db.execute(
                    select(ChildVaccineRecord).where(
                        ChildVaccineRecord.user_id == user_id,
                        ChildVaccineRecord.child_local_id == child_local_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    async def get_vaccine(self, user_id: UUID, child_local_id: str, vaccine_key: str) -> ChildVaccineRecord | None:
        return (
            await self._db.execute(
                select(ChildVaccineRecord).where(
                    ChildVaccineRecord.user_id == user_id,
                    ChildVaccineRecord.child_local_id == child_local_id,
                    ChildVaccineRecord.vaccine_key == vaccine_key,
                )
            )
        ).scalar_one_or_none()

    async def list_followups(self, user_id: UUID, child_local_id: str) -> list[ChildFollowupVisit]:
        return list(
            (
                await self._db.execute(
                    select(ChildFollowupVisit).where(
                        ChildFollowupVisit.user_id == user_id,
                        ChildFollowupVisit.child_local_id == child_local_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
