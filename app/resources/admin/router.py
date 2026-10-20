from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequireAdmin
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.admin.repository import SqlAlchemyAdminRepository
from app.resources.admin.schemas import (
    ActivateChildIn,
    ActivityLogsOut,
    AdminCreateIn,
    AdminPatchIn,
    AppointmentStatusIn,
    CategoryIn,
    CategoryPatchIn,
    DoctorBookingIn,
    ClinicalAdviceIn,
    ClinicalAdvicePatchIn,
    ClinicalAdviceTranslationIn,
    DailyTipIn,
    DailyTipPatchIn,
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
    PayoutReviewOut,
    SettingIn,
    SubscriptionGrantIn,
    WalletBalancePatchIn,
    WeekIn,
    WeekPatchIn,
    WeekTranslationIn,
    ReferralApplyIn,
    BroadcastNotificationIn,
    UserNotificationIn,
)
from app.resources.admin.service import AdminService

router = APIRouter(prefix="/admin")
activity_router = APIRouter(tags=["Admin - Activity"])
admins_router = APIRouter(tags=["Admin - Admins"])
appointments_router = APIRouter(tags=["Admin - Appointments"])
children_router = APIRouter(tags=["Admin - Children"])
content_router = APIRouter(tags=["Admin - Content"])
dashboard_router = APIRouter(tags=["Admin - Dashboard"])
doctors_router = APIRouter(tags=["Admin - Doctors"])
finance_router = APIRouter(tags=["Admin - Finance"])
hospitals_router = APIRouter(tags=["Admin - Hospitals"])
legal_docs_router = APIRouter(tags=["Admin - Legal & Docs"])
membership_router = APIRouter(tags=["Admin - Membership"])
referrals_router = APIRouter(tags=["Admin - Referrals"])
settings_router = APIRouter(tags=["Admin - Settings"])
users_router = APIRouter(tags=["Admin - Users"])


def get_admin_service(db: DbDep) -> AdminService:
    return AdminService(SqlAlchemyAdminRepository(db))


AdminDep = Annotated[AdminService, Depends(get_admin_service)]


