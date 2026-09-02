from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import (
    Appointment,
    AppointmentReview,
    AppSetting,
    AppSubscription,
    CareSubscription,
    ChatConversation,
    ChatMessage,
    Child,
    ChildFollowupVisit,
    ChildGrowthMeasurement,
    ChildGrowthPeriod,
    ChildGrowthPeriodTranslation,
    ChildMilestoneCheck,
    ChildVaccineRecord,
    DailyTip,
    DailyTipTranslation,
    DoctorAvailabilitySlot,
    DoctorCategory,
    DoctorProfile,
    DoctorService,
    GrowthClinicalAdvice,
    GrowthClinicalAdviceTranslation,
    LegalDocument,
    Notification,
    PatientWallet,
    PatientWalletTransaction,
    PatientWalletWithdrawalRequest,
    Pregnancy,
    PregnancyLog,
    PregnancyWeek,
    PregnancyWeekTranslation,
    Profile,
    SymptomCatalog,
    VaccineDoseSchedule,
)

router = APIRouter(tags=["mother"])


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    account_type: str | None = None
    user_tracking_type: str | None = None
    locale: str | None = None
    dark_mode: bool | None = None
    notifications_enabled: bool | None = None
    fcm_token: str | None = None
    avatar_url: str | None = None
    location: str | None = None
    hospital: str | None = None
    onboarding_complete: bool | None = None


class PregnancyIn(BaseModel):
    lmp_date: date | None = None
    edd: date | None = None
    status: str = "active"
    pregnancy_number: int = 1
    is_first_pregnancy: bool = True
    location: str | None = None
    hospital: str | None = None
    conditions: list[str] = Field(default_factory=list)
    pre_pregnancy_weight: Decimal | None = None
    height_cm: Decimal | None = None
    embryo_transfer_date: date | None = None
    embryo_age_days: int | None = None


class PregnancyLogIn(BaseModel):
    pregnancy_id: UUID
    week_number: int
    weight: Decimal | None = None
    height: Decimal | None = None
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    temperature: Decimal | None = None
    symptoms: list[str] = Field(default_factory=list)
    notes: str | None = None


class ChildIn(BaseModel):
    local_id: str | None = None
    name: str = ""
    gender: str
    birth_date: date
    pregnancy_id: UUID | None = None
    birth_weight: Decimal | None = None
    birth_height: Decimal | None = None
    delivery_type: str | None = None
    gestational_age_weeks: Decimal | None = None
    gestational_age_days: int | None = None
    birth_hospital: str | None = None
    blood_group: str | None = None
    woreda: str | None = None
    photo_url: str | None = None
    is_active: bool = True


class MeasurementIn(BaseModel):
    child_local_id: str
    measured_on: date | None = None
    age_months: Decimal | None = None
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None
    head_circumference_cm: Decimal | None = None
    notes: str | None = None


class MilestoneIn(BaseModel):
    child_local_id: str
    item_key: str


class VaccineIn(BaseModel):
    child_local_id: str
    vaccine_key: str
    vaccine_name: str
    age_months: int | None = None
    received: bool = False
    date_received: date | None = None


class BookIn(BaseModel):
    doctor_id: UUID
    appointment_date: date
    time_slot: str
    service_id: UUID | None = None
    note: str | None = None
    care_subscription_id: UUID | None = None
    payment_method: str | None = None
    chapa_tx_ref: str | None = None
    amount_paid: Decimal = Decimal("0")


class ReviewIn(BaseModel):
    appointment_id: UUID
    rating: Decimal
    comment: str | None = None


class ChatIn(BaseModel):
    body: str = Field(min_length=1)


class WithdrawIn(BaseModel):
    amount: Decimal
    note: str | None = None


@router.get("/me/profile")
async def get_profile(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.id == user.id))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(404, "Profile not found")
    return _row(profile)


@router.patch("/me/profile")
async def patch_profile(body: ProfileUpdate, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.id == user.id))).scalar_one()
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(profile, k, v)
    await db.flush()
    return _row(profile)


