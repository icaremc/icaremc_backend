from pydantic import BaseModel, EmailStr, Field


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
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str | None = None
    roles: list[str] | None = None
    admin_role: str | None = None


class RefreshBody(BaseModel):
    refresh_token: str


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
