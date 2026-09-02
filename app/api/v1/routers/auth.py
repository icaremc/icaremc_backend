from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.core.security.deps import RequireAny
from app.core.services import auth_service
from app.core.services.sms_otp import send_otp
from app.persistence.sqlalchemy.deps import DbDep

router = APIRouter(prefix="/auth", tags=["auth"])


class PhoneBody(BaseModel):
    phone: str


class PatientSignup(BaseModel):
    phone: str
    password: str = Field(min_length=6)
    otp: str
    full_name: str
    account_type: str = "Mother"
    referral_code: str | None = None


class DoctorSignup(BaseModel):
    phone: str
    password: str = Field(min_length=6)
    otp: str
    first_name: str
    last_name: str
    specialty: str = "General"


class LoginBody(BaseModel):
    phone: str
    password: str


class AdminLoginBody(BaseModel):
    email: EmailStr
    password: str


class ResetBody(BaseModel):
    phone: str
    otp: str
    new_password: str = Field(min_length=6)


class TokenOut(BaseModel):
    ok: bool = True
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str | None = None
    roles: list[str] | None = None
    admin_role: str | None = None


class OkOut(BaseModel):
    ok: bool = True
    detail: str | None = None
    dev_code: str | None = None


class MeOut(BaseModel):
    id: str
    role: str
    roles: list[str]
    admin_role: str | None = None


class PhoneTakenOut(BaseModel):
    taken: bool


@router.post("/patient/otp")
async def patient_otp(body: PhoneBody, db: DbDep) -> OkOut:
    return OkOut(**await auth_service.request_signup_otp(db, body.phone, purpose="signup"))


@router.post("/doctor/otp")
async def doctor_otp(body: PhoneBody, db: DbDep) -> OkOut:
    return OkOut(**await auth_service.request_signup_otp(db, body.phone, purpose="doctor_signup"))


@router.post("/patient/signup")
async def patient_signup(body: PatientSignup, db: DbDep) -> TokenOut:
    result = await auth_service.register_patient(db, **body.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["detail"])
    return TokenOut(**result)


@router.post("/doctor/signup")
async def doctor_signup(body: DoctorSignup, db: DbDep) -> TokenOut:
    result = await auth_service.register_doctor(db, **body.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["detail"])
    return TokenOut(**result)


@router.post("/patient/login")
async def patient_login(body: LoginBody, db: DbDep) -> TokenOut:
    result = await auth_service.login(db, phone=body.phone, password=body.password, expected_role="patient")
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["detail"])
    return TokenOut(**result)


@router.post("/doctor/login")
async def doctor_login(body: LoginBody, db: DbDep) -> TokenOut:
    result = await auth_service.login(db, phone=body.phone, password=body.password, expected_role="doctor")
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["detail"])
    return TokenOut(**result)


@router.post("/admin/login")
async def admin_login(body: AdminLoginBody, db: DbDep) -> TokenOut:
    result = await auth_service.admin_login(db, email=body.email, password=body.password)
    if not result["ok"]:
        raise HTTPException(status_code=401, detail=result["detail"])
    return TokenOut(**result)


@router.post("/password/otp")
async def password_otp(body: PhoneBody, db: DbDep) -> OkOut:
    code = await send_otp(db, phone=body.phone, purpose="reset")
    return OkOut(ok=True, dev_code=code or None)


@router.post("/password/reset")
async def password_reset(body: ResetBody, db: DbDep) -> OkOut:
    result = await auth_service.reset_password(
        db, phone=body.phone, otp=body.otp, new_password=body.new_password
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["detail"])
    return OkOut(**result)


@router.get("/me")
async def me(user: RequireAny) -> MeOut:
    return MeOut(id=str(user.id), role=user.role, roles=user.roles, admin_role=user.admin_role)


@router.delete("/me")
async def delete_me(user: RequireAny, db: DbDep) -> OkOut:
    if user.role not in ("patient", "doctor"):
        raise HTTPException(status_code=403, detail="Forbidden")
    await auth_service.soft_delete_user(db, user.id)
    return OkOut(ok=True)


@router.get("/phone-taken")
async def phone_taken(
    phone: Annotated[str, Query(min_length=5)],
    db: DbDep,
    role: Annotated[str | None, Query()] = None,
) -> PhoneTakenOut:
    return PhoneTakenOut(taken=await auth_service.phone_taken(db, phone, role=role))
