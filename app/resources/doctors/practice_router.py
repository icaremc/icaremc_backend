from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.schemas import OkOut, RowOut, WalletBundleOut
from app.core.security.deps import RequireDoctor
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.appointments.router import get_appointment_service
from app.resources.appointments.service import AppointmentService
from app.resources.chat.router import get_chat_service
from app.resources.chat.schemas import ChatIn
from app.resources.chat.service import ChatService
from app.resources.doctors.practice import PracticeService
from app.resources.doctors.practice_repository import SqlAlchemyPracticeRepository
from app.resources.doctors.practice_schemas import (
    PayoutIn,
    PayoutMethodIn,
    ProfileUpdate,
    ServiceIn,
    SlotIn,
)
from app.resources.notifications.router import get_notification_service
from app.resources.notifications.service import NotificationService
from app.resources.settings.router import get_settings_service
from app.resources.settings.service import SettingsService

router = APIRouter(prefix="/doctor", tags=["doctor"])


def get_practice_service(db: DbDep) -> PracticeService:
    return PracticeService(SqlAlchemyPracticeRepository(db))


PracticeDep = Annotated[PracticeService, Depends(get_practice_service)]
AppointmentDep = Annotated[AppointmentService, Depends(get_appointment_service)]
ChatDep = Annotated[ChatService, Depends(get_chat_service)]
NotificationDep = Annotated[NotificationService, Depends(get_notification_service)]
SettingsDep = Annotated[SettingsService, Depends(get_settings_service)]


class StatusIn(BaseModel):
    status: str


@router.get("/me")
async def me(user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.me(user.id)


@router.patch("/me")
async def patch_me(body: ProfileUpdate, user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.patch_me(user.id, body)


@router.get("/services")
async def list_services(user: RequireDoctor, svc: PracticeDep) -> list[RowOut]:
    return await svc.list_services(user.id)


@router.post("/services")
async def create_service(body: ServiceIn, user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.create_service(user.id, body)


@router.patch("/services/{service_id}")
async def patch_service(service_id: UUID, body: ServiceIn, user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.patch_service(service_id, user.id, body)


@router.delete("/services/{service_id}")
async def delete_service(service_id: UUID, user: RequireDoctor, svc: PracticeDep) -> OkOut:
    return await svc.delete_service(service_id, user.id)


@router.get("/slots")
async def list_slots(user: RequireDoctor, svc: PracticeDep) -> list[RowOut]:
    return await svc.list_slots(user.id)


@router.post("/slots")
async def create_slot(body: SlotIn, user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.create_slot(user.id, body)


@router.delete("/slots/{slot_id}")
async def delete_slot(slot_id: UUID, user: RequireDoctor, svc: PracticeDep) -> OkOut:
    return await svc.delete_slot(slot_id, user.id)


@router.get("/appointments")
async def appointments(user: RequireDoctor, svc: AppointmentDep) -> list[RowOut]:
    return await svc.list_doctor(user.id)


@router.post("/appointments/{appointment_id}/status")
async def set_status(appointment_id: UUID, body: StatusIn, user: RequireDoctor, svc: AppointmentDep) -> RowOut:
    return await svc.set_status(appointment_id, user.id, body.status)


@router.get("/wallet")
async def wallet(user: RequireDoctor, svc: PracticeDep) -> WalletBundleOut:
    return await svc.wallet(user.id)


@router.get("/payout-methods")
async def payout_methods(user: RequireDoctor, svc: PracticeDep) -> list[RowOut]:
    return await svc.list_payout_methods(user.id)


@router.post("/payout-methods")
async def create_payout_method(body: PayoutMethodIn, user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.create_payout_method(user.id, body)


@router.post("/payouts")
async def create_payout(body: PayoutIn, user: RequireDoctor, svc: PracticeDep) -> RowOut:
    return await svc.create_payout(user.id, body)


@router.get("/payouts")
async def list_payouts(user: RequireDoctor, svc: PracticeDep) -> list[RowOut]:
    return await svc.list_payouts(user.id)


@router.get("/referrals")
async def referrals(user: RequireDoctor, svc: PracticeDep) -> dict[str, object]:
    return await svc.referrals(user.id)


@router.get("/hospitals")
async def hospitals(svc: PracticeDep) -> list[RowOut]:
    return await svc.hospitals()


@router.post("/hospitals/{hospital_id}/affiliate")
async def affiliate(hospital_id: UUID, user: RequireDoctor, svc: PracticeDep, is_primary: bool = False) -> RowOut:
    return await svc.affiliate(hospital_id, user.id, is_primary)


@router.get("/chat/conversations")
async def conversations(user: RequireDoctor, svc: ChatDep) -> list[RowOut]:
    return await svc.list_doctor(user.id)


@router.get("/chat/conversations/{conversation_id}/messages")
async def messages(conversation_id: UUID, user: RequireDoctor, svc: ChatDep) -> list[RowOut]:
    return await svc.messages_doctor(conversation_id, user.id)


@router.post("/chat/conversations/{conversation_id}/messages")
async def send_message(conversation_id: UUID, body: ChatIn, user: RequireDoctor, svc: ChatDep) -> RowOut:
    return await svc.send_doctor(conversation_id, user.id, body)


@router.get("/notifications")
async def notifications(user: RequireDoctor, svc: NotificationDep) -> list[RowOut]:
    return await svc.list_for_user(user.id)


@router.get("/reviews")
async def reviews(user: RequireDoctor, svc: AppointmentDep) -> list[RowOut]:
    return await svc.list_reviews_for_doctor(user.id)


@router.get("/settings/version")
async def version_policy(svc: SettingsDep) -> dict:
    return await svc.get_public("doctors_version")
