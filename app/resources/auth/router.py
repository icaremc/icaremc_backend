from typing import Annotated

from fastapi import APIRouter, Query

from app.core.security.deps import RequireAny
from app.resources.auth.deps import AuthServiceDep
from app.resources.auth.schemas import (
    AdminLoginBody,
    DoctorSignup,
    LoginBody,
    MeOut,
    OkOut,
    PatientSignup,
    PhoneBody,
    PhoneTakenOut,
    RefreshBody,
    ResetBody,
    TokenOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/patient/otp")
async def patient_otp(body: PhoneBody, svc: AuthServiceDep) -> OkOut:
    return OkOut(**await svc.request_signup_otp(body.phone, purpose="signup"))


@router.post("/doctor/otp")
async def doctor_otp(body: PhoneBody, svc: AuthServiceDep) -> OkOut:
    return OkOut(**await svc.request_signup_otp(body.phone, purpose="doctor_signup"))


@router.post("/patient/signup")
async def patient_signup(body: PatientSignup, svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.register_patient(**body.model_dump()))


@router.post("/doctor/signup")
async def doctor_signup(body: DoctorSignup, svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.register_doctor(**body.model_dump()))


@router.post("/patient/login")
async def patient_login(body: LoginBody, svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.login(phone=body.phone, password=body.password, expected_role="patient"))


@router.post("/doctor/login")
async def doctor_login(body: LoginBody, svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.login(phone=body.phone, password=body.password, expected_role="doctor"))


@router.post("/admin/login")
async def admin_login(body: AdminLoginBody, svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.admin_login(email=body.email, password=body.password))


@router.post("/password/otp")
async def password_otp(body: PhoneBody, svc: AuthServiceDep) -> OkOut:
    return OkOut(**await svc.request_reset_otp(body.phone))


@router.post("/password/reset")
async def password_reset(body: ResetBody, svc: AuthServiceDep) -> OkOut:
    return OkOut(**await svc.reset_password(phone=body.phone, otp=body.otp, new_password=body.new_password))


@router.post("/refresh")
async def refresh(body: RefreshBody, svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.refresh(body.refresh_token))


@router.post("/logout")
async def logout(body: RefreshBody, svc: AuthServiceDep) -> OkOut:
    return OkOut(**await svc.logout(body.refresh_token))


@router.get("/me")
async def me(user: RequireAny) -> MeOut:
    return MeOut(id=str(user.id), role=user.role, roles=user.roles, admin_role=user.admin_role)


@router.delete("/me")
async def delete_me(user: RequireAny, svc: AuthServiceDep) -> OkOut:
    await svc.soft_delete_user(user.id, user.role)
    return OkOut(ok=True)


@router.get("/phone-taken")
async def phone_taken(
    phone: Annotated[str, Query(min_length=5)],
    svc: AuthServiceDep,
    role: Annotated[str | None, Query()] = None,
) -> PhoneTakenOut:
    return PhoneTakenOut(taken=await svc.phone_taken(phone, role=role))
