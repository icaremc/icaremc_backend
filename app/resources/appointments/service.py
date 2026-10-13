from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.api.v1.schemas import AppointmentOut, RowOut
from app.core.services.booking_finance import (
    cancel_appointment as refund_cancel,
    credit_doctor_on_complete,
)
from app.persistence.sqlalchemy.models import Appointment, AppointmentReview, ChatConversation
from app.persistence.sqlalchemy.serialize import row_dict
from app.resources.appointments.repository import AppointmentRepository
from app.resources.appointments.schemas import BookIn, ReviewIn
from app.resources.errors import bad_request, conflict, not_found
from app.resources.push.service import dispatch_notification
from app.resources.serialize import require_row, to_rows


class AppointmentService:
    def __init__(self, repo: AppointmentRepository) -> None:
        self._repo = repo

    async def book(self, user_id: UUID, body: BookIn) -> AppointmentOut:
        profile = await self._repo.get_profile(user_id)
        service = await self._repo.get_service(body.service_id) if body.service_id else None
        doctor = await self._repo.get_doctor(body.doctor_id)
        if doctor is None:
            raise not_found("Doctor not found")
        total = service.price if service else Decimal("0")
        prepay = total if doctor.prepayment_mode == "full" else Decimal("0")
        row = Appointment(
            doctor_id=body.doctor_id,
            patient_id=user_id,
            appointment_date=body.appointment_date,
            time_slot=body.time_slot,
            note=body.note,
            patient_name=profile.full_name,
            patient_phone=profile.phone,
            service_id=body.service_id,
            service_name=service.name if service else None,
            service_description=service.description if service else None,
            service_price=service.price if service else None,
            service_duration_minutes=service.duration_minutes if service else None,
            prepayment_mode=doctor.prepayment_mode,
            prepayment_percent=doctor.prepayment_percent,
            total_amount=total,
            prepayment_amount=prepay,
            amount_paid=Decimal("0"),
            payment_status="unpaid" if prepay > 0 else "waived",
            payment_method=body.payment_method,
            care_subscription_id=body.care_subscription_id,
            status="pending",
        )
        self._repo.add(row)
        try:
            await self._repo.flush()
        except IntegrityError as exc:
            raise conflict("Slot already booked") from exc
        self._repo.add(ChatConversation(appointment_id=row.id, patient_id=user_id, doctor_id=body.doctor_id))
        await self._repo.flush()

        # Real-time push notification to the doctor about new appointment request
        p_name = profile.full_name or "A patient"
        await dispatch_notification(
            db=self._repo.session,
            user_id=body.doctor_id,
            title="New Appointment Request",
            body=f"{p_name} booked for {body.appointment_date} at {body.time_slot}.",
            type="appointment_new",
            data={
                "type": "appointment",
                "screen": "doctor_appointment_detail",
                "route": f"/doctor/appointments/{row.id}",
                "resource_id": str(row.id),
                "appointment_id": str(row.id),
            },
            is_urgent=True,
        )

        return AppointmentOut.model_validate(row_dict(row))

    async def list_patient(self, user_id: UUID) -> list[AppointmentOut]:
        rows = await self._repo.list_for_patient(user_id)
        return [AppointmentOut.model_validate(row_dict(r)) for r in rows]

    async def list_doctor(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_for_doctor(user_id))

    async def set_status(self, appointment_id: UUID, doctor_id: UUID, status: str) -> RowOut:
        row = await self._repo.get_for_doctor(appointment_id, doctor_id)
        if row is None:
            raise not_found()
        if status == "completed":
            await credit_doctor_on_complete(self._repo.session, row)
            # Push notification to the patient to review the consultation
            doctor = await self._repo.get_doctor(doctor_id)
            doc_name = (
                f"{getattr(doctor, 'first_name', '') or ''} {getattr(doctor, 'last_name', '') or ''}".strip()
                if doctor
                else "Doctor"
            )
            doc_display = f"Dr. {doc_name}" if not doc_name.lower().startswith("dr.") else doc_name
            await dispatch_notification(
                db=self._repo.session,
                user_id=row.patient_id,
                title="Consultation Completed",
                body=f"Your visit with {doc_display} has ended. Please leave a review.",
                type="appointment_completed",
                data={
                    "type": "appointment_review",
                    "screen": "appointment_review",
                    "route": f"/appointments/{row.id}/review",
                    "resource_id": str(row.id),
                    "appointment_id": str(row.id),
                },
                is_urgent=True,
            )
        elif status == "cancelled":
            try:
                await refund_cancel(self._repo.session, row, cancelled_by="doctor")
            except ValueError as exc:
                raise bad_request(str(exc)) from exc
            # Push notification to patient that doctor cancelled
            doctor = await self._repo.get_doctor(doctor_id)
            doc_name = (
                f"{getattr(doctor, 'first_name', '') or ''} {getattr(doctor, 'last_name', '') or ''}".strip()
                if doctor
                else "Doctor"
            )
            doc_display = f"Dr. {doc_name}" if not doc_name.lower().startswith("dr.") else doc_name
            await dispatch_notification(
                db=self._repo.session,
                user_id=row.patient_id,
                title="Appointment Cancelled",
                body=f"{doc_display} cancelled the appointment scheduled on {row.appointment_date}.",
                type="appointment_cancelled",
                data={
                    "type": "appointment",
                    "screen": "appointment_detail",
                    "route": f"/appointments/{row.id}",
                    "resource_id": str(row.id),
                    "appointment_id": str(row.id),
                },
                is_urgent=True,
            )
        else:
            row.status = status
            await self._repo.flush()
            if status == "confirmed":
                doctor = await self._repo.get_doctor(doctor_id)
                doc_name = (
                    f"{getattr(doctor, 'first_name', '') or ''} {getattr(doctor, 'last_name', '') or ''}".strip()
                    if doctor
                    else "Doctor"
                )
                doc_display = f"Dr. {doc_name}" if not doc_name.lower().startswith("dr.") else doc_name
                await dispatch_notification(
                    db=self._repo.session,
                    user_id=row.patient_id,
                    title="Appointment Confirmed",
                    body=f"{doc_display} confirmed your appointment scheduled on {row.appointment_date} at {row.time_slot}.",
                    type="appointment_confirmed",
                    data={
                        "type": "appointment",
                        "screen": "appointment_detail",
                        "route": f"/appointments/{row.id}",
                        "resource_id": str(row.id),
                        "appointment_id": str(row.id),
                    },
                    is_urgent=True,
                )
        return require_row(row)

    async def list_reviews_for_doctor(self, doctor_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_reviews_for_doctor(doctor_id))

    async def cancel_patient(self, appointment_id: UUID, user_id: UUID) -> RowOut:
        row = await self._repo.get_for_patient(appointment_id, user_id)
        if row is None:
            raise not_found()
        await refund_cancel(self._repo.session, row, cancelled_by="patient")
        # Push notification to doctor that patient cancelled
        p_name = row.patient_name or "Patient"
        await dispatch_notification(
            db=self._repo.session,
            user_id=row.doctor_id,
            title="Appointment Cancelled",
            body=f"{p_name} cancelled their appointment on {row.appointment_date}.",
            type="appointment_cancelled",
            data={
                "type": "appointment",
                "screen": "doctor_appointment_detail",
                "route": f"/doctor/appointments/{row.id}",
                "resource_id": str(row.id),
                "appointment_id": str(row.id),
            },
            is_urgent=True,
        )
        return require_row(row)

    async def create_review(self, user_id: UUID, body: ReviewIn) -> RowOut:
        appt = await self._repo.get_for_patient(body.appointment_id, user_id)
        if appt is None:
            raise not_found()
        row = AppointmentReview(
            appointment_id=appt.id,
            service_id=appt.service_id,
            doctor_id=appt.doctor_id,
            patient_id=user_id,
            rating=body.rating,
            comment=body.comment,
        )
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)
