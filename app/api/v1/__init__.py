from fastapi import APIRouter
from pydantic import BaseModel

from app.resources.admin.router import router as admin_router
from app.resources.appointments.router import router as appointments_router
from app.resources.auth.router import router as auth_router
from app.resources.chat.router import router as chat_router
from app.resources.children.router import router as children_router
from app.resources.cms.router import router as cms_router
from app.resources.doctors.catalog_router import router as doctor_catalog_router
from app.resources.doctors.practice_router import router as doctor_router
from app.resources.notifications.router import router as notifications_router
from app.resources.payments.router import router as payments_router
from app.resources.pregnancies.router import router as pregnancies_router
from app.resources.profiles.router import router as profiles_router
from app.resources.push.router import router as push_router
from app.resources.settings.router import router as settings_router
from app.resources.subscriptions.router import router as subscriptions_router
from app.resources.wallets.router import router as wallets_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(profiles_router)
api_v1_router.include_router(pregnancies_router)
api_v1_router.include_router(children_router)
api_v1_router.include_router(cms_router)
api_v1_router.include_router(doctor_catalog_router)
api_v1_router.include_router(appointments_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(wallets_router)
api_v1_router.include_router(subscriptions_router)
api_v1_router.include_router(settings_router)
api_v1_router.include_router(doctor_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(payments_router)
api_v1_router.include_router(push_router)


class HealthOut(BaseModel):
    status: str


@api_v1_router.get("/health")
async def health_check() -> HealthOut:
    return HealthOut(status="ok")
