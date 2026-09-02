from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import RequireAdmin
from app.core.security.tokens import hash_password
from app.core.services.auth_service import ensure_admin
from app.persistence.sqlalchemy.deps import get_db
from app.persistence.sqlalchemy.models import (
    AdminActivityLog,
    AdminDocument,
    AdminUser,
    Appointment,
    AppSetting,
    AppSubscription,
    Child,
    ChildFollowupVisitTemplate,
    ChildGrowthPeriod,
    ChildGrowthPeriodTranslation,
    DailyTip,
    DailyTipTranslation,
    DocumentDelivery,
    DoctorCategory,
    DoctorCategoryTranslation,
    DoctorPayoutRequest,
    DoctorProfile,
    DoctorWallet,
    GrowthClinicalAdvice,
    GrowthClinicalAdviceTranslation,
    Hospital,
    LegalDocument,
    PlatformActivityLog,
    Pregnancy,
    PregnancyWeek,
    PregnancyWeekTranslation,
    Profile,
    User,
    WalletTransaction,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class SettingIn(BaseModel):
    data: dict


class DoctorVerifyIn(BaseModel):
    is_verified: bool


class PayoutActionIn(BaseModel):
    status: str
    admin_note: str | None = None


class AdminCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = "Admin"
    admin_role: str = "viewer"


class SubscriptionGrantIn(BaseModel):
    patient_id: UUID
    days: int = 365
    amount_paid: Decimal = Decimal("0")
    admin_receipt_url: str | None = None


class HospitalIn(BaseModel):
    name: str
    slug: str
    description: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    image_url: str | None = None
    is_active: bool = True
    sort_order: int = 0


class CategoryIn(BaseModel):
    name: str
    slug: str
    is_active: bool = True
    sort_order: int = 1
    image_url: str | None = None
    care_focus: str = "both"


class WeekIn(BaseModel):
    week_number: int
    trimester: int
    image_note: str | None = None
    image_url: str | None = None
    is_published: bool = False


class WeekTranslationIn(BaseModel):
    language_code: str
    title: str
    subtitle: str | None = None
    baby: str | None = None
    stage: str | None = None
    mother_changes: str | None = None
    recommendations: str | None = None
    warning_signs: str | None = None
    sections: list = Field(default_factory=list)


class LegalIn(BaseModel):
    slug: str
    locale: str = "en"
    title: str
    sections: list = Field(default_factory=list)


async def _log(db: AsyncSession, admin: RequireAdmin, event_type: str, event_label: str, **kwargs):
    db.add(
        AdminActivityLog(
            actor_id=admin.id,
            actor_role=admin.admin_role,
            event_type=event_type,
            event_label=event_label,
            metadata_=kwargs or {},
        )
    )


@router.get("/dashboard")
async def dashboard(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    async def count(model):
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    return {
        "profiles": await count(Profile),
        "pregnancies": await count(Pregnancy),
        "children": await count(Child),
        "doctors": await count(DoctorProfile),
        "appointments": await count(Appointment),
        "pending_appointments": (
            await db.execute(select(func.count()).select_from(Appointment).where(Appointment.status == "pending"))
        ).scalar_one(),
        "admin_users": await count(AdminUser),
    }


@router.get("/users")
async def list_users(user: RequireAdmin, db: AsyncSession = Depends(get_db), limit: int = 100, offset: int = 0):
    rows = (await db.execute(select(Profile).offset(offset).limit(limit))).scalars().all()
    return [_row(r) for r in rows]


@router.get("/users/{user_id}")
async def user_detail(user_id: UUID, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    profile = (await db.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(404)
    pregnancies = (await db.execute(select(Pregnancy).where(Pregnancy.user_id == user_id))).scalars().all()
    children = (await db.execute(select(Child).where(Child.user_id == user_id))).scalars().all()
    return {"profile": _row(profile), "pregnancies": [_row(p) for p in pregnancies], "children": [_row(c) for c in children]}


@router.get("/doctors")
async def list_doctors(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(DoctorProfile))).scalars().all()]


@router.post("/doctors/{doctor_id}/verify")
async def verify_doctor(doctor_id: UUID, body: DoctorVerifyIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    row.is_verified = body.is_verified
    await _log(db, user, "doctor.verify", "Doctor verification updated", doctor_id=str(doctor_id))
    await db.flush()
    return _row(row)


@router.get("/appointments")
async def list_appointments(user: RequireAdmin, db: AsyncSession = Depends(get_db), limit: int = 100):
    rows = (await db.execute(select(Appointment).order_by(Appointment.created_at.desc()).limit(limit))).scalars().all()
    return [_row(r) for r in rows]


@router.get("/settings/{setting_id}")
async def get_setting(setting_id: str, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppSetting).where(AppSetting.id == setting_id))).scalar_one_or_none()
    return {"id": setting_id, "data": row.data if row else {}}


@router.put("/settings/{setting_id}")
async def put_setting(setting_id: str, body: SettingIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppSetting).where(AppSetting.id == setting_id))).scalar_one_or_none()
    if row is None:
        row = AppSetting(id=setting_id, data=body.data)
        db.add(row)
    else:
        row.data = body.data
    await _log(db, user, "settings.update", f"Updated {setting_id}")
    await db.flush()
    return {"id": setting_id, "data": row.data}


