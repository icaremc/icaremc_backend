from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    Appointment,
    AppointmentReview,
    DoctorProfile,
    DoctorService,
    Profile,
)


class AppointmentRepository(Protocol):
    async def get_profile(self, user_id: UUID) -> Profile: ...
    async def get_service(self, service_id: UUID) -> DoctorService | None: ...
    async def get_doctor(self, doctor_id: UUID) -> DoctorProfile | None: ...
    async def get_for_patient(self, appointment_id: UUID, patient_id: UUID) -> Appointment | None: ...
    async def list_for_patient(self, patient_id: UUID) -> list[Appointment]: ...
    async def list_for_doctor(self, doctor_id: UUID) -> list[Appointment]: ...
    async def get_for_doctor(self, appointment_id: UUID, doctor_id: UUID) -> Appointment | None: ...
    async def list_reviews_for_doctor(self, doctor_id: UUID) -> list[AppointmentReview]: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...
    @property
    def session(self) -> AsyncSession: ...


class SqlAlchemyAppointmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.session = db

    async def get_profile(self, user_id: UUID) -> Profile:
        return (await self.session.execute(select(Profile).where(Profile.id == user_id))).scalar_one()

    async def get_service(self, service_id: UUID) -> DoctorService | None:
        return (await self.session.execute(select(DoctorService).where(DoctorService.id == service_id))).scalar_one_or_none()

    async def get_doctor(self, doctor_id: UUID) -> DoctorProfile | None:
        return (await self.session.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))).scalar_one_or_none()

    async def get_for_patient(self, appointment_id: UUID, patient_id: UUID) -> Appointment | None:
        return (
            await self.session.execute(
                select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == patient_id)
            )
        ).scalar_one_or_none()

    async def list_for_patient(self, patient_id: UUID) -> list[Appointment]:
        return list(
            (await self.session.execute(select(Appointment).where(Appointment.patient_id == patient_id))).scalars().all()
        )

    async def list_for_doctor(self, doctor_id: UUID) -> list[Appointment]:
        return list(
            (await self.session.execute(select(Appointment).where(Appointment.doctor_id == doctor_id))).scalars().all()
        )

    async def get_for_doctor(self, appointment_id: UUID, doctor_id: UUID) -> Appointment | None:
        return (
            await self.session.execute(
                select(Appointment).where(Appointment.id == appointment_id, Appointment.doctor_id == doctor_id)
            )
        ).scalar_one_or_none()

    async def list_reviews_for_doctor(self, doctor_id: UUID) -> list[AppointmentReview]:
        return list(
            (
                await self.session.execute(select(AppointmentReview).where(AppointmentReview.doctor_id == doctor_id))
            )
            .scalars()
            .all()
        )

    def add(self, obj: object) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        await self.session.flush()
