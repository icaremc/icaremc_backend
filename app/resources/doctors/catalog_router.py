from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.schemas import DoctorDetailOut, RowOut
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.doctors.catalog import DoctorCatalogService
from app.resources.doctors.catalog_repository import SqlAlchemyDoctorCatalogRepository

router = APIRouter(tags=["mother"])


def get_catalog_service(db: DbDep) -> DoctorCatalogService:
    return DoctorCatalogService(SqlAlchemyDoctorCatalogRepository(db))


CatalogServiceDep = Annotated[DoctorCatalogService, Depends(get_catalog_service)]


@router.get("/doctors")
async def list_doctors(
    svc: CatalogServiceDep, category_id: UUID | None = None, verified_only: bool = True
) -> list[RowOut]:
    return await svc.list_doctors(category_id, verified_only)


@router.get("/doctors/categories")
async def doctor_categories(svc: CatalogServiceDep) -> list[RowOut]:
    return await svc.categories()


@router.get("/doctors/{doctor_id}")
async def doctor_detail(doctor_id: UUID, svc: CatalogServiceDep) -> DoctorDetailOut:
    return await svc.detail(doctor_id)
