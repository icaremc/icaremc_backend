from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.schemas import AppointmentOut, RowOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.appointments.repository import SqlAlchemyAppointmentRepository
from app.resources.appointments.schemas import BookIn, ReviewIn
from app.resources.appointments.service import AppointmentService

router = APIRouter(tags=["mother"])


def get_appointment_service(db: DbDep) -> AppointmentService:
    return AppointmentService(SqlAlchemyAppointmentRepository(db))


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]


@router.post("/appointments")
async def book_appointment(body: BookIn, user: RequirePatient, svc: AppointmentServiceDep) -> AppointmentOut:
    return await svc.book(user.id, body)


@router.get("/appointments")
async def my_appointments(user: RequirePatient, svc: AppointmentServiceDep) -> list[AppointmentOut]:
    return await svc.list_patient(user.id)


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: UUID, user: RequirePatient, svc: AppointmentServiceDep) -> RowOut:
    return await svc.cancel_patient(appointment_id, user.id)


@router.post("/reviews")
async def create_review(body: ReviewIn, user: RequirePatient, svc: AppointmentServiceDep) -> RowOut:
    return await svc.create_review(user.id, body)


@router.get("/reviews")
async def list_reviews(
    user: RequirePatient,
    svc: AppointmentServiceDep,
    appointment_id: UUID | None = None,
    doctor_id: UUID | None = None,
    mine: bool | None = None,
) -> list[RowOut]:
    return await svc.list_reviews(
        user_id=user.id,
        appointment_id=appointment_id,
        doctor_id=doctor_id,
        mine=mine,
    )


@router.get("/appointments/{appointment_id}/review")
async def get_appointment_review(
    appointment_id: UUID, user: RequirePatient, svc: AppointmentServiceDep
) -> RowOut:
    return await svc.get_appointment_review(appointment_id, user.id)
