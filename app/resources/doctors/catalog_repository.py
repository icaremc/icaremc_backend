from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import DoctorAvailabilitySlot, DoctorCategory, DoctorProfile, DoctorService


class DoctorCatalogRepository(Protocol):
    async def list_doctors(self, category_id: UUID | None, verified_only: bool) -> list[DoctorProfile]: ...
    async def categories(self) -> list[DoctorCategory]: ...
    async def get_doctor(self, doctor_id: UUID) -> DoctorProfile | None: ...
    async def active_services(self, doctor_id: UUID) -> list[DoctorService]: ...
    async def active_slots(self, doctor_id: UUID) -> list[DoctorAvailabilitySlot]: ...


class SqlAlchemyDoctorCatalogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_doctors(self, category_id: UUID | None, verified_only: bool) -> list[DoctorProfile]:
        q = select(DoctorProfile)
        if verified_only:
            q = q.where(DoctorProfile.is_verified.is_(True))
        if category_id:
            q = q.where(DoctorProfile.category_id == category_id)
        return list((await self._db.execute(q)).scalars().all())

    async def categories(self) -> list[DoctorCategory]:
        return list(
            (await self._db.execute(select(DoctorCategory).where(DoctorCategory.is_active.is_(True)))).scalars().all()
        )

    async def get_doctor(self, doctor_id: UUID) -> DoctorProfile | None:
        return (await self._db.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))).scalar_one_or_none()

    async def active_services(self, doctor_id: UUID) -> list[DoctorService]:
        return list(
            (
                await self._db.execute(
                    select(DoctorService).where(DoctorService.doctor_id == doctor_id, DoctorService.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )

    async def active_slots(self, doctor_id: UUID) -> list[DoctorAvailabilitySlot]:
        return list(
            (
                await self._db.execute(
                    select(DoctorAvailabilitySlot).where(
                        DoctorAvailabilitySlot.doctor_id == doctor_id,
                        DoctorAvailabilitySlot.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