@router.get("/pregnancies")
async def list_pregnancies(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Pregnancy).where(Pregnancy.user_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/pregnancies")
async def create_pregnancy(body: PregnancyIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    row = Pregnancy(user_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.post("/pregnancy-logs")
async def create_pregnancy_log(body: PregnancyLogIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    preg = (
        await db.execute(select(Pregnancy).where(Pregnancy.id == body.pregnancy_id, Pregnancy.user_id == user.id))
    ).scalar_one_or_none()
    if preg is None:
        raise HTTPException(404, "Pregnancy not found")
    row = PregnancyLog(**body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/pregnancy-logs")
async def list_pregnancy_logs(user: RequirePatient, db: AsyncSession = Depends(get_db), pregnancy_id: UUID | None = None):
    q = (
        select(PregnancyLog)
        .join(Pregnancy, Pregnancy.id == PregnancyLog.pregnancy_id)
        .where(Pregnancy.user_id == user.id)
    )
    if pregnancy_id:
        q = q.where(PregnancyLog.pregnancy_id == pregnancy_id)
    return [_row(r) for r in (await db.execute(q)).scalars().all()]


@router.get("/cms/pregnancy-weeks")
async def cms_pregnancy_weeks(db: AsyncSession = Depends(get_db), lang: str = "en"):
    weeks = (await db.execute(select(PregnancyWeek).where(PregnancyWeek.is_published.is_(True)))).scalars().all()
    out = []
    for w in weeks:
        item = _row(w)
        tr = (
            await db.execute(
                select(PregnancyWeekTranslation).where(
                    PregnancyWeekTranslation.pregnancy_week_id == w.id,
                    PregnancyWeekTranslation.language_code == lang,
                )
            )
        ).scalar_one_or_none()
        item["translation"] = _row(tr) if tr else None
        out.append(item)
    return out


@router.get("/children")
async def list_children(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(Child).where(Child.user_id == user.id))).scalars().all()]


@router.post("/children")
async def create_child(body: ChildIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    row = Child(user_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.patch("/children/{child_id}")
async def patch_child(child_id: UUID, body: ChildIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Child).where(Child.id == child_id, Child.user_id == user.id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    return _row(row)


@router.get("/cms/child-growth-periods")
async def cms_growth_periods(db: AsyncSession = Depends(get_db), lang: str = "en"):
    periods = (
        await db.execute(select(ChildGrowthPeriod).where(ChildGrowthPeriod.is_published.is_(True)))
    ).scalars().all()
    out = []
    for p in periods:
        item = _row(p)
        tr = (
            await db.execute(
                select(ChildGrowthPeriodTranslation).where(
                    ChildGrowthPeriodTranslation.period_id == p.id,
                    ChildGrowthPeriodTranslation.language_code == lang,
                )
            )
        ).scalar_one_or_none()
        item["translation"] = _row(tr) if tr else None
        out.append(item)
    return out


@router.post("/child-measurements")
async def add_measurement(body: MeasurementIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    data = body.model_dump()
    if data.get("measured_on") is None:
        data.pop("measured_on", None)
    row = ChildGrowthMeasurement(user_id=user.id, **{k: v for k, v in data.items() if v is not None or k == "child_local_id"})
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/child-measurements")
async def list_measurements(user: RequirePatient, child_local_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ChildGrowthMeasurement).where(
                ChildGrowthMeasurement.user_id == user.id,
                ChildGrowthMeasurement.child_local_id == child_local_id,
            )
        )
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/child-milestones")
async def add_milestone(body: MilestoneIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    row = ChildMilestoneCheck(user_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/child-milestones")
async def list_milestones(user: RequirePatient, child_local_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ChildMilestoneCheck).where(
                ChildMilestoneCheck.user_id == user.id,
                ChildMilestoneCheck.child_local_id == child_local_id,
            )
        )
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/child-vaccines")
async def upsert_vaccine(body: VaccineIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    existing = (
        await db.execute(
            select(ChildVaccineRecord).where(
                ChildVaccineRecord.user_id == user.id,
                ChildVaccineRecord.child_local_id == body.child_local_id,
                ChildVaccineRecord.vaccine_key == body.vaccine_key,
            )
        )
    ).scalar_one_or_none()
    if existing:
        for k, v in body.model_dump().items():
            setattr(existing, k, v)
        await db.flush()
        return _row(existing)
    row = ChildVaccineRecord(user_id=user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/child-vaccines")
async def list_vaccines(user: RequirePatient, child_local_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ChildVaccineRecord).where(
                ChildVaccineRecord.user_id == user.id,
                ChildVaccineRecord.child_local_id == child_local_id,
            )
        )
    ).scalars().all()
    return [_row(r) for r in rows]


@router.get("/child-followups")
async def list_followups(user: RequirePatient, child_local_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ChildFollowupVisit).where(
                ChildFollowupVisit.user_id == user.id,
                ChildFollowupVisit.child_local_id == child_local_id,
            )
        )
    ).scalars().all()
    return [_row(r) for r in rows]


@router.get("/cms/vaccine-schedule")
async def vaccine_schedule(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(VaccineDoseSchedule).where(VaccineDoseSchedule.is_published.is_(True)))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.get("/cms/clinical-advice")
async def clinical_advice(db: AsyncSession = Depends(get_db), lang: str = "en"):
    rows = (await db.execute(select(GrowthClinicalAdvice).where(GrowthClinicalAdvice.is_active.is_(True)))).scalars().all()
    out = []
    for r in rows:
        item = _row(r)
        tr = (
            await db.execute(
                select(GrowthClinicalAdviceTranslation).where(
                    GrowthClinicalAdviceTranslation.advice_id == r.id,
                    GrowthClinicalAdviceTranslation.language_code == lang,
                )
            )
        ).scalar_one_or_none()
        item["translation"] = _row(tr) if tr else None
        out.append(item)
    return out


@router.get("/cms/daily-tips")
async def daily_tips(db: AsyncSession = Depends(get_db), week_number: int | None = None, lang: str = "en"):
    q = select(DailyTip).where(DailyTip.is_active.is_(True))
    if week_number is not None:
        q = q.where(DailyTip.week_number == week_number)
    tips = (await db.execute(q)).scalars().all()
    out = []
    for t in tips:
        item = _row(t)
        tr = (
            await db.execute(
                select(DailyTipTranslation).where(
                    DailyTipTranslation.tip_id == t.id,
                    DailyTipTranslation.language_code == lang,
                )
            )
        ).scalar_one_or_none()
        item["translation"] = _row(tr) if tr else None
        out.append(item)
    return out


@router.get("/cms/symptoms")
async def symptoms(db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(SymptomCatalog))).scalars().all()]


@router.get("/cms/legal/{slug}")
async def legal(slug: str, db: AsyncSession = Depends(get_db), locale: str = "en"):
    row = (
        await db.execute(select(LegalDocument).where(LegalDocument.slug == slug, LegalDocument.locale == locale))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    return _row(row)


@router.get("/settings/{setting_id}")
async def get_setting(setting_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppSetting).where(AppSetting.id == setting_id))).scalar_one_or_none()
    return row.data if row else {}


@router.get("/doctors")
async def list_doctors(db: AsyncSession = Depends(get_db), category_id: UUID | None = None, verified_only: bool = True):
    q = select(DoctorProfile)
    if verified_only:
        q = q.where(DoctorProfile.is_verified.is_(True))
    if category_id:
        q = q.where(DoctorProfile.category_id == category_id)
    return [_row(r) for r in (await db.execute(q)).scalars().all()]


@router.get("/doctors/categories")
async def doctor_categories(db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(DoctorCategory).where(DoctorCategory.is_active.is_(True)))).scalars().all()]


