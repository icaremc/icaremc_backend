from typing import Annotated

from fastapi import APIRouter, Depends
from uuid import UUID

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.children.repository import SqlAlchemyChildrenRepository
from app.resources.children.schemas import ChildIn, MeasurementIn, MilestoneIn, VaccineIn
from app.resources.children.service import ChildrenService

router = APIRouter(tags=["mother"])


def get_children_service(db: DbDep) -> ChildrenService:
    return ChildrenService(SqlAlchemyChildrenRepository(db))


ChildrenServiceDep = Annotated[ChildrenService, Depends(get_children_service)]


@router.get("/children")
async def list_children(user: RequirePatient, svc: ChildrenServiceDep) -> list[RowOut]:
    return await svc.list_children(user.id)


@router.post("/children")
async def create_child(body: ChildIn, user: RequirePatient, svc: ChildrenServiceDep) -> RowOut:
    return await svc.create_child(user.id, body)


@router.patch("/children/{child_id}")
async def patch_child(child_id: UUID, body: ChildIn, user: RequirePatient, svc: ChildrenServiceDep) -> RowOut:
    return await svc.patch_child(child_id, user.id, body)


@router.post("/child-measurements")
async def add_measurement(body: MeasurementIn, user: RequirePatient, svc: ChildrenServiceDep) -> RowOut:
    return await svc.add_measurement(user.id, body)


@router.get("/child-measurements")
async def list_measurements(user: RequirePatient, child_local_id: str, svc: ChildrenServiceDep) -> list[RowOut]:
    return await svc.list_measurements(user.id, child_local_id)


@router.post("/child-milestones")
async def add_milestone(body: MilestoneIn, user: RequirePatient, svc: ChildrenServiceDep) -> RowOut:
    return await svc.add_milestone(user.id, body)


@router.get("/child-milestones")
async def list_milestones(user: RequirePatient, child_local_id: str, svc: ChildrenServiceDep) -> list[RowOut]:
    return await svc.list_milestones(user.id, child_local_id)


@router.post("/child-vaccines")
async def upsert_vaccine(body: VaccineIn, user: RequirePatient, svc: ChildrenServiceDep) -> RowOut:
    return await svc.upsert_vaccine(user.id, body)


@router.get("/child-vaccines")
async def list_vaccines(user: RequirePatient, child_local_id: str, svc: ChildrenServiceDep) -> list[RowOut]:
    return await svc.list_vaccines(user.id, child_local_id)


@router.get("/child-followups")
async def list_followups(user: RequirePatient, child_local_id: str, svc: ChildrenServiceDep) -> list[RowOut]:
    return await svc.list_followups(user.id, child_local_id)
