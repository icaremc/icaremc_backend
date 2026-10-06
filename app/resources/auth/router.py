from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security.deps import RequireAny, bearer
from app.persistence.sqlalchemy.deps import DbDep
from app.persistence.sqlalchemy.models import AdminUser, DoctorProfile, Profile, User
from sqlalchemy import select
from app.resources.auth.deps import AuthServiceDep
from app.resources.errors import AppError
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
    SessionOut,
    SessionUserOut,
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
async def patient_login(body: Annotated[OAuth2PasswordRequestForm, Depends()], svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.login(phone=body.username, password=body.password, expected_role="patient"))


@router.post("/doctor/login")
async def doctor_login(body: Annotated[OAuth2PasswordRequestForm, Depends()], svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.login(phone=body.username, password=body.password, expected_role="doctor"))


@router.post("/admin/login")
async def admin_login(body: Annotated[OAuth2PasswordRequestForm, Depends()], svc: AuthServiceDep) -> TokenOut:
    return TokenOut(**await svc.admin_login(email=body.username, password=body.password))


@router.post("/token", include_in_schema=False)
async def swagger_login(body: Annotated[OAuth2PasswordRequestForm, Depends()], svc: AuthServiceDep) -> TokenOut:
    if "@" in body.username:
        return TokenOut(**await svc.admin_login(email=body.username, password=body.password))
    try:
        return TokenOut(**await svc.login(phone=body.username, password=body.password, expected_role="doctor"))
    except AppError:
        return TokenOut(**await svc.login(phone=body.username, password=body.password, expected_role="patient"))


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


@router.get("/session")
async def session(
    user: RequireAny,
    token: Annotated[str | None, Depends(bearer)],
    db: DbDep,
) -> SessionOut:
    email = None
    name = "User"
    
    if user.role == "admin":
        admin = (await db.execute(select(AdminUser).where(AdminUser.id == user.id))).scalar_one_or_none()
        if admin:
            email = admin.email
            name = admin.full_name or "Admin"
    elif user.role == "doctor":
        doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == user.id))).scalar_one_or_none()
        if doctor:
            name = f"{doctor.first_name} {doctor.last_name}"
    else:
        profile = (await db.execute(select(Profile).where(Profile.id == user.id))).scalar_one_or_none()
        if profile and profile.full_name:
            name = profile.full_name
            
    if not email:
        user_record = (await db.execute(select(User).where(User.id == user.id))).scalar_one_or_none()
        if user_record and user_record.email:
            email = user_record.email

    return SessionOut(
        mode="backend",
        token=token,
        user=SessionUserOut(
            id=user.id,
            email=email or "",
            name=name,
            adminRole=user.admin_role
        )
    )
