from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequireAdmin
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.admin.repository import SqlAlchemyAdminRepository
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
from app.resources.admin.service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(db: DbDep) -> AdminService:
    return AdminService(SqlAlchemyAdminRepository(db))


AdminDep = Annotated[AdminService, Depends(get_admin_service)]


@router.get("/dashboard")
async def dashboard(user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.dashboard()


@router.get("/users")
async def list_users(user: RequireAdmin, svc: AdminDep, limit: int = 100, offset: int = 0) -> list[RowOut]:
    return await svc.list_users(limit, offset)


@router.get("/users/{user_id}")
async def user_detail(user_id: UUID, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.user_detail(user_id)


@router.get("/doctors")
async def list_doctors(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_doctors()


@router.post("/doctors/{doctor_id}/verify")
async def verify_doctor(doctor_id: UUID, body: DoctorVerifyIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.verify_doctor(doctor_id, body, user)


@router.get("/appointments")
async def list_appointments(user: RequireAdmin, svc: AdminDep, limit: int = 100) -> list[RowOut]:
    return await svc.list_appointments(limit)


@router.get("/settings/{setting_id}")
async def get_setting(setting_id: str, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.get_setting(setting_id)


@router.put("/settings/{setting_id}")
async def put_setting(setting_id: str, body: SettingIn, user: RequireAdmin, svc: AdminDep) -> dict[str, object]:
    return await svc.put_setting(setting_id, body, user)


@router.get("/payout-requests")
async def payout_requests(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.payout_requests()


@router.post("/payout-requests/{request_id}")
async def payout_action(request_id: UUID, body: PayoutActionIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.payout_action(request_id, body)


@router.get("/wallet-transactions")
async def wallet_transactions(user: RequireAdmin, svc: AdminDep, limit: int = 100) -> list[RowOut]:
    return await svc.wallet_transactions(limit)


@router.post("/membership/grant")
async def grant_membership(body: SubscriptionGrantIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.grant_membership(body)


@router.post("/membership/{subscription_id}/revoke")
async def revoke_membership(subscription_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.revoke_membership(subscription_id)


@router.get("/membership")
async def list_membership(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_membership()


@router.get("/admins")
async def list_admins(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_admins()


@router.post("/admins")
async def create_admin(body: AdminCreateIn, user: RequireAdmin, svc: AdminDep) -> dict[str, str]:
    return await svc.create_admin(body, user)


@router.get("/hospitals")
async def list_hospitals(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.list_hospitals()


@router.post("/hospitals")
async def create_hospital(body: HospitalIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_hospital(body)


@router.patch("/hospitals/{hospital_id}")
async def patch_hospital(hospital_id: UUID, body: HospitalIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.patch_hospital(hospital_id, body)


@router.get("/doctor-categories")
async def categories(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.categories()


@router.post("/doctor-categories")
async def create_category(body: CategoryIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_category(body)


@router.get("/pregnancy-weeks")
async def pregnancy_weeks(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.pregnancy_weeks()


@router.post("/pregnancy-weeks")
async def create_week(body: WeekIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.create_week(body)


@router.post("/pregnancy-weeks/{week_id}/translations")
async def week_translation(week_id: UUID, body: WeekTranslationIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.week_translation(week_id, body)


@router.get("/child-growth-periods")
async def growth_periods(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.growth_periods()


@router.get("/followup-templates")
async def followup_templates(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.followup_templates()


@router.get("/legal-documents")
async def legal_docs(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.legal_docs()


@router.put("/legal-documents")
async def upsert_legal(body: LegalIn, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.upsert_legal(body)


@router.get("/documents")
async def documents(user: RequireAdmin, svc: AdminDep) -> list[RowOut]:
    return await svc.documents()


@router.post("/documents/{document_id}/deliver")
async def deliver_document(document_id: UUID, recipient_id: UUID, user: RequireAdmin, svc: AdminDep) -> RowOut:
    return await svc.deliver_document(document_id, recipient_id, user.id)


@router.get("/activity/admin")
async def admin_activity(user: RequireAdmin, svc: AdminDep, limit: int = 100) -> list[RowOut]:
    return await svc.admin_activity(limit)


@router.get("/activity/platform")
async def platform_activity(user: RequireAdmin, svc: AdminDep, limit: int = 100) -> list[RowOut]:
    return await svc.platform_activity(limit)


@router.post("/bootstrap-super-admin")
async def bootstrap_super_admin(body: AdminCreateIn, svc: AdminDep) -> dict[str, str]:
    return await svc.bootstrap_super_admin(body)