@router.get("/payout-requests")
async def payout_requests(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(DoctorPayoutRequest).order_by(DoctorPayoutRequest.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/payout-requests/{request_id}")
async def payout_action(request_id: UUID, body: PayoutActionIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    req = (await db.execute(select(DoctorPayoutRequest).where(DoctorPayoutRequest.id == request_id))).scalar_one_or_none()
    if req is None:
        raise HTTPException(404)
    wallet = (await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == req.doctor_id))).scalar_one()
    if body.status == "rejected" and req.status == "pending":
        wallet.pending_balance -= req.amount
        wallet.available_balance += req.amount
        db.add(
            WalletTransaction(
                doctor_id=req.doctor_id,
                amount=req.amount,
                is_credit=True,
                type="payout_release",
                payout_request_id=req.id,
            )
        )
    elif body.status == "completed" and req.status in ("pending", "approved"):
        wallet.pending_balance -= req.amount
        db.add(
            WalletTransaction(
                doctor_id=req.doctor_id,
                amount=req.amount,
                is_credit=False,
                type="payout_paid",
                payout_request_id=req.id,
            )
        )
        req.payment_date = datetime.now(UTC)
    req.status = body.status
    req.admin_note = body.admin_note
    await db.flush()
    return _row(req)


@router.get("/wallet-transactions")
async def wallet_transactions(user: RequireAdmin, db: AsyncSession = Depends(get_db), limit: int = 100):
    rows = (
        await db.execute(select(WalletTransaction).order_by(WalletTransaction.created_at.desc()).limit(limit))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/membership/grant")
async def grant_membership(body: SubscriptionGrantIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    now = datetime.now(UTC)
    row = AppSubscription(
        patient_id=body.patient_id,
        plan="yearly",
        status="active",
        starts_at=now,
        ends_at=now + timedelta(days=body.days),
        amount_paid=body.amount_paid,
        payment_method="admin",
        admin_receipt_url=body.admin_receipt_url,
    )
    db.add(row)
    await db.flush()
    return _row(row)


@router.post("/membership/{subscription_id}/revoke")
async def revoke_membership(subscription_id: UUID, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(AppSubscription).where(AppSubscription.id == subscription_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    row.status = "cancelled"
    await db.flush()
    return _row(row)


@router.get("/membership")
async def list_membership(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(AppSubscription).order_by(AppSubscription.created_at.desc()))).scalars().all()]


@router.get("/admins")
async def list_admins(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(AdminUser))).scalars().all()]


@router.post("/admins")
async def create_admin(body: AdminCreateIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    if user.admin_role != "super_admin":
        raise HTTPException(403, "super_admin required")
    admin_id = await ensure_admin(
        db, email=body.email, password=body.password, full_name=body.full_name, admin_role=body.admin_role
    )
    return {"id": str(admin_id)}


@router.get("/hospitals")
async def list_hospitals(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(Hospital))).scalars().all()]


@router.post("/hospitals")
async def create_hospital(body: HospitalIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = Hospital(**body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.patch("/hospitals/{hospital_id}")
async def patch_hospital(hospital_id: UUID, body: HospitalIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Hospital).where(Hospital.id == hospital_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await db.flush()
    return _row(row)


@router.get("/doctor-categories")
async def categories(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(DoctorCategory))).scalars().all()]


@router.post("/doctor-categories")
async def create_category(body: CategoryIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = DoctorCategory(**body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/pregnancy-weeks")
async def pregnancy_weeks(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(PregnancyWeek))).scalars().all()]


@router.post("/pregnancy-weeks")
async def create_week(body: WeekIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = PregnancyWeek(**body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.post("/pregnancy-weeks/{week_id}/translations")
async def week_translation(week_id: UUID, body: WeekTranslationIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = PregnancyWeekTranslation(pregnancy_week_id=week_id, **body.model_dump())
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/child-growth-periods")
async def growth_periods(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(ChildGrowthPeriod))).scalars().all()]


@router.get("/followup-templates")
async def followup_templates(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(ChildFollowupVisitTemplate))).scalars().all()]


@router.get("/legal-documents")
async def legal_docs(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(LegalDocument))).scalars().all()]


@router.put("/legal-documents")
async def upsert_legal(body: LegalIn, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(LegalDocument).where(LegalDocument.slug == body.slug, LegalDocument.locale == body.locale)
        )
    ).scalar_one_or_none()
    if row is None:
        row = LegalDocument(**body.model_dump())
        db.add(row)
    else:
        row.title = body.title
        row.sections = body.sections
    await db.flush()
    return _row(row)


@router.get("/documents")
async def documents(user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    return [_row(r) for r in (await db.execute(select(AdminDocument))).scalars().all()]


@router.post("/documents/{document_id}/deliver")
async def deliver_document(document_id: UUID, recipient_id: UUID, user: RequireAdmin, db: AsyncSession = Depends(get_db)):
    row = DocumentDelivery(document_id=document_id, recipient_id=recipient_id, sent_by=user.id)
    db.add(row)
    await db.flush()
    return _row(row)


@router.get("/activity/admin")
async def admin_activity(user: RequireAdmin, db: AsyncSession = Depends(get_db), limit: int = 100):
    rows = (
        await db.execute(select(AdminActivityLog).order_by(AdminActivityLog.created_at.desc()).limit(limit))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.get("/activity/platform")
async def platform_activity(user: RequireAdmin, db: AsyncSession = Depends(get_db), limit: int = 100):
    rows = (
        await db.execute(select(PlatformActivityLog).order_by(PlatformActivityLog.created_at.desc()).limit(limit))
    ).scalars().all()
    return [_row(r) for r in rows]


@router.post("/bootstrap-super-admin")
async def bootstrap_super_admin(
    body: AdminCreateIn,
    db: AsyncSession = Depends(get_db),
):
    """ponytail: one-shot bootstrap when no admins exist; lock down in prod via empty table check."""
    count = (await db.execute(select(func.count()).select_from(AdminUser))).scalar_one()
    if count > 0:
        raise HTTPException(403, "Admins already exist")
    admin_id = await ensure_admin(
        db, email=body.email, password=body.password, full_name=body.full_name, admin_role="super_admin"
    )
    return {"id": str(admin_id)}
