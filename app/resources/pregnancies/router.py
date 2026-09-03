from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.pregnancies.repository import SqlAlchemyPregnancyRepository
from app.resources.pregnancies.schemas import PregnancyIn, PregnancyLogIn
from app.resources.pregnancies.service import PregnancyService

router = APIRouter(tags=["mother"])


def get_pregnancy_service(db: DbDep) -> PregnancyService:
    return PregnancyService(SqlAlchemyPregnancyRepository(db))


PregnancyServiceDep = Annotated[PregnancyService, Depends(get_pregnancy_service)]


@router.get("/pregnancies")
async def list_pregnancies(user: RequirePatient, svc: PregnancyServiceDep) -> list[RowOut]:
    return await svc.list_pregnancies(user.id)


@router.post("/pregnancies")
async def create_pregnancy(body: PregnancyIn, user: RequirePatient, svc: PregnancyServiceDep) -> RowOut:
    return await svc.create_pregnancy(user.id, body)


@router.post("/pregnancy-logs")
async def create_pregnancy_log(body: PregnancyLogIn, user: RequirePatient, svc: PregnancyServiceDep) -> RowOut:
    return await svc.create_log(user.id, body)


@router.get("/pregnancy-logs")
async def list_pregnancy_logs(
    user: RequirePatient, svc: PregnancyServiceDep, pregnancy_id: UUID | None = None
) -> list[RowOut]:
    return await svc.list_logs(user.id, pregnancy_id)
