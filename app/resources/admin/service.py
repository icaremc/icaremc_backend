from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.api.v1.schemas import RowOut
from app.core.security.deps import AuthUser
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
    GrowthClinicalAdvice,
    GrowthClinicalAdviceTranslation,
    DailyTip,
    DailyTipTranslation,
    DocumentDelivery,
    DoctorCategory,
    DoctorCategoryTranslation,
    DoctorPayoutRequest,
    DoctorProfile,
    DoctorReferral,
    DoctorReferralCommission,
    DoctorService,
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
    AdminPatchIn,
    AppointmentStatusIn,
    CategoryIn,
    CategoryPatchIn,
    CategoryTranslationIn,
    DoctorBookingIn,
    DailyTipIn,
    DailyTipPatchIn,
    ClinicalAdviceIn,
    ClinicalAdvicePatchIn,
    ClinicalAdviceTranslationIn,
    DailyTipTranslationIn,
    DoctorVerifyIn,
    DocumentIn,
    FollowupTemplateIn,
    FollowupTemplatePatchIn,
    GrowthPeriodIn,
    GrowthPeriodPatchIn,
    GrowthPeriodTranslationIn,
    HospitalIn,
    LegalIn,
    PayoutActionIn,
    SettingIn,
    SubscriptionGrantIn,
    WeekIn,
    WeekPatchIn,
    WeekTranslationIn,
)
from app.resources.errors import bad_request, forbidden, not_found
from app.resources.auth.repository import SqlAlchemyAuthRepository
from app.resources.auth.service import AuthService
from app.resources.serialize import require_row, to_rows

_APPOINTMENT_STATUSES = frozenset({"pending", "confirmed", "completed", "cancelled"})
_ADMIN_ROLES = frozenset({"super_admin", "content_admin", "support", "viewer"})