@router.get("/doctors/{doctor_id}")
async def doctor_detail(doctor_id: UUID, db: AsyncSession = Depends(get_db)):
    doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(404)
    services = (
        await db.execute(
            select(DoctorService).where(DoctorService.doctor_id == doctor_id, DoctorService.is_active.is_(True))
        )
    ).scalars().all()
    slots = (
        await db.execute(
            select(DoctorAvailabilitySlot).where(
                DoctorAvailabilitySlot.doctor_id == doctor_id,
                DoctorAvailabilitySlot.is_active.is_(True),
            )
        )
    ).scalars().all()
    return {"doctor": _row(doctor), "services": [_row(s) for s in services], "slots": [_row(s) for s in slots]}


@router.post("/appointments")
async def book_appointment(body: BookIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.id == user.id))).scalar_one()
    service = None
    if body.service_id:
        service = (await db.execute(select(DoctorService).where(DoctorService.id == body.service_id))).scalar_one_or_none()
    doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == body.doctor_id))).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(404, "Doctor not found")
    total = service.price if service else Decimal("0")
    prepay = total if doctor.prepayment_mode == "full" else Decimal("0")
    row = Appointment(
        doctor_id=body.doctor_id,
        patient_id=user.id,
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
        amount_paid=body.amount_paid,
        payment_status="paid" if body.amount_paid >= prepay and prepay > 0 else ("unpaid" if prepay > 0 else "waived"),
        payment_method=body.payment_method,
        chapa_tx_ref=body.chapa_tx_ref,
        care_subscription_id=body.care_subscription_id,
        status="pending",
    )
    db.add(row)
    await db.flush()
    db.add(
        ChatConversation(
            appointment_id=row.id,
            patient_id=user.id,
            doctor_id=body.doctor_id,
        )
    )
    await db.flush()
    return _row(row)


