from uuid import UUID

from app.api.v1.schemas import DoctorDetailOut, RowOut
from app.resources.doctors.catalog_repository import DoctorCatalogRepository
from app.resources.errors import not_found
from app.resources.serialize import require_row, to_rows


class DoctorCatalogService:
    def __init__(self, repo: DoctorCatalogRepository) -> None:
        self._repo = repo

    async def list_doctors(self, category_id: UUID | None, verified_only: bool) -> list[RowOut]:
        return to_rows(await self._repo.list_doctors(category_id, verified_only))

    async def categories(self) -> list[RowOut]:
        return to_rows(await self._repo.categories())

    async def detail(self, doctor_id: UUID) -> DoctorDetailOut:
        doctor = await self._repo.get_doctor(doctor_id)
        if doctor is None:
            raise not_found()
        services = await self._repo.active_services(doctor_id)
        slots = await self._repo.active_slots(doctor_id)
        return DoctorDetailOut(
            doctor=require_row(doctor),
            services=to_rows(services),
            slots=to_rows(slots),
        )