class AdminService:
    def __init__(self, repo: AdminRepository) -> None:
        self._repo = repo

    def _auth(self) -> AuthService:
        return AuthService(SqlAlchemyAuthRepository(self._repo.session))

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

        # Appointment Payments
        appt_payments_row = (
            await self._repo.session.execute(
                select(func.sum(Appointment.amount_paid), func.count(Appointment.id)).where(
                    Appointment.payment_status == "paid", Appointment.status == "completed"
                )
            )
        ).one()
        appt_payments_sum = float(appt_payments_row[0] or 0)
        appt_payments_count = int(appt_payments_row[1] or 0)

        # Doctor Earnings
        doc_earnings_row = (
            await self._repo.session.execute(
                select(func.sum(WalletTransaction.amount), func.count(WalletTransaction.id)).where(
                    WalletTransaction.type == "appointment_earning"
                )
            )
        ).one()
        doc_earnings_sum = float(doc_earnings_row[0] or 0)
        doc_earnings_count = int(doc_earnings_row[1] or 0)

        # Subscriptions
        sub_payments_row = (
            await self._repo.session.execute(
                select(func.sum(AppSubscription.amount_paid), func.count(AppSubscription.id)).where(
                    AppSubscription.status == "active"
                )
            )
        ).one()
        sub_payments_sum = float(sub_payments_row[0] or 0)
        sub_payments_count = int(sub_payments_row[1] or 0)

        # Commission
        comm_row = (
            await self._repo.session.execute(select(func.sum(DoctorReferralCommission.commission_amount)))
        ).scalar_one_or_none()
        commission_sum = float(comm_row or 0)

        # Charts
        # 1. Appointment Payments Chart
        appt_chart_rows = (
            await self._repo.session.execute(
                select(func.date(Appointment.created_at), func.sum(Appointment.amount_paid))
                .where(Appointment.payment_status == "paid", Appointment.status == "completed")
                .group_by(func.date(Appointment.created_at))
                .order_by(func.date(Appointment.created_at))
            )
        ).all()
        appointment_payments_chart = [{"date": str(r[0]), "amount": float(r[1] or 0)} for r in appt_chart_rows]

        # 2. Doctor Earnings Chart
        doc_earnings_chart_rows = (
            await self._repo.session.execute(
                select(func.date(WalletTransaction.created_at), func.sum(WalletTransaction.amount))
                .where(WalletTransaction.type == "appointment_earning")
                .group_by(func.date(WalletTransaction.created_at))
                .order_by(func.date(WalletTransaction.created_at))
            )
        ).all()
        doctor_earnings_chart = [{"date": str(r[0]), "amount": float(r[1] or 0)} for r in doc_earnings_chart_rows]

        # 3. Subscriptions Chart
        sub_chart_rows = (
            await self._repo.session.execute(
                select(func.date(AppSubscription.created_at), func.sum(AppSubscription.amount_paid))
                .where(AppSubscription.status == "active")
                .group_by(func.date(AppSubscription.created_at))
                .order_by(func.date(AppSubscription.created_at))
            )
        ).all()
        subscription_payments_chart = [{"date": str(r[0]), "amount": float(r[1] or 0)} for r in sub_chart_rows]

        # 4. Commission Chart
        comm_chart_rows = (
            await self._repo.session.execute(
                select(func.date(DoctorReferralCommission.created_at), func.sum(DoctorReferralCommission.commission_amount))
                .group_by(func.date(DoctorReferralCommission.created_at))
                .order_by(func.date(DoctorReferralCommission.created_at))
            )
        ).all()
        commission_chart = [{"date": str(r[0]), "amount": float(r[1] or 0)} for r in comm_chart_rows]

        total_transactions = doc_earnings_count + sub_payments_count

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
            "transactions_count": total_transactions,
            "appointment_payments_sum": appt_payments_sum,
            "appointment_payments_count": appt_payments_count,
            "doctor_earnings_sum": doc_earnings_sum,
            "doctor_earnings_count": doc_earnings_count,
            "subscription_payments_sum": sub_payments_sum,
            "subscription_payments_count": sub_payments_count,
            "commission_sum": commission_sum,
            "commission_growth": 0.0,
            "appointment_payments_chart": appointment_payments_chart,
            "doctor_earnings_chart": doctor_earnings_chart,
            "subscription_payments_chart": subscription_payments_chart,
            "commission_chart": commission_chart,
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

    async def get_user_referral(self, user_id: UUID) -> dict[str, object]:
        profile = (await self._repo.session.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()
        if profile is None:
            raise not_found("User not found")
        
        doctor_name = None
        if profile.referred_by_doctor_id:
            doctor = (await self._repo.session.execute(
                select(DoctorProfile).where(DoctorProfile.id == profile.referred_by_doctor_id)
            )).scalar_one_or_none()
            if doctor:
                parts = [p for p in [doctor.first_name, doctor.last_name] if p and str(p).strip()]
                doctor_name = " ".join(parts) if parts else None
        
        referral_record = None
        if profile.referred_by_doctor_id:
            referral_record = (await self._repo.session.execute(
                select(DoctorReferral).where(
                    DoctorReferral.patient_id == user_id, 
                    DoctorReferral.doctor_id == profile.referred_by_doctor_id
                )
            )).scalar_one_or_none()

        return {
            "referral": {
                "referralCodeUsed": profile.referral_code_used,
                "referredByDoctorId": str(profile.referred_by_doctor_id) if profile.referred_by_doctor_id else None,
                "referredByDoctorName": doctor_name,
                "referredAt": referral_record.created_at.isoformat() if referral_record and referral_record.created_at else None,
                "canApplyCode": profile.referred_by_doctor_id is None
            }
        }

    async def apply_user_referral(self, user_id: UUID, code: str) -> dict[str, object]:
        profile = (await self._repo.session.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()
        if profile is None:
            raise not_found("User not found")
        if profile.referred_by_doctor_id is not None:
            raise bad_request("User already has a referral")
            
        doctor = (await self._repo.session.execute(
            select(DoctorProfile).where(DoctorProfile.referral_code == code.strip().upper())
        )).scalar_one_or_none()
        if doctor is None:
            raise not_found("Doctor referral code not found")
            
        profile.referral_code_used = doctor.referral_code
        profile.referred_by_doctor_id = doctor.id
        
        ref = DoctorReferral(patient_id=user_id, doctor_id=doctor.id, referral_code=doctor.referral_code)
        self._repo.session.add(ref)
        await self._repo.session.flush()
        
        res = await self.get_user_referral(user_id)
        res["applied"] = {
            "referralCode": doctor.referral_code,
            "doctorId": str(doctor.id)
        }
        return res

    async def list_doctors(self) -> list[RowOut]:
        return to_rows(list((await self._repo.session.execute(select(DoctorProfile))).scalars().all()))

    async def list_doctor_services(self, doctor_id: UUID) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(
                select(DoctorService).where(DoctorService.doctor_id == doctor_id)
            )
        ).scalars().all()
        return to_rows(list(rows))

    async def replace_doctor_booking(
        self, doctor_id: UUID, body: DoctorBookingIn, admin: AuthUser
    ) -> dict[str, object]:
        doctor = (
            await self._repo.session.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))
        ).scalar_one_or_none()
        if doctor is None:
            raise not_found()

        if body.currency:
            # ponytail: doctor_profiles may not have currency; ignore if attr missing
            if hasattr(doctor, "currency"):
                doctor.currency = body.currency

        if body.services is not None:
            existing = list(
                (
                    await self._repo.session.execute(
                        select(DoctorService).where(DoctorService.doctor_id == doctor_id)
                    )
                ).scalars().all()
            )
            kept = {str(s.id) for s in body.services if s.id is not None}
            for row in existing:
                if str(row.id) not in kept:
                    await self._repo.session.delete(row)

            for index, service in enumerate(body.services):
                name = service.name.strip()
                if not name:
                    continue
                if service.id is not None:
                    row = next((r for r in existing if r.id == service.id), None)
                    if row is None:
                        raise bad_request(f"Unknown service id {service.id}")
                    row.name = name
                    row.description = service.description
                    row.price = service.price
                    row.is_active = service.is_active
                    row.sort_order = index
                else:
                    self._repo.session.add(
                        DoctorService(
                            doctor_id=doctor_id,
                            name=name,
                            description=service.description,
                            price=service.price,
                            is_active=service.is_active,
                            sort_order=index,
                        )
                    )

        await self._log(admin, "doctor.booking", "Doctor booking services updated", doctor_id=str(doctor_id))
        await self._repo.session.flush()
        services = await self.list_doctor_services(doctor_id)
        return {"doctor": require_row(doctor), "services": services}

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

    async def patch_appointment(self, appointment_id: UUID, body: AppointmentStatusIn, admin: AuthUser) -> RowOut:
        if body.status not in _APPOINTMENT_STATUSES:
            raise bad_request("status must be pending, confirmed, completed, or cancelled")
        row = (
            await self._repo.session.execute(select(Appointment).where(Appointment.id == appointment_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        previous = row.status
        row.status = body.status
        if body.status == "cancelled":
            row.cancelled_by = "admin"
        await self._log(
            admin,
            "appointment.status",
            "Appointment status updated",
            appointment_id=str(appointment_id),
            previous_status=previous,
            new_status=body.status,
        )
        await self._repo.session.flush()
        return require_row(row)

    async def get_appointment(self, appointment_id: UUID) -> dict[str, object]:
        row = (
            await self._repo.session.execute(select(Appointment).where(Appointment.id == appointment_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        return {"appointment": require_row(row), "conversation": None, "messages": []}

    async def list_children(self, limit: int = 200) -> dict[str, object]:
        cap = max(1, min(limit, 500))
        rows = (
            await self._repo.session.execute(
                select(Child, Profile)
                .join(Profile, Child.user_id == Profile.id)
                .order_by(Child.created_at.desc())
                .limit(cap)
            )
        ).all()
        
        children = []
        for child, profile in rows:
            child_dict = require_row(child).model_dump()
            child_dict["profiles"] = require_row(profile).model_dump()
            children.append(child_dict)
            
        return {"children": children}

    async def get_child(self, child_id: UUID) -> RowOut:
        row = (await self._repo.session.execute(select(Child).where(Child.id == child_id))).scalar_one_or_none()
        if row is None:
            raise not_found()
        return require_row(row)

    async def list_setting_keys(self) -> list[str]:
        keys = (await self._repo.session.execute(select(AppSetting.id))).scalars().all()
        return list(keys)

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

    async def wallet_transactions(self, limit: int) -> dict[str, object]:
        rows = (
            await self._repo.session.execute(
                select(WalletTransaction, DoctorProfile)
                .join(DoctorProfile, WalletTransaction.doctor_id == DoctorProfile.id)
                .order_by(WalletTransaction.created_at.desc())
                .limit(limit)
            )
        ).all()
        
        transactions = []
        for wt, dp in rows:
            wt_dict = require_row(wt).model_dump()
            wt_dict["doctor_profiles"] = {"first_name": dp.first_name, "last_name": dp.last_name}
            transactions.append(wt_dict)
            
        return {"transactions": transactions}

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
        admin_id = await self._auth().ensure_admin(
            email=body.email, password=body.password, full_name=body.full_name, admin_role=body.admin_role
        )
        return {"id": str(admin_id)}

    async def patch_admin(self, admin_id: UUID, body: AdminPatchIn, actor: AuthUser) -> RowOut:
        if actor.admin_role != "super_admin":
            raise forbidden("super_admin required")
        row = (
            await self._repo.session.execute(select(AdminUser).where(AdminUser.id == admin_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        if body.is_active is False and admin_id == actor.id:
            raise bad_request("Cannot deactivate your own admin account")
        if body.admin_role is not None:
            if body.admin_role not in _ADMIN_ROLES:
                raise bad_request("Invalid admin_role")
            if admin_id == actor.id and body.admin_role != actor.admin_role:
                raise bad_request("Cannot change your own admin role")
            row.admin_role = body.admin_role
        if body.is_active is not None:
            row.is_active = body.is_active
        if body.full_name is not None:
            row.full_name = body.full_name
        await self._log(actor, "admin.patch", "Admin updated", admin_id=str(admin_id))
        await self._repo.session.flush()
        return require_row(row)

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

    async def delete_hospital(self, hospital_id: UUID) -> None:
        row = (await self._repo.session.execute(select(Hospital).where(Hospital.id == hospital_id))).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()

    async def _category_out(self, row: DoctorCategory) -> RowOut:
        translations = (
            await self._repo.session.execute(
                select(DoctorCategoryTranslation).where(DoctorCategoryTranslation.category_id == row.id)
            )
        ).scalars().all()
        data = require_row(row).model_dump()
        data["doctor_category_translations"] = [
            {
                "id": str(t.id),
                "category_id": str(t.category_id),
                "language_code": t.language_code,
                "name": t.name,
            }
            for t in translations
        ]
        return RowOut.model_validate(data)

    async def _upsert_category_translations(
        self, category_id: UUID, translations: list[CategoryTranslationIn]
    ) -> None:
        for item in translations:
            code = item.language_code.strip().lower()
            name = item.name.strip()
            if not code or not name:
                continue
            existing = (
                await self._repo.session.execute(
                    select(DoctorCategoryTranslation).where(
                        DoctorCategoryTranslation.category_id == category_id,
                        DoctorCategoryTranslation.language_code == code,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                self._repo.session.add(
                    DoctorCategoryTranslation(category_id=category_id, language_code=code, name=name)
                )
            else:
                existing.name = name
        await self._repo.session.flush()

    async def categories(self) -> list[RowOut]:
        rows = list((await self._repo.session.execute(select(DoctorCategory))).scalars().all())
        return [await self._category_out(row) for row in rows]

    async def create_category(self, body: CategoryIn) -> RowOut:
        payload = body.model_dump(exclude={"translations"})
        row = DoctorCategory(**payload)
        self._repo.session.add(row)
        await self._repo.session.flush()
        if body.translations:
            await self._upsert_category_translations(row.id, body.translations)
        return await self._category_out(row)

    async def patch_category(self, category_id: UUID, body: CategoryPatchIn) -> RowOut:
        row = (
            await self._repo.session.execute(select(DoctorCategory).where(DoctorCategory.id == category_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True, exclude={"translations"}).items():
            setattr(row, key, value)
        await self._repo.session.flush()
        if body.translations is not None:
            await self._upsert_category_translations(category_id, body.translations)
        return await self._category_out(row)

    async def delete_category(self, category_id: UUID) -> dict[str, bool]:
        row = (
            await self._repo.session.execute(select(DoctorCategory).where(DoctorCategory.id == category_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()
        return {"ok": True}

    async def pregnancy_weeks(self) -> list[RowOut]:
        rows = list((await self._repo.session.execute(select(PregnancyWeek))).scalars().all())
        return [await self._pregnancy_week_out(row) for row in rows]

    async def _pregnancy_week_out(self, row: PregnancyWeek) -> RowOut:
        translations = (
            await self._repo.session.execute(
                select(PregnancyWeekTranslation).where(
                    PregnancyWeekTranslation.pregnancy_week_id == row.id
                )
            )
        ).scalars().all()
        data = require_row(row).model_dump()
        data["pregnancy_week_translations"] = [
            {
                "id": str(t.id),
                "pregnancy_week_id": str(t.pregnancy_week_id),
                "language_code": t.language_code,
                "title": t.title,
                "subtitle": t.subtitle,
                "baby": t.baby,
                "stage": t.stage,
                "mother_changes": t.mother_changes,
                "recommendations": t.recommendations,
                "warning_signs": t.warning_signs,
                "sections": t.sections,
            }
            for t in translations
        ]
        return RowOut.model_validate(data)

    async def create_week(self, body: WeekIn) -> RowOut:
        row = PregnancyWeek(**body.model_dump())
        self._repo.session.add(row)
        await self._repo.session.flush()
        return await self._pregnancy_week_out(row)

    async def patch_week(self, week_id: UUID, body: WeekPatchIn) -> RowOut:
        row = (
            await self._repo.session.execute(select(PregnancyWeek).where(PregnancyWeek.id == week_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self._repo.session.flush()
        return await self._pregnancy_week_out(row)

    async def delete_week(self, week_id: UUID) -> None:
        row = (
            await self._repo.session.execute(select(PregnancyWeek).where(PregnancyWeek.id == week_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()

    async def week_translation(self, week_id: UUID, body: WeekTranslationIn) -> RowOut:
        week = (
            await self._repo.session.execute(select(PregnancyWeek).where(PregnancyWeek.id == week_id))
        ).scalar_one_or_none()
        if week is None:
            raise not_found()
        code = body.language_code.strip().lower()
        existing = (
            await self._repo.session.execute(
                select(PregnancyWeekTranslation).where(
                    PregnancyWeekTranslation.pregnancy_week_id == week_id,
                    PregnancyWeekTranslation.language_code == code,
                )
            )
        ).scalar_one_or_none()
        payload = body.model_dump()
        payload["language_code"] = code
        if existing is None:
            row = PregnancyWeekTranslation(pregnancy_week_id=week_id, **payload)
            self._repo.session.add(row)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            row = existing
        await self._repo.session.flush()
        return require_row(row)

    async def _growth_period_out(self, row: ChildGrowthPeriod) -> RowOut:
        translations = (
            await self._repo.session.execute(
                select(ChildGrowthPeriodTranslation).where(
                    ChildGrowthPeriodTranslation.period_id == row.id
                )
            )
        ).scalars().all()
        data = require_row(row).model_dump()
        data["child_growth_period_translations"] = [
            {
                "id": str(t.id),
                "period_id": str(t.period_id),
                "language_code": t.language_code,
                "title": t.title,
                "subtitle": t.subtitle,
                "growth": t.growth,
                "vaccines": t.vaccines,
                "milestones": t.milestones,
                "red_flags": t.red_flags,
                "nutrition": t.nutrition,
                "visit_reminders": t.visit_reminders,
            }
            for t in translations
        ]
        return RowOut.model_validate(data)

    async def _upsert_growth_translations(
        self, period_id: UUID, translations: list[GrowthPeriodTranslationIn]
    ) -> None:
        for item in translations:
            code = item.language_code.strip().lower()
            title = item.title.strip()
            if not code or not title:
                continue
            payload = item.model_dump()
            payload["language_code"] = code
            payload["title"] = title
            existing = (
                await self._repo.session.execute(
                    select(ChildGrowthPeriodTranslation).where(
                        ChildGrowthPeriodTranslation.period_id == period_id,
                        ChildGrowthPeriodTranslation.language_code == code,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                self._repo.session.add(
                    ChildGrowthPeriodTranslation(period_id=period_id, **payload)
                )
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
        await self._repo.session.flush()

    async def growth_periods(self) -> list[RowOut]:
        rows = list((await self._repo.session.execute(select(ChildGrowthPeriod))).scalars().all())
        return [await self._growth_period_out(row) for row in rows]

    async def get_growth_period(self, period_id: UUID) -> RowOut:
        row = (
            await self._repo.session.execute(
                select(ChildGrowthPeriod).where(ChildGrowthPeriod.id == period_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        return await self._growth_period_out(row)

    async def create_growth_period(self, body: GrowthPeriodIn) -> RowOut:
        payload = body.model_dump(exclude={"translations"})
        row = ChildGrowthPeriod(**payload)
        self._repo.session.add(row)
        await self._repo.session.flush()
        if body.translations:
            await self._upsert_growth_translations(row.id, body.translations)
        return await self._growth_period_out(row)

    async def patch_growth_period(self, period_id: UUID, body: GrowthPeriodPatchIn) -> RowOut:
        row = (
            await self._repo.session.execute(
                select(ChildGrowthPeriod).where(ChildGrowthPeriod.id == period_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True, exclude={"translations"}).items():
            setattr(row, key, value)
        await self._repo.session.flush()
        if body.translations is not None:
            await self._upsert_growth_translations(period_id, body.translations)
        return await self._growth_period_out(row)

    async def delete_growth_period(self, period_id: UUID) -> None:
        row = (
            await self._repo.session.execute(
                select(ChildGrowthPeriod).where(ChildGrowthPeriod.id == period_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()

    async def growth_period_translation(
        self, period_id: UUID, body: GrowthPeriodTranslationIn
    ) -> RowOut:
        period = (
            await self._repo.session.execute(
                select(ChildGrowthPeriod).where(ChildGrowthPeriod.id == period_id)
            )
        ).scalar_one_or_none()
        if period is None:
            raise not_found()
        await self._upsert_growth_translations(period_id, [body])
        existing = (
            await self._repo.session.execute(
                select(ChildGrowthPeriodTranslation).where(
                    ChildGrowthPeriodTranslation.period_id == period_id,
                    ChildGrowthPeriodTranslation.language_code == body.language_code.strip().lower(),
                )
            )
        ).scalar_one()
        return require_row(existing)

    async def followup_templates(self) -> list[RowOut]:
        return to_rows(
            list((await self._repo.session.execute(select(ChildFollowupVisitTemplate))).scalars().all())
        )

    async def create_followup_template(self, body: FollowupTemplateIn) -> RowOut:
        row = ChildFollowupVisitTemplate(**body.model_dump())
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def patch_followup_template(
        self, template_id: UUID, body: FollowupTemplatePatchIn
    ) -> RowOut:
        row = (
            await self._repo.session.execute(
                select(ChildFollowupVisitTemplate).where(
                    ChildFollowupVisitTemplate.id == template_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self._repo.session.flush()
        return require_row(row)

    async def _daily_tip_out(self, row: DailyTip) -> RowOut:
        translations = (
            await self._repo.session.execute(
                select(DailyTipTranslation).where(DailyTipTranslation.tip_id == row.id)
            )
        ).scalars().all()
        data = require_row(row).model_dump()
        data["daily_tip_translations"] = [
            {
                "id": str(t.id),
                "tip_id": str(t.tip_id),
                "language_code": t.language_code,
                "title": t.title,
                "content": t.content,
            }
            for t in translations
        ]
        return RowOut.model_validate(data)

    async def _upsert_daily_tip_translations(
        self, tip_id: UUID, translations: list[DailyTipTranslationIn]
    ) -> None:
        for item in translations:
            code = item.language_code.strip().lower()
            title = item.title.strip()
            content = item.content.strip()
            if not code or not title or not content:
                continue
            existing = (
                await self._repo.session.execute(
                    select(DailyTipTranslation).where(
                        DailyTipTranslation.tip_id == tip_id,
                        DailyTipTranslation.language_code == code,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                self._repo.session.add(
                    DailyTipTranslation(
                        tip_id=tip_id, language_code=code, title=title, content=content
                    )
                )
            else:
                existing.title = title
                existing.content = content
        await self._repo.session.flush()

    async def list_daily_tips(self) -> list[RowOut]:
        rows = list(
            (
                await self._repo.session.execute(
                    select(DailyTip).order_by(DailyTip.week_number, DailyTip.day_number)
                )
            )
            .scalars()
            .all()
        )
        return [await self._daily_tip_out(row) for row in rows]

    async def get_daily_tip(self, tip_id: UUID) -> RowOut:
        row = (
            await self._repo.session.execute(select(DailyTip).where(DailyTip.id == tip_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        return await self._daily_tip_out(row)

    async def create_daily_tip(self, body: DailyTipIn) -> RowOut:
        payload = body.model_dump(exclude={"translations"})
        row = DailyTip(**payload)
        self._repo.session.add(row)
        await self._repo.session.flush()
        if body.translations:
            await self._upsert_daily_tip_translations(row.id, body.translations)
        return await self._daily_tip_out(row)

    async def patch_daily_tip(self, tip_id: UUID, body: DailyTipPatchIn) -> RowOut:
        row = (
            await self._repo.session.execute(select(DailyTip).where(DailyTip.id == tip_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True, exclude={"translations"}).items():
            setattr(row, key, value)
        await self._repo.session.flush()
        if body.translations is not None:
            await self._upsert_daily_tip_translations(tip_id, body.translations)
        return await self._daily_tip_out(row)

    async def delete_daily_tip(self, tip_id: UUID) -> None:
        row = (
            await self._repo.session.execute(select(DailyTip).where(DailyTip.id == tip_id))
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()

    async def daily_tip_translation(self, tip_id: UUID, body: DailyTipTranslationIn) -> RowOut:
        tip = (
            await self._repo.session.execute(select(DailyTip).where(DailyTip.id == tip_id))
        ).scalar_one_or_none()
        if tip is None:
            raise not_found()
        await self._upsert_daily_tip_translations(tip_id, [body])
        existing = (
            await self._repo.session.execute(
                select(DailyTipTranslation).where(
                    DailyTipTranslation.tip_id == tip_id,
                    DailyTipTranslation.language_code == body.language_code.strip().lower(),
                )
            )
        ).scalar_one()
        return require_row(existing)


    async def _clinical_advice_out(self, row: GrowthClinicalAdvice) -> RowOut:
        translations = (
            await self._repo.session.execute(
                select(GrowthClinicalAdviceTranslation).where(
                    GrowthClinicalAdviceTranslation.advice_id == row.id
                )
            )
        ).scalars().all()
        data = require_row(row).model_dump()
        data["growth_clinical_advice_translations"] = [
            {
                "id": str(t.id),
                "advice_id": str(t.advice_id),
                "language_code": t.language_code,
                "explain_text": t.explain_text,
                "causes": t.causes,
                "recommendations": t.recommendations,
            }
            for t in translations
        ]
        return RowOut.model_validate(data)

    async def _upsert_clinical_advice_translations(
        self, advice_id: UUID, translations: list[ClinicalAdviceTranslationIn]
    ) -> None:
        for item in translations:
            code = item.language_code.strip().lower()
            if not code:
                continue
            payload = {
                "language_code": code,
                "explain_text": item.explain_text.strip(),
                "causes": item.causes.strip(),
                "recommendations": item.recommendations.strip(),
            }
            existing = (
                await self._repo.session.execute(
                    select(GrowthClinicalAdviceTranslation).where(
                        GrowthClinicalAdviceTranslation.advice_id == advice_id,
                        GrowthClinicalAdviceTranslation.language_code == code,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                self._repo.session.add(
                    GrowthClinicalAdviceTranslation(advice_id=advice_id, **payload)
                )
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
        await self._repo.session.flush()

    async def list_clinical_advice(self) -> list[RowOut]:
        rows = list(
            (
                await self._repo.session.execute(
                    select(GrowthClinicalAdvice).order_by(
                        GrowthClinicalAdvice.sort_order, GrowthClinicalAdvice.code
                    )
                )
            )
            .scalars()
            .all()
        )
        return [await self._clinical_advice_out(row) for row in rows]

    async def get_clinical_advice(self, advice_id: UUID) -> RowOut:
        row = (
            await self._repo.session.execute(
                select(GrowthClinicalAdvice).where(GrowthClinicalAdvice.id == advice_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        return await self._clinical_advice_out(row)

    async def create_clinical_advice(self, body: ClinicalAdviceIn) -> RowOut:
        payload = body.model_dump(exclude={"translations"})
        payload["code"] = payload["code"].strip().lower()
        payload["metric"] = payload["metric"].strip()
        payload["condition"] = payload["condition"].strip()
        row = GrowthClinicalAdvice(**payload)
        self._repo.session.add(row)
        await self._repo.session.flush()
        if body.translations:
            await self._upsert_clinical_advice_translations(row.id, body.translations)
        return await self._clinical_advice_out(row)

    async def patch_clinical_advice(self, advice_id: UUID, body: ClinicalAdvicePatchIn) -> RowOut:
        row = (
            await self._repo.session.execute(
                select(GrowthClinicalAdvice).where(GrowthClinicalAdvice.id == advice_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        updates = body.model_dump(exclude_unset=True, exclude={"translations"})
        if "code" in updates and updates["code"] is not None:
            updates["code"] = updates["code"].strip().lower()
        if "metric" in updates and updates["metric"] is not None:
            updates["metric"] = updates["metric"].strip()
        if "condition" in updates and updates["condition"] is not None:
            updates["condition"] = updates["condition"].strip()
        for key, value in updates.items():
            setattr(row, key, value)
        await self._repo.session.flush()
        if body.translations is not None:
            await self._upsert_clinical_advice_translations(advice_id, body.translations)
        return await self._clinical_advice_out(row)

    async def delete_clinical_advice(self, advice_id: UUID) -> None:
        row = (
            await self._repo.session.execute(
                select(GrowthClinicalAdvice).where(GrowthClinicalAdvice.id == advice_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()

    async def clinical_advice_translation(
        self, advice_id: UUID, body: ClinicalAdviceTranslationIn
    ) -> RowOut:
        advice = (
            await self._repo.session.execute(
                select(GrowthClinicalAdvice).where(GrowthClinicalAdvice.id == advice_id)
            )
        ).scalar_one_or_none()
        if advice is None:
            raise not_found()
        await self._upsert_clinical_advice_translations(advice_id, [body])
        existing = (
            await self._repo.session.execute(
                select(GrowthClinicalAdviceTranslation).where(
                    GrowthClinicalAdviceTranslation.advice_id == advice_id,
                    GrowthClinicalAdviceTranslation.language_code
                    == body.language_code.strip().lower(),
                )
            )
        ).scalar_one()
        return require_row(existing)

    async def delete_followup_template(self, template_id: UUID) -> None:
        row = (
            await self._repo.session.execute(
                select(ChildFollowupVisitTemplate).where(
                    ChildFollowupVisitTemplate.id == template_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise not_found()
        await self._repo.session.delete(row)
        await self._repo.session.flush()

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
        rows = list((await self._repo.session.execute(select(AdminDocument))).scalars().all())
        result = []
        for row in rows:
            data = require_row(row).model_dump()
            data["preview_url"] = row.storage_path
            result.append(RowOut.model_validate(data))
        return result

    async def create_document(self, body: DocumentIn, admin: AuthUser) -> RowOut:
        row = AdminDocument(
            title=body.title,
            category=body.category,
            storage_path=body.storage_path,
            file_name=body.file_name,
            mime_type=body.mime_type,
            uploaded_by=admin.id,
        )
        self._repo.session.add(row)
        await self._log(admin, "document.create", "Admin document created", title=body.title)
        await self._repo.session.flush()
        return require_row(row)

    async def deliver_document(self, document_id: UUID, recipient_id: UUID, sender_id: UUID) -> RowOut:
        row = DocumentDelivery(document_id=document_id, recipient_id=recipient_id, sent_by=sender_id)
        self._repo.session.add(row)
        await self._repo.session.flush()
        return require_row(row)

    async def doctor_document_deliveries(self, doctor_id: UUID) -> list[RowOut]:
        rows = (
            await self._repo.session.execute(
                select(DocumentDelivery)
                .where(DocumentDelivery.recipient_id == doctor_id)
                .order_by(DocumentDelivery.sent_at.desc())
            )
        ).scalars().all()
        return to_rows(list(rows))

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

    async def activity_logs(self, source: str, limit: int, offset: int = 0) -> dict[str, object]:
        if source == "platform":
            total = (await self._repo.session.execute(select(func.count()).select_from(PlatformActivityLog))).scalar_one()
            rows = (
                await self._repo.session.execute(select(PlatformActivityLog).order_by(PlatformActivityLog.created_at.desc()).limit(limit).offset(offset))
            ).scalars().all()
        else:
            total = (await self._repo.session.execute(select(func.count()).select_from(AdminActivityLog))).scalar_one()
            rows = (
                await self._repo.session.execute(select(AdminActivityLog).order_by(AdminActivityLog.created_at.desc()).limit(limit).offset(offset))
            ).scalars().all()
            
        return {
            "logs": [require_row(r).model_dump() for r in rows],
            "pagination": {
                "total": int(total),
                "offset": offset,
                "limit": limit
            }
        }

    async def doctor_wallet(self, doctor_id: UUID, limit: int = 100) -> dict[str, object]:
        doctor = (
            await self._repo.session.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))
        ).scalar_one_or_none()
        if doctor is None:
            raise not_found()

        wallet = (
            await self._repo.session.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == doctor_id))
        ).scalar_one_or_none()

        finance = (
            await self._repo.session.execute(select(AppSetting).where(AppSetting.id == "finance"))
        ).scalar_one_or_none()
        finance_data = finance.data if finance and isinstance(finance.data, dict) else {}
        commission_raw = finance_data.get("platformCommissionPercent", finance_data.get("platform_commission_percent", 10))
        try:
            commission_percent = int(float(commission_raw))
        except (TypeError, ValueError):
            commission_percent = 10

        cap = max(1, min(limit, 500))
        txs = list(
            (
                await self._repo.session.execute(
                    select(WalletTransaction)
                    .where(WalletTransaction.doctor_id == doctor_id)
                    .order_by(WalletTransaction.created_at.desc())
                    .limit(cap)
                )
            ).scalars().all()
        )

        earning_appts = {
            a.id: a
            for a in (
                await self._repo.session.execute(
                    select(Appointment).where(
                        Appointment.id.in_([t.appointment_id for t in txs if t.appointment_id is not None])
                    )
                )
            ).scalars().all()
        } if any(t.appointment_id for t in txs) else {}

        earnings: list[dict[str, object]] = []
        for tx in txs:
            if tx.type != "appointment_earning":
                continue
            appt = earning_appts.get(tx.appointment_id) if tx.appointment_id else None
            earnings.append(
                {
                    "id": str(tx.id),
                    "amount": float(tx.amount),
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                    "note": tx.note,
                    "appointment_id": str(tx.appointment_id) if tx.appointment_id else None,
                    "appointment_date": appt.appointment_date.isoformat() if appt and appt.appointment_date else None,
                    "time_slot": appt.time_slot if appt else None,
                    "service_name": appt.service_name if appt else None,
                    "patient_id": str(appt.patient_id) if appt else None,
                    "patient_name": appt.patient_name if appt else None,
                }
            )

        wallet_out = None
        if wallet is not None:
            wallet_out = {
                "available_balance": float(wallet.available_balance),
                "pending_balance": float(wallet.pending_balance),
                "currency": wallet.currency,
            }

        return {
            "history": {
                "wallet": wallet_out,
                "commissionPercent": commission_percent,
                "earnings": earnings,
                "transactions": to_rows(txs),
            }
        }

    async def doctor_referral_stats(self, doctor_id: UUID) -> dict[str, object]:
        doctor = (
            await self._repo.session.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))
        ).scalar_one_or_none()
        if doctor is None:
            raise not_found()
        refs = list(
            (
                await self._repo.session.execute(
                    select(DoctorReferral).where(DoctorReferral.doctor_id == doctor_id)
                )
            ).scalars().all()
        )
        commissions = list(
            (
                await self._repo.session.execute(
                    select(DoctorReferralCommission).where(DoctorReferralCommission.doctor_id == doctor_id)
                )
            ).scalars().all()
        )
        total = sum((float(c.commission_amount) for c in commissions), 0.0)
        currency = commissions[0].currency if commissions else "ETB"
        return {
            "referral_code": doctor.referral_code,
            "referred_count": len(refs),
            "total_commission": total,
            "currency": currency,
        }

    async def list_referrals(self, limit: int = 200) -> list[dict[str, object]]:
        refs = list(
            (
                await self._repo.session.execute(
                    select(DoctorReferral).order_by(DoctorReferral.created_at.desc()).limit(limit)
                )
            ).scalars().all()
        )
        if not refs:
            return []

        patient_ids = {r.patient_id for r in refs}
        doctor_ids = {r.doctor_id for r in refs}
        profiles = {
            p.id: p
            for p in (
                await self._repo.session.execute(select(Profile).where(Profile.id.in_(patient_ids)))
            ).scalars().all()
        }
        doctors = {
            d.id: d
            for d in (
                await self._repo.session.execute(select(DoctorProfile).where(DoctorProfile.id.in_(doctor_ids)))
            ).scalars().all()
        }
        paid = {
            row.patient_id
            for row in (
                await self._repo.session.execute(
                    select(AppSubscription).where(
                        AppSubscription.patient_id.in_(patient_ids),
                        AppSubscription.amount_paid > 0,
                    )
                )
            ).scalars().all()
        }

        out: list[dict[str, object]] = []
        for ref in refs:
            profile = profiles.get(ref.patient_id)
            doctor = doctors.get(ref.doctor_id)
            doctor_name = None
            if doctor is not None:
                parts = [p for p in [doctor.first_name, doctor.last_name] if p and str(p).strip()]
                doctor_name = " ".join(parts) if parts else None
            out.append(
                {
                    "id": str(ref.id),
                    "patient_id": str(ref.patient_id),
                    "doctor_id": str(ref.doctor_id),
                    "referral_code": ref.referral_code,
                    "created_at": ref.created_at.isoformat() if ref.created_at else None,
                    "patient_name": getattr(profile, "full_name", None) if profile else None,
                    "patient_phone": getattr(profile, "phone", None) if profile else None,
                    "doctor_name": doctor_name,
                    "is_subscribed": ref.patient_id in paid,
                }
            )
        return out

    async def list_referral_commissions(self, limit: int = 200) -> list[dict[str, object]]:
        rows = list(
            (
                await self._repo.session.execute(
                    select(DoctorReferralCommission)
                    .order_by(DoctorReferralCommission.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
        )
        if not rows:
            return []

        patient_ids = {r.patient_id for r in rows}
        doctor_ids = {r.doctor_id for r in rows}
        profiles = {
            p.id: p
            for p in (
                await self._repo.session.execute(select(Profile).where(Profile.id.in_(patient_ids)))
            ).scalars().all()
        }
        doctors = {
            d.id: d
            for d in (
                await self._repo.session.execute(select(DoctorProfile).where(DoctorProfile.id.in_(doctor_ids)))
            ).scalars().all()
        }

        out: list[dict[str, object]] = []
        for row in rows:
            profile = profiles.get(row.patient_id)
            doctor = doctors.get(row.doctor_id)
            doctor_name = None
            if doctor is not None:
                parts = [p for p in [doctor.first_name, doctor.last_name] if p and str(p).strip()]
                doctor_name = " ".join(parts) if parts else None
            out.append(
                {
                    "id": str(row.id),
                    "referral_id": str(row.referral_id),
                    "doctor_id": str(row.doctor_id),
                    "patient_id": str(row.patient_id),
                    "payment_id": str(row.payment_id) if row.payment_id else None,
                    "subscription_amount": float(row.subscription_amount),
                    "commission_percent": float(row.commission_percent),
                    "commission_amount": float(row.commission_amount),
                    "currency": row.currency,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "patient_name": getattr(profile, "full_name", None) if profile else None,
                    "doctor_name": doctor_name,
                }
            )
        return out


    async def bootstrap_super_admin(self, body: AdminCreateIn) -> dict[str, str]:
        count = (await self._repo.session.execute(select(func.count()).select_from(AdminUser))).scalar_one()
        if count > 0:
            raise forbidden("Admins already exist")
        admin_id = await self._auth().ensure_admin(
            email=body.email, password=body.password, full_name=body.full_name, admin_role="super_admin"
        )
        return {"id": str(admin_id)}