@dashboard_router.get("/dashboard")
async def dashboard(user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.dashboard()


@users_router.get("/users")
async def list_users(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search full name, phone, or email")] = None,
    role: Annotated[str | None, Query(description="Filter by role")] = None,
    is_pregnant: Annotated[bool | None, Query(description="Filter by pregnancy status")] = None,
    created_from: Annotated[datetime | None, Query(description="Filter by created_at >= created_from")] = None,
    created_to: Annotated[datetime | None, Query(description="Filter by created_at <= created_to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RowOut]:
    return await svc.list_users(
        limit=limit,
        offset=offset,
        search=search,
        role=role,
        is_pregnant=is_pregnant,
        created_from=created_from,
        created_to=created_to,
    )


@users_router.get("/users/{user_id}")
async def user_detail(user_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.user_detail(user_id)


@users_router.get("/users/{user_id}/referral")
async def get_user_referral(user_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.get_user_referral(user_id)


@users_router.post("/users/{user_id}/referral")
async def apply_user_referral(user_id: UUID, body: ReferralApplyIn, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.apply_user_referral(user_id, body.code)


@users_router.patch("/users/{user_id}/wallet")
async def patch_user_wallet(user_id: UUID, body: WalletBalancePatchIn, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.patch_user_wallet(user_id, body, user)


@doctors_router.get("/doctors")
async def list_doctors(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_doctors()


@doctors_router.post("/doctors/{doctor_id}/verify")
async def verify_doctor(doctor_id: UUID, body: DoctorVerifyIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.verify_doctor(doctor_id, body, user)


@doctors_router.get("/doctors/{doctor_id}/services")
async def list_doctor_services(doctor_id: UUID, user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_doctor_services(doctor_id)


@doctors_router.get("/doctors/{doctor_id}/wallet")
async def doctor_wallet(
    doctor_id: UUID,
    user: RequireAdmin,
    svc: AdminDep,
    type: Annotated[str | None, Query(description="Filter by transaction type")] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by created_at >= date_from")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by created_at <= date_to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return await svc.doctor_wallet(
        doctor_id=doctor_id,
        limit=limit,
        offset=offset,
        type=type,
        date_from=date_from,
        date_to=date_to,
    )


@doctors_router.patch("/doctors/{doctor_id}/booking")
async def replace_doctor_booking(
    doctor_id: UUID, body: DoctorBookingIn, user: RequireAdmin, svc: AdminDep
) -> dict[str, object]:
    return await svc.replace_doctor_booking(doctor_id, body, user)


@doctors_router.get("/doctors/{doctor_id}/document-deliveries")
async def doctor_document_deliveries(doctor_id: UUID, user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.doctor_document_deliveries(doctor_id)


@doctors_router.get("/doctors/{doctor_id}/referral-stats")
async def doctor_referral_stats(doctor_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.doctor_referral_stats(doctor_id)


@appointments_router.get("/appointments")
async def list_appointments(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search doctor name, patient name, or phone")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    doctor_id: Annotated[UUID | None, Query(description="Filter by doctor ID")] = None,
    patient_id: Annotated[UUID | None, Query(description="Filter by patient ID")] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by scheduled_for >= date_from")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by scheduled_for <= date_to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return await svc.list_appointments(
        limit=limit,
        offset=offset,
        search=search,
        status=status,
        doctor_id=doctor_id,
        patient_id=patient_id,
        date_from=date_from,
        date_to=date_to,
    )


@appointments_router.patch("/appointments/{appointment_id}")
async def patch_appointment(
    appointment_id: UUID, body: AppointmentStatusIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.patch_appointment(appointment_id, body, user)


@appointments_router.get("/appointments/{appointment_id}")
async def get_appointment(appointment_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.get_appointment(appointment_id)


@children_router.get("/children")
async def list_children(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search child name, parent name, or phone")] = None,
    gender: Annotated[str | None, Query(description="Filter by gender")] = None,
    payment_status: Annotated[str | None, Query(description="Filter by payment status")] = None,
    user_id: Annotated[UUID | None, Query(description="Filter by parent user ID")] = None,
    dob_from: Annotated[date | None, Query(description="Filter by birth date >= dob_from")] = None,
    dob_to: Annotated[date | None, Query(description="Filter by birth date <= dob_to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return await svc.list_children(
        limit=limit,
        offset=offset,
        search=search,
        gender=gender,
        payment_status=payment_status,
        user_id=user_id,
        dob_from=dob_from,
        dob_to=dob_to,
    )


@children_router.get("/child-payments")
async def list_child_payments(
    user: RequireAdmin,
    svc: AdminDep,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    child_id: Annotated[UUID | None, Query(description="Filter by child ID")] = None,
    user_id: Annotated[UUID | None, Query(description="Filter by parent ID")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return await svc.list_child_payments(
        limit=limit,
        offset=offset,
        status=status,
        child_id=child_id,
        user_id=user_id,
    )


@children_router.post("/children/{child_id}/activate")
async def manual_activate_child(
    child_id: UUID,
    body: ActivateChildIn,
    user: RequireAdmin,
    svc: AdminDep,
) -> RowOut:
    return await svc.manual_activate_child(
        child_id=child_id,
        amount=body.amount,
        payment_method=body.payment_method,
        actor=user,
    )


@children_router.get("/children/{child_id}")
async def get_child(child_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.get_child(child_id)


@children_router.get("/children/{child_id}/measurements")
async def list_child_measurements(child_id: UUID, user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_child_measurements(child_id)


@children_router.get("/children/{child_id}/milestones")
async def list_child_milestones(child_id: UUID, user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_child_milestones(child_id)


@children_router.get("/children/{child_id}/vaccines")
async def list_child_vaccines(child_id: UUID, user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_child_vaccines(child_id)


@settings_router.get("/settings")
async def list_settings(user: RequireAdmin, svc: AdminDep) -> list[str]:
    return await svc.list_setting_keys()


@settings_router.get("/settings/{setting_id}")
async def get_setting(setting_id: str, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.get_setting(setting_id)


@settings_router.put("/settings/{setting_id}")
async def put_setting(setting_id: str, body: SettingIn, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.put_setting(setting_id, body, user)


@finance_router.get("/payout-requests")
async def payout_requests(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.payout_requests()


@finance_router.get("/payout-requests/{request_id}", response_model=PayoutReviewOut)
async def get_payout_review(request_id: UUID, user: RequireAdmin, svc: AdminDep) -> PayoutReviewOut:
    return await svc.get_payout_review(request_id)


@finance_router.post("/payout-requests/{request_id}")
async def payout_action(request_id: UUID, body: PayoutActionIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.payout_action(request_id, body, admin=user)


@finance_router.get("/patient-withdrawals")
async def list_patient_withdrawals(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_patient_withdrawals()


@finance_router.get("/patient-withdrawals/{request_id}")
async def get_patient_withdrawal_review(request_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.get_patient_withdrawal_review(request_id)


@finance_router.post("/patient-withdrawals/{request_id}")
async def action_patient_withdrawal(
    request_id: UUID, body: PayoutActionIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.action_patient_withdrawal(request_id, body, admin=user)


@finance_router.get("/wallet-transactions")
async def wallet_transactions(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search doctor name or note")] = None,
    doctor_id: Annotated[UUID | None, Query(description="Filter by doctor ID")] = None,
    type: Annotated[str | None, Query(description="Filter by transaction type")] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by created_at >= date_from")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by created_at <= date_to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return await svc.wallet_transactions(
        limit=limit,
        offset=offset,
        search=search,
        doctor_id=doctor_id,
        type=type,
        date_from=date_from,
        date_to=date_to,
    )


@membership_router.post("/membership/grant")
async def grant_membership(body: SubscriptionGrantIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.grant_membership(body)


@membership_router.post("/membership/{subscription_id}/revoke")
async def revoke_membership(subscription_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.revoke_membership(subscription_id)


@membership_router.get("/membership")
async def list_membership(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_membership()


@admins_router.get("/admins")
async def list_admins(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_admins()


@admins_router.post("/admins")
async def create_admin(body: AdminCreateIn, user: RequireAdmin, svc: AdminDep) -> dict[str, str]:
    return await svc.create_admin(body, user)


@admins_router.patch("/admins/{admin_id}")
async def patch_admin(admin_id: UUID, body: AdminPatchIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.patch_admin(admin_id, body, user)


@hospitals_router.get("/hospitals")
async def list_hospitals(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_hospitals()


@hospitals_router.post("/hospitals")
async def create_hospital(body: HospitalIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_hospital(body)


@hospitals_router.patch("/hospitals/{hospital_id}")
async def patch_hospital(hospital_id: UUID, body: HospitalIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.patch_hospital(hospital_id, body)


@hospitals_router.delete("/hospitals/{hospital_id}", status_code=204)
async def delete_hospital(hospital_id: UUID, user: RequireAdmin, svc: AdminDep) -> None:
    await svc.delete_hospital(hospital_id)


@doctors_router.get("/doctor-categories")
async def categories(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.categories()


@doctors_router.post("/doctor-categories")
async def create_category(body: CategoryIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_category(body)


@doctors_router.patch("/doctor-categories/{category_id}")
async def patch_category(
    category_id: UUID, body: CategoryPatchIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.patch_category(category_id, body)


@doctors_router.delete("/doctor-categories/{category_id}")
async def delete_category(category_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, bool]:
    return await svc.delete_category(category_id)


@content_router.get("/pregnancy-weeks")
async def pregnancy_weeks(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.pregnancy_weeks()


@content_router.post("/pregnancy-weeks")
async def create_week(body: WeekIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_week(body)


@content_router.patch("/pregnancy-weeks/{week_id}")
async def patch_week(week_id: UUID, body: WeekPatchIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.patch_week(week_id, body)


@content_router.delete("/pregnancy-weeks/{week_id}", status_code=204)
async def delete_week(week_id: UUID, user: RequireAdmin, svc: AdminDep) -> None:
    await svc.delete_week(week_id)


@content_router.post("/pregnancy-weeks/{week_id}/translations")
async def week_translation(week_id: UUID, body: WeekTranslationIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.week_translation(week_id, body)


@content_router.get("/daily-tips")
async def list_daily_tips(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_daily_tips()


@content_router.get("/daily-tips/{tip_id}")
async def get_daily_tip(tip_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.get_daily_tip(tip_id)


@content_router.post("/daily-tips")
async def create_daily_tip(body: DailyTipIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_daily_tip(body)


@content_router.patch("/daily-tips/{tip_id}")
async def patch_daily_tip(tip_id: UUID, body: DailyTipPatchIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.patch_daily_tip(tip_id, body)


@content_router.delete("/daily-tips/{tip_id}", status_code=204)
async def delete_daily_tip(tip_id: UUID, user: RequireAdmin, svc: AdminDep) -> None:
    await svc.delete_daily_tip(tip_id)


@content_router.post("/daily-tips/{tip_id}/translations")
async def daily_tip_translation(
    tip_id: UUID, body: DailyTipTranslationIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.daily_tip_translation(tip_id, body)




@content_router.get("/clinical-advice")
async def list_clinical_advice(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_clinical_advice()


@content_router.get("/clinical-advice/{advice_id}")
async def get_clinical_advice(advice_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.get_clinical_advice(advice_id)


@content_router.post("/clinical-advice")
async def create_clinical_advice(body: ClinicalAdviceIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_clinical_advice(body)


@content_router.patch("/clinical-advice/{advice_id}")
async def patch_clinical_advice(
    advice_id: UUID, body: ClinicalAdvicePatchIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.patch_clinical_advice(advice_id, body)


@content_router.delete("/clinical-advice/{advice_id}", status_code=204)
async def delete_clinical_advice(advice_id: UUID, user: RequireAdmin, svc: AdminDep) -> None:
    await svc.delete_clinical_advice(advice_id)


@content_router.post("/clinical-advice/{advice_id}/translations")
async def clinical_advice_translation(
    advice_id: UUID, body: ClinicalAdviceTranslationIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.clinical_advice_translation(advice_id, body)

@children_router.get("/child-growth-periods")
async def growth_periods(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.growth_periods()


@children_router.get("/child-growth-periods/{period_id}")
async def get_growth_period(period_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.get_growth_period(period_id)


@children_router.post("/child-growth-periods")
async def create_growth_period(body: GrowthPeriodIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_growth_period(body)


@children_router.patch("/child-growth-periods/{period_id}")
async def patch_growth_period(
    period_id: UUID, body: GrowthPeriodPatchIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.patch_growth_period(period_id, body)


@children_router.delete("/child-growth-periods/{period_id}", status_code=204)
async def delete_growth_period(period_id: UUID, user: RequireAdmin, svc: AdminDep) -> None:
    await svc.delete_growth_period(period_id)


@children_router.post("/child-growth-periods/{period_id}/translations")
async def growth_period_translation(
    period_id: UUID, body: GrowthPeriodTranslationIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.growth_period_translation(period_id, body)


@content_router.get("/followup-templates")
async def followup_templates(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.followup_templates()


@content_router.post("/followup-templates")
async def create_followup_template(
    body: FollowupTemplateIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.create_followup_template(body)


@content_router.patch("/followup-templates/{template_id}")
async def patch_followup_template(
    template_id: UUID, body: FollowupTemplatePatchIn, user: RequireAdmin, svc: AdminDep
) -> RowOut:
    return await svc.patch_followup_template(template_id, body)


@content_router.delete("/followup-templates/{template_id}", status_code=204)
async def delete_followup_template(
    template_id: UUID, user: RequireAdmin, svc: AdminDep
) -> None:
    await svc.delete_followup_template(template_id)


@content_router.get("/vaccine-schedule")
async def vaccine_schedule(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.vaccine_schedule()


@content_router.get("/symptoms")
async def symptoms(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.symptoms()


@legal_docs_router.get("/legal-documents")
async def legal_docs(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.legal_docs()


@legal_docs_router.put("/legal-documents")
async def upsert_legal(body: LegalIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.upsert_legal(body)


@legal_docs_router.patch("/legal-documents")
async def patch_legal_docs(body: LegalIn, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    row = await svc.upsert_legal(body)
    return {"document": row.model_dump()}


@legal_docs_router.get("/documents")
async def documents(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.documents()


@legal_docs_router.post("/documents")
async def create_document(body: DocumentIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_document(body, user)


@legal_docs_router.post("/documents/{document_id}/deliver")
async def deliver_document(document_id: UUID, recipient_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.deliver_document(document_id, recipient_id, user.id)


@activity_router.get("/activity/admin")
async def admin_activity(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search event or actor")] = None,
    actor_id: Annotated[UUID | None, Query(description="Filter by actor ID")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RowOut]:
    return await svc.admin_activity(limit=limit, offset=offset, search=search, actor_id=actor_id)


@activity_router.get("/activity/platform")
async def platform_activity(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search event or actor")] = None,
    actor_id: Annotated[UUID | None, Query(description="Filter by actor ID")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RowOut]:
    return await svc.platform_activity(limit=limit, offset=offset, search=search, actor_id=actor_id)


@activity_router.get("/activity-logs")
async def activity_logs(
    user: RequireAdmin,
    svc: AdminDep,
    source: Annotated[str, Query(description="Activity source (all, admin, platform)")] = "all",
    search: Annotated[str | None, Query(description="Search event or actor")] = None,
    event_type: Annotated[str | None, Query(description="Filter by event type")] = None,
    resource_type: Annotated[str | None, Query(description="Filter by resource type")] = None,
    resource_id: Annotated[str | None, Query(description="Filter by resource ID")] = None,
    actor_id: Annotated[UUID | None, Query(description="Filter by actor ID")] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by created_at >= date_from")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by created_at <= date_to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActivityLogsOut:
    return ActivityLogsOut(
        **await svc.activity_logs(
            source=source,
            limit=limit,
            offset=offset,
            search=search,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            date_from=date_from,
            date_to=date_to,
        )
    )




@referrals_router.get("/referrals")
async def list_referrals(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search referral code, patient, or doctor")] = None,
    doctor_id: Annotated[UUID | None, Query(description="Filter by doctor ID")] = None,
    is_subscribed: Annotated[bool | None, Query(description="Filter by subscription status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    return await svc.list_referrals(
        limit=limit,
        offset=offset,
        search=search,
        doctor_id=doctor_id,
        is_subscribed=is_subscribed,
    )


@referrals_router.get("/referral-commissions")
async def list_referral_commissions(
    user: RequireAdmin,
    svc: AdminDep,
    search: Annotated[str | None, Query(description="Search patient or doctor")] = None,
    doctor_id: Annotated[UUID | None, Query(description="Filter by doctor ID")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, object]]:
    return await svc.list_referral_commissions(
        limit=limit,
        offset=offset,
        search=search,
        doctor_id=doctor_id,
    )


@admins_router.post("/bootstrap-super-admin")
async def bootstrap_super_admin(body: AdminCreateIn, svc: AdminDep) -> dict[str, str]:
    return await svc.bootstrap_super_admin(body)


@users_router.post("/users/{user_id}/notify")
async def send_user_notification(
    user_id: UUID, body: UserNotificationIn, user: RequireAdmin, svc: AdminDep
) -> dict[str, object]:
    return await svc.send_user_notification(user_id, body, user)


@router.post("/broadcast")
async def broadcast_notification(
    body: BroadcastNotificationIn, user: RequireAdmin, svc: AdminDep
) -> dict[str, object]:
    return await svc.broadcast_notification(body, user)


router.include_router(activity_router)
router.include_router(admins_router)
router.include_router(appointments_router)
router.include_router(children_router)
router.include_router(content_router)
router.include_router(dashboard_router)
router.include_router(doctors_router)
router.include_router(finance_router)
router.include_router(hospitals_router)
router.include_router(legal_docs_router)
router.include_router(membership_router)
router.include_router(referrals_router)
router.include_router(settings_router)
router.include_router(users_router)
