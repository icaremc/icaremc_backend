from datetime import time
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import RequireDoctor
from app.core.services.booking_finance import cancel_appointment, credit_doctor_on_complete, request_doctor_payout
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import (
    Appointment,
    AppointmentReview,
    AppSetting,
    ChatConversation,
    ChatMessage,
    DoctorAvailabilitySlot,
    DoctorHospitalAffiliation,
    DoctorPayoutMethod,
    DoctorPayoutRequest,
    DoctorProfile,
    DoctorReferral,
    DoctorReferralCommission,
    DoctorService,
    DoctorWallet,
    Hospital,
    Notification,
    WalletTransaction,
)

router = APIRouter(prefix="/doctor", tags=["doctor"])


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    specialty: str | None = None
    hospital: str | None = None
    license_number: str | None = None
    experience_years: int | None = None
    availability: str | None = None
    bio: str | None = None
    category_id: UUID | None = None
    license_image_url: str | None = None
    degree_image_url: str | None = None
    profile_photo_url: str | None = None
    fcm_token: str | None = None
    notifications_enabled: bool | None = None
    dark_mode: bool | None = None
    available_today: bool | None = None
    primary_hospital_id: UUID | None = None
    prepayment_mode: str | None = None
    prepayment_percent: int | None = None


class ServiceIn(BaseModel):
    name: str
    description: str | None = None
    price: Decimal
    currency: str = "ETB"
    is_active: bool = True
    sort_order: int = 0
    image_url: str | None = None
    billing_type: str = "one_time"
    duration_minutes: int = 30
    visits_per_period: int | None = None


class SlotIn(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    hospital_id: UUID | None = None
    slot_duration_minutes: int = 30
    is_active: bool = True


class StatusIn(BaseModel):
    status: str


class PayoutMethodIn(BaseModel):
    holder_name: str
    account_number: str
    bank_name: str
    bank_code: str | None = None
    swift_code: str | None = None
    is_default: bool = False
    currency: str = "ETB"


class PayoutIn(BaseModel):
    amount: Decimal
    payout_method_id: UUID
    note: str | None = None


class ChatIn(BaseModel):
    body: str = Field(min_length=1)


@router.get("/me")
async def me(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == user.id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    return _row(row)


@router.patch("/me")
async def patch_me(body: ProfileUpdate, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == user.id))).scalar_one()
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    return _row(row)


@router.get("/services")
async def list_services(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(DoctorService).where(DoctorService.doctor_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/services")
async def create_service(body: ServiceIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = DoctorService(doctor_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.patch("/services/{service_id}")
async def patch_service(service_id: UUID, body: ServiceIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(DoctorService).where(DoctorService.id == service_id, DoctorService.doctor_id == user.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    return _row(row)


@router.delete("/services/{service_id}")
async def delete_service(service_id: UUID, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    open_count = (
        await db.execute(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.service_id == service_id,
                Appointment.status.in_(["pending", "confirmed", "awaiting_patient_confirmation"]),
            )
        )
    ).scalar_one()
    if open_count:
        raise HTTPException(400, "Service has open bookings")
    row = (
        await db.execute(select(DoctorService).where(DoctorService.id == service_id, DoctorService.doctor_id == user.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    await db.delete(row)
    await db.flush()
    return {"ok": True}


@router.get("/slots")
async def list_slots(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(DoctorAvailabilitySlot).where(DoctorAvailabilitySlot.doctor_id == user.id))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/slots")
async def create_slot(body: SlotIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = DoctorAvailabilitySlot(doctor_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.delete("/slots/{slot_id}")
async def delete_slot(slot_id: UUID, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(DoctorAvailabilitySlot).where(
                DoctorAvailabilitySlot.id == slot_id,
                DoctorAvailabilitySlot.doctor_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    await db.delete(row)
    await db.flush()
    return {"ok": True}


@router.get("/appointments")
async def appointments(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Appointment).where(Appointment.doctor_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/appointments/{appointment_id}/status")
async def set_status(appointment_id: UUID, body: StatusIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(Appointment).where(Appointment.id == appointment_id, Appointment.doctor_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    if body.status == "completed":
        await credit_doctor_on_complete(db, row)
    elif body.status == "cancelled":
        await cancel_appointment(db, row, cancelled_by="doctor")
    else:
        row.status = body.status
        await db.flush()
    return _row(row)


@router.get("/wallet")
async def wallet(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    w = (await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == user.id))).scalar_one_or_none()
    txs = (
        await db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.doctor_id == user.id)
            .order_by(WalletTransaction.created_at.desc())
        )
    ).scalars().all()
    return {"wallet": _row(w) if w else None, "transactions": [_row(t) for t in txs]}


@router.get("/payout-methods")
async def payout_methods(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(DoctorPayoutMethod).where(DoctorPayoutMethod.doctor_id == user.id))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/payout-methods")
async def create_payout_method(body: PayoutMethodIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    row = DoctorPayoutMethod(doctor_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.post("/payouts")
async def create_payout(body: PayoutIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    try:
        req = await request_doctor_payout(
            db,
            doctor_id=user.id,
            amount=body.amount,
            payout_method_id=body.payout_method_id,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _row(req)


@router.get("/payouts")
async def list_payouts(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(DoctorPayoutRequest).where(DoctorPayoutRequest.doctor_id == user.id))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.get("/referrals")
async def referrals(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == user.id))).scalar_one()
    refs = (await db.execute(select(DoctorReferral).where(DoctorReferral.doctor_id == user.id))).scalars().all()
    commissions = (
        await db.execute(select(DoctorReferralCommission).where(DoctorReferralCommission.doctor_id == user.id))
    ).scalars().all()
    return {
        "referral_code": doctor.referral_code,
        "referrals": [_row(r) for r in refs],
        "commissions": [_row(c) for c in commissions],
    }


@router.get("/hospitals")
async def hospitals(db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(Hospital).where(Hospital.is_active.is_(True)))).scalars().all()]


@router.post("/hospitals/{hospital_id}/affiliate")
async def affiliate(hospital_id: UUID, user: RequireDoctor, db: AsyncSession = Depends(get_db), is_primary: bool = False):
    row = DoctorHospitalAffiliation(doctor_id=user.id, hospital_id=hospital_id, is_primary=is_primary)
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/chat/conversations")
async def conversations(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ChatConversation).where(ChatConversation.doctor_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.get("/chat/conversations/{conversation_id}/messages")
async def messages(conversation_id: UUID, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    conv = (
        await db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id, ChatConversation.doctor_id == user.id)
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(404)
    rows = (
        await db.execute(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/chat/conversations/{conversation_id}/messages")
async def send_message(conversation_id: UUID, body: ChatIn, user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    from datetime import UTC, datetime

    conv = (
        await db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id, ChatConversation.doctor_id == user.id)
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(404)
    msg = ChatMessage(conversation_id=conversation_id, sender_id=user.id, body=body.body.strip())
    db.add(msg)
    conv.last_message = body.body.strip()
    conv.last_message_at = datetime.now(UTC)
    conv.patient_unread_count += 1
    await db.flush()
    return _row(msg)


@router.get("/notifications")
async def notifications(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.get("/reviews")
async def reviews(user: RequireDoctor, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AppointmentReview).where(AppointmentReview.doctor_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.get("/settings/version")
async def version_policy(db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppSetting).where(AppSetting.id == "doctors_version"))).scalar_one_or_none()
    return row.data if row else {}
