from fastapi import APIRouter

from app.api.v1.schemas import ProfileOut
from app.core.security.deps import RequirePatient
from app.resources.profiles.deps import ProfileServiceDep
from app.resources.profiles.schemas import ProfileUpdate

router = APIRouter(tags=["mother"])


@router.get("/me/profile")
async def get_profile(user: RequirePatient, svc: ProfileServiceDep) -> ProfileOut:
    return await svc.get_profile(user.id)


@router.patch("/me/profile")
async def patch_profile(body: ProfileUpdate, user: RequirePatient, svc: ProfileServiceDep) -> ProfileOut:
    return await svc.patch_profile(user.id, body)
