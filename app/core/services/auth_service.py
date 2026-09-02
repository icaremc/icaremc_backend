import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.tokens import create_access_token, hash_password, verify_password
from app.core.services.roles import ensure_roles, get_user_by_phone, has_role, roles_of
from app.core.services.sms_otp import normalize_phone, send_otp, verify_otp
from app.persistence.sqlalchemy.models import (
    AdminUser,
    DoctorProfile,
    DoctorReferral,
    DoctorWallet,
    PatientWallet,
    Profile,
    User,
)


def _referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "DR" + "".join(secrets.choice(alphabet) for _ in range(6))


async def phone_taken(db: AsyncSession, phone: str, role: str | None = None) -> bool:
    phone = normalize_phone(phone)
    user = (
        await db.execute(select(User).where(User.phone == phone, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if user is None:
        return False
    if role is None:
        return True
    return has_role(user, role)


async def request_signup_otp(db: AsyncSession, phone: str, purpose: str = "signup") -> dict:
    role = "patient" if purpose == "signup" else "doctor"
    if await phone_taken(db, phone, role=role):
        return {"ok": False, "detail": "Phone already registered"}
    code = await send_otp(db, phone=phone, purpose=purpose)
    return {"ok": True, "dev_code": code or None}


async def register_patient(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    otp: str,
    full_name: str,
    account_type: str = "Mother",
    referral_code: str | None = None,
) -> dict:
    phone = normalize_phone(phone)
    if not await verify_otp(db, phone=phone, purpose="signup", code=otp):
        return {"ok": False, "detail": "Invalid OTP"}
    if await phone_taken(db, phone, role="patient"):
        return {"ok": False, "detail": "Phone already registered as patient"}

    existing = await get_user_by_phone(db, phone)
    if existing is not None:
        if not verify_password(password, existing.password_hash):
            return {"ok": False, "detail": "Wrong password for existing account"}
        user = existing
        ensure_roles(user, "patient")
    else:
        user = User(
            phone=phone,
            password_hash=hash_password(password),
            role="patient",
            roles=["patient"],
        )
        db.add(user)
        await db.flush()

    referred_by = None
    code_used = None
    if referral_code:
        doctor = (
            await db.execute(select(DoctorProfile).where(DoctorProfile.referral_code == referral_code.strip().upper()))
        ).scalar_one_or_none()
        if doctor:
            referred_by = doctor.id
            code_used = doctor.referral_code
            db.add(DoctorReferral(patient_id=user.id, doctor_id=doctor.id, referral_code=doctor.referral_code))

    profile = (await db.execute(select(Profile).where(Profile.id == user.id))).scalar_one_or_none()
    if profile is None:
        db.add(
            Profile(
                id=user.id,
                full_name=full_name,
                phone=phone,
                account_type=account_type,
                referred_by_doctor_id=referred_by,
                referral_code_used=code_used,
            )
        )
        await db.flush()
        db.add(PatientWallet(patient_id=user.id))
        await db.flush()
    else:
        profile.full_name = full_name or profile.full_name
        await db.flush()

    token = create_access_token(sub=user.id, role="patient")
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": "patient",
        "roles": roles_of(user),
    }


async def register_doctor(
    db: AsyncSession,
    *,
    phone: str,
    password: str,
    otp: str,
    first_name: str,
    last_name: str,
    specialty: str = "General",
) -> dict:
    phone = normalize_phone(phone)
    if not await verify_otp(db, phone=phone, purpose="doctor_signup", code=otp):
        return {"ok": False, "detail": "Invalid OTP"}
    if await phone_taken(db, phone, role="doctor"):
        return {"ok": False, "detail": "Phone already registered as doctor"}

    existing = await get_user_by_phone(db, phone)
    if existing is not None:
        if not verify_password(password, existing.password_hash):
            return {"ok": False, "detail": "Wrong password for existing account"}
        user = existing
        ensure_roles(user, "doctor")
    else:
        user = User(
            phone=phone,
            password_hash=hash_password(password),
            role="doctor",
            roles=["doctor"],
        )
        db.add(user)
        await db.flush()

    doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == user.id))).scalar_one_or_none()
    if doctor is None:
        code = _referral_code()
        while (await db.execute(select(DoctorProfile).where(DoctorProfile.referral_code == code))).scalar_one_or_none():
            code = _referral_code()
        db.add(
            DoctorProfile(
                id=user.id,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                specialty=specialty,
                hospital="",
                referral_code=code,
            )
        )
        await db.flush()
        db.add(DoctorWallet(doctor_id=user.id))
        await db.flush()

    token = create_access_token(sub=user.id, role="doctor")
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": "doctor",
        "roles": roles_of(user),
    }


async def login(db: AsyncSession, *, phone: str, password: str, expected_role: str | None = None) -> dict:
    phone = normalize_phone(phone)
    user = await get_user_by_phone(db, phone)
    if user is None or not verify_password(password, user.password_hash):
        return {"ok": False, "detail": "Invalid credentials"}
    if expected_role and not has_role(user, expected_role):
        return {"ok": False, "detail": f"Not a {expected_role} account"}
    active_role = expected_role or user.role
    if active_role == "doctor":
        doctor = (await db.execute(select(DoctorProfile).where(DoctorProfile.id == user.id))).scalar_one_or_none()
        if doctor is None:
            return {"ok": False, "detail": "Doctor profile missing"}
    token = create_access_token(sub=user.id, role=active_role)
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": active_role,
        "roles": roles_of(user),
    }


async def admin_login(db: AsyncSession, *, email: str, password: str) -> dict:
    admin = (await db.execute(select(AdminUser).where(AdminUser.email == email.lower(), AdminUser.is_active.is_(True)))).scalar_one_or_none()
    if admin is None:
        return {"ok": False, "detail": "Invalid credentials"}
    user = (await db.execute(select(User).where(User.id == admin.id, User.is_active.is_(True)))).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return {"ok": False, "detail": "Invalid credentials"}
    token = create_access_token(sub=user.id, role="admin", extra={"admin_role": admin.admin_role})
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": "admin",
        "admin_role": admin.admin_role,
        "roles": ["admin"],
    }


async def soft_delete_user(db: AsyncSession, user_id: UUID) -> None:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    user.deleted_at = datetime.now(UTC)
    user.is_active = False
    await db.flush()


async def reset_password(db: AsyncSession, *, phone: str, otp: str, new_password: str) -> dict:
    phone = normalize_phone(phone)
    if not await verify_otp(db, phone=phone, purpose="reset", code=otp):
        return {"ok": False, "detail": "Invalid OTP"}
    user = (await db.execute(select(User).where(User.phone == phone, User.deleted_at.is_(None)))).scalar_one_or_none()
    if user is None:
        return {"ok": False, "detail": "User not found"}
    user.password_hash = hash_password(new_password)
    await db.flush()
    return {"ok": True}


async def ensure_admin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str = "Admin",
    admin_role: str = "super_admin",
) -> UUID:
    existing = (await db.execute(select(AdminUser).where(AdminUser.email == email.lower()))).scalar_one_or_none()
    if existing:
        return existing.id
    phone = f"admin-{email.lower()}"
    user = User(
        phone=phone,
        email=email.lower(),
        password_hash=hash_password(password),
        role="admin",
        roles=["admin"],
    )
    db.add(user)
    await db.flush()
    db.add(AdminUser(id=user.id, email=email.lower(), full_name=full_name, admin_role=admin_role))
    await db.flush()
    return user.id