@router.get("/appointments")
async def my_appointments(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Appointment).where(Appointment.patient_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: UUID, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    from app.core.services.booking_finance import cancel_appointment as do_cancel

    row = (
        await db.execute(select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == user.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    await do_cancel(db, row, cancelled_by="patient")
    return _row(row)


@router.post("/reviews")
async def create_review(body: ReviewIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    appt = (
        await db.execute(
            select(Appointment).where(Appointment.id == body.appointment_id, Appointment.patient_id == user.id)
        )
    ).scalar_one_or_none()
    if appt is None:
        raise HTTPException(404)
    row = AppointmentReview(
        appointment_id=appt.id,
        service_id=appt.service_id,
        doctor_id=appt.doctor_id,
        patient_id=user.id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/chat/conversations")
async def chat_conversations(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ChatConversation).where(ChatConversation.patient_id == user.id))).scalars().all()
    return [_row(r) for r in rows]


@router.get("/chat/conversations/{conversation_id}/messages")
async def chat_messages(conversation_id: UUID, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    conv = (
        await db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id, ChatConversation.patient_id == user.id)
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(404)
    rows = (
        await db.execute(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/chat/conversations/{conversation_id}/messages")
async def send_chat(conversation_id: UUID, body: ChatIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    from datetime import UTC, datetime

    conv = (
        await db.execute(
            select(ChatConversation).where(ChatConversation.id == conversation_id, ChatConversation.patient_id == user.id)
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(404)
    msg = ChatMessage(conversation_id=conversation_id, sender_id=user.id, body=body.body.strip())
    db.add(msg)
    conv.last_message = body.body.strip()
    conv.last_message_at = datetime.now(UTC)
    conv.doctor_unread_count += 1
    await db.flush()
    return _row(msg)


@router.get("/notifications")
async def notifications(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: UUID, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    from datetime import UTC, datetime

    row = (
        await db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    row.read_at = datetime.now(UTC)
    await db.flush()
    return _row(row)


@router.get("/wallet")
async def wallet(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    w = (await db.execute(select(PatientWallet).where(PatientWallet.patient_id == user.id))).scalar_one_or_none()
    txs = (
        await db.execute(
            select(PatientWalletTransaction)
            .where(PatientWalletTransaction.patient_id == user.id)
            .order_by(PatientWalletTransaction.created_at.desc())
        )
    ).scalars().all()
    return {"wallet": _row(w) if w else None, "transactions": [_row(t) for t in txs]}


@router.post("/wallet/withdraw")
async def wallet_withdraw(body: WithdrawIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
    w = (await db.execute(select(PatientWallet).where(PatientWallet.patient_id == user.id))).scalar_one_or_none()
    if w is None or w.balance < body.amount:
        raise HTTPException(400, "Insufficient balance")
    req = PatientWalletWithdrawalRequest(patient_id=user.id, amount=body.amount, note=body.note)
    db.add(req)
    await db.flush()
    return _row(req)


@router.get("/subscriptions/app")
async def app_subscription(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(AppSubscription).where(AppSubscription.patient_id == user.id, AppSubscription.status == "active")
        )
    ).scalar_one_or_none()
    return _row(row) if row else None


@router.get("/subscriptions/care")
async def care_subscriptions(user: RequirePatient, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(CareSubscription).where(CareSubscription.patient_id == user.id))
    ).scalars().all()
    return [_row(r) for r in rows]
