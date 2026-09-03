from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.api.v1.schemas import RowOut
from app.core.security.deps import AuthUser
from app.core.services.auth_service import ensure_admin
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
    DocumentDelivery,
    DoctorCategory,
    DoctorPayoutRequest,
    DoctorProfile,
    DoctorWallet,
    Hospital,
    LegalDocument,
    PlatformActivityLog,
    Pregnancy,
    PregnancyWeek,
    PregnancyWeekTranslation,
    Profile,
    WalletTransaction,
)
from app.resources.admin.repository import AdminRepository
from app.resources.admin.schemas import (
    AdminCreateIn,
    CategoryIn,
    DoctorVerifyIn,
    HospitalIn,
    LegalIn,
    PayoutActionIn,
    SettingIn,
    SubscriptionGrantIn,
    WeekIn,
    WeekTranslationIn,
)
from app.resources.errors import forbidden, not_found
from app.resources.serialize import require_row, to_rows


class AdminService:
    def __init__(self, repo: AdminRepository) -> None:
        self._repo = repo

    async def _log(self, admin: AuthUser, event_type: str, event_label: str, **kwargs: object) -> None:
        self._repo.session.add(
            AdminActivityLog(
                actor_id=admin.id,
                actor_role=admin.admin_role,
                event_type=event_type,
                event_label=event_label,
                metadata_=kwargs or {},
            )
        )

    async def dashboard(self) -> dict[str, object]:
        async def count(model: type[object]) -> int:
            return int((await self._repo.session.execute(select(func.count()).select_from(model))).scalar_one())

        return {
            "profiles": await count(Profile),
            "pregnancies": await count(Pregnancy),
            "children": await count(Child),
            "doctors": await count(DoctorProfile),
            "appointments": await count(Appointment),
            "pending_appointments": int(
                (
                    await self._repo.session.execute(
                        select(func.count()).select_from(Appointment).where(Appointment.status == "pending")
                    )
                ).scalar_one()
            ),
            "admin_users": await count(AdminUser),
        }

    async def list_users(self, limit: int, offset: int) -> list[RowOut]:
        rows = (await self._repo.session.execute(select(Profile).offset(offset).limit(limit))).scalars().all()
        return to_rows(list(rows))

    async def user_detail(self, user_id: UUID) -> dict[str, object]:
        profile = (await self._repo.session.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()
        if profile is None:
            raise not_found()
        pregnancies = (await self._repo.session.execute(select(Pregnancy).where(Pregnancy.user_id == user_id))).scalars().all()
        children = (await self._repo.session.execute(select(Child).where(Child.user_id == user_id))).scalars().all()
        return {
            "profile": require_row(profile),
            "pregnancies": to_rows(list(pregnancies)),
            "children": to_rows(list(children)),
        }

    async def list_doctors(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(DoctorProfile))).scalars().all()))

    async def verify_doctor(self, doctor_id: UUID, body: DoctorVerifyIn, admin: AuthUser) -> RowOut:
        row = (await self._repo.session.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))).scalar_one_or_none()
        if row is None:
            raise not_found()
        row.is_verified = body.is_verified
        await self._log(admin, "doctor.verify", "Doctor verification updated", doctor_id=str(doctor_id))
        await self._repo.session.flush()
        return require_row(row)

    async def list_appointments(self, limit: int) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(select(Appointment).order_by(Appointment.created_at.desc()).limit(limit))
        ).scalars().all()
        return to_rows(list(rows))

    async def get_setting(self, setting_id: str) -> dict[str, object]:
        row = (await self._repo.session.execute(select(AppSetting).where(AppSetting.id == setting_id))).scalar_one_or_none()
        return {"id": setting_id, "data": row.data if row else {}}

    async def put_setting(self, setting_id: str, body: SettingIn, admin: AuthUser) -> dict[str, object]:
        row = (await self._repo.session.execute(select(AppSetting).where(AppSetting.id == setting_id))).scalar_one_or_none()
        if row is None:
            row = AppSetting(id=setting_id, data=body.data)
            self._repo.session.add(row)
        else:
            row.data = body.data
        await self._log(admin, "settings.update", f"Updated {setting_id}")
        await self._repo.session.flush()
        return {"id": setting_id, "data": row.data}

    async def payout_requests(self) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(select(DoctorPayoutRequest).order_by(DoctorPayoutRequest.created_at.desc()))
        ).scalars().all()
        return to_rows(list(rows))

    async def payout_action(self, request_id: UUID, body: PayoutActionIn) -> RowOut:
        req = (
            await self._repo.session.execute(select(DoctorPayoutRequest).where(DoctorPayoutRequest.id == request_id))
        ).scalar_one_or_none()
        if req is None:
            raise not_found()
        wallet = (await self._repo.session.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == req.doctor_id))).scalar_one()
        if body.status == "rejected" and req.status == "pending":
            wallet.pending_balance -= req.amount
            wallet.available_balance += req.amount
            self._repo.session.add(
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
            self._repo.session.add(
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
        await self._repo.session.flush()
        return require_row(req)

    async def wallet_transactions(self, limit: int) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(select(WalletTransaction).order_by(WalletTransaction.created_at.desc()).limit(limit))
        ).scalars().all()
        return to_rows(list(rows))

    async def grant_membership(self, body: SubscriptionGrantIn) -> RowOut:
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
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def revoke_membership(self, subscription_id: UUID) -> RowOut:
        row = (
            await self._repo.session.execute(select(AppSubscription).where(AppSubscription.id == subscription_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        row.status = "cancelled"
        await self._repo.session.flush()
        return require_row(row)

    async def list_membership(self) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(select(AppSubscription).order_by(AppSubscription.created_at.desc()))
        ).scalars().all()
        return to_rows(list(rows))

    async def list_admins(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(AdminUser))).scalars().all()))

    async def create_admin(self, body: AdminCreateIn, actor: AuthUser) -> dict[str, str]:
        if actor.admin_role != "super_admin":
            raise forbidden("super_admin required")
        admin_id = await ensure_admin(
            self._repo.session, email=body.email, password=body.password, full_name=body.full_name, admin_role=body.admin_role
        )
        return {"id": str(admin_id)}

    async def list_hospitals(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(Hospital))).scalars().all()))

    async def create_hospital(self, body: HospitalIn) -> RowOut:
        row = Hospital(**body.model_dump())
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def patch_hospital(self, hospital_id: UUID, body: HospitalIn) -> RowOut:
        row = (await self._repo.session.execute(select(Hospital).where(Hospital.id == hospital_id))).scalar_one_or_none()
        if row is None:
            raise not_found()
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self._repo.session.flush()
        return require_row(row)

    async def categories(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(DoctorCategory))).scalars().all()))

    async def create_category(self, body: CategoryIn) -> RowOut:
        row = DoctorCategory(**body.model_dump())
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def pregnancy_weeks(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(PregnancyWeek))).scalars().all()))

    async def create_week(self, body: WeekIn) -> RowOut:
        row = PregnancyWeek(**body.model_dump())
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def week_translation(self, week_id: UUID, body: WeekTranslationIn) -> RowOut:
        row = PregnancyWeekTranslation(pregnancy_week_id=week_id, **body.model_dump())
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def growth_periods(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(ChildGrowthPeriod))).scalars().all()))

    async def followup_templates(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(ChildFollowupVisitTemplate))).scalars().all()))

    async def legal_docs(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(LegalDocument))).scalars().all()))

    async def upsert_legal(self, body: LegalIn) -> RowOut:
        row = (
            await self._repo.session.execute(
                select(LegalDocument).where(LegalDocument.slug == body.slug, LegalDocument.locale == body.locale)
            )
        ).scalar_one_or_none()
        if row is None:
            row = LegalDocument(**body.model_dump())
            self._repo.session.add(row)
        else:
            row.title = body.title
            row.sections = body.sections
        await self._repo.session.flush()
        return require_row(row)

    async def documents(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(AdminDocument))).scalars().all()))

    async def deliver_document(self, document_id: UUID, recipient_id: UUID, sender_id: UUID) -> RowOut:
        row = DocumentDelivery(document_id=document_id, recipient_id=recipient_id, sent_by=sender_id)
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def admin_activity(self, limit: int) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(select(AdminActivityLog).order_by(AdminActivityLog.created_at.desc()).limit(limit))
        ).scalars().all()
        return to_rows(list(rows))

    async def platform_activity(self, limit: int) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(
                select(PlatformActivityLog).order_by(PlatformActivityLog.created_at.desc()).limit(limit)
            )
        ).scalars().all()
        return to_rows(list(rows))

    async def bootstrap_super_admin(self, body: AdminCreateIn) -> dict[str, str]:
        count = (await self._repo.session.execute(select(func.count()).select_from(AdminUser))).scalar_one()
        if count > 0:
            raise forbidden("Admins already exist")
        admin_id = await ensure_admin(
            self._repo.session, email=body.email, password=body.password, full_name=body.full_name, admin_role="super_admin"
        )
        return {"id": str(admin_id)}
