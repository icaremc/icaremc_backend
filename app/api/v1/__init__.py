from fastapi import APIRouter

from app.api.v1.routers import admin, auth, doctor, mother, payments, push

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router)
api_v1_router.include_router(mother.router)
api_v1_router.include_router(doctor.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(payments.router)
api_v1_router.include_router(push.router)


@api_v1_router.get("/health")
async def health_check():
    return {"status": "ok"}
