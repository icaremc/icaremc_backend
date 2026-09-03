from datetime import UTC, datetime
from uuid import UUID

from app.core.security.tokens import create_access_token, hash_password, verify_password
from app.core.services.roles import ensure_roles, has_role, roles_of
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
from app.resources.auth.repository import AuthRepository
from app.resources.errors import bad_request, forbidden, unauthorized

import secrets
import string


def _referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "DR" + "".join(secrets.choice(alphabet) for _ in range(6))


class AuthService:
    def __init__(self, repo: AuthRepository) -> None:
        self._repo = repo

    async def phone_taken(self, phone: str, role: str | None = None) -> bool:
        phone = normalize_phone(phone)
        user = await self._repo.get_user_by_phone(phone)
        if user is None:
            return False
        if role is None:
            return True
        return has_role(user, role)

    async def request_signup_otp(self, phone: str, purpose: str = "signup") -> dict:
        role = "patient" if purpose == "signup" else "doctor"
        if await self.phone_taken(phone, role=role):
            return {"ok": False, "detail": "Phone already registered"}
        code = await send_otp(self._repo.session, phone=phone, purpose=purpose)
        return {"ok": True, "dev_code": code or None}

    async def register_patient(
        self,
        *,
        phone: str,
        password: str,
        otp: str,
        full_name: str,
        account_type: str = "Mother",
        referral_code: str | None = None,
    ) -> dict:
        phone = normalize_phone(phone)
        db = self._repo.session
        if not await verify_otp(db, phone=phone, purpose="signup", code=otp):
            raise bad_request("Invalid OTP")
        if await self.phone_taken(phone, role="patient"):
            raise bad_request("Phone already registered as patient")

        existing = await self._repo.get_user_by_phone(phone)
        if existing is not None:
            if not verify_password(password, existing.password_hash):
                raise bad_request("Wrong password for existing account")
            user = existing
            ensure_roles(user, "patient")
        else:
            user = User(
                phone=phone,
                password_hash=hash_password(password),
                role="patient",
                roles=["patient"],
            )
            self._repo.add(user)
            await self._repo.flush()

        referred_by = None
        code_used = None
        if referral_code:
            doctor = await self._repo.get_doctor_by_referral(referral_code.strip().upper())
            if doctor:
                referred_by = doctor.id
                code_used = doctor.referral_code
                self._repo.add(DoctorReferral(patient_id=user.id, doctor_id=doctor.id, referral_code=doctor.referral_code))

        profile = await self._repo.get_profile(user.id)
        if profile is None:
            self._repo.add(
                Profile(
                    id=user.id,
                    full_name=full_name,
                    phone=phone,
                    account_type=account_type,
                    referred_by_doctor_id=referred_by,
                    referral_code_used=code_used,
                )
            )
            await self._repo.flush()
            self._repo.add(PatientWallet(patient_id=user.id))
            await self._repo.flush()
        else:
            profile.full_name = full_name or profile.full_name
            await self._repo.flush()

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
        self,
        *,
        phone: str,
        password: str,
        otp: str,
        first_name: str,
        last_name: str,
        specialty: str = "General",
    ) -> dict:
        phone = normalize_phone(phone)
        db = self._repo.session
        if not await verify_otp(db, phone=phone, purpose="doctor_signup", code=otp):
            raise bad_request("Invalid OTP")
        if await self.phone_taken(phone, role="doctor"):
            raise bad_request("Phone already registered as doctor")

        existing = await self._repo.get_user_by_phone(phone)
        if existing is not None:
            if not verify_password(password, existing.password_hash):
                raise bad_request("Wrong password for existing account")
            user = existing
            ensure_roles(user, "doctor")
        else:
            user = User(
                phone=phone,
                password_hash=hash_password(password),
                role="doctor",
                roles=["doctor"],
            )
            self._repo.add(user)
            await self._repo.flush()

        doctor = await self._repo.get_doctor(user.id)
        if doctor is None:
            code = _referral_code()
            while await self._repo.referral_code_taken(code):
                code = _referral_code()
            self._repo.add(
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
            await self._repo.flush()
            self._repo.add(DoctorWallet(doctor_id=user.id))
            await self._repo.flush()

        token = create_access_token(sub=user.id, role="doctor")
        return {
            "ok": True,
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "role": "doctor",
            "roles": roles_of(user),
        }

    async def login(self, *, phone: str, password: str, expected_role: str | None = None) -> dict:
        phone = normalize_phone(phone)
        user = await self._repo.get_user_by_phone(phone)
        if user is None or not verify_password(password, user.password_hash):
            raise unauthorized("Invalid credentials")
        if expected_role and not has_role(user, expected_role):
            raise unauthorized(f"Not a {expected_role} account")
        active_role = expected_role or user.role
        if active_role == "doctor":
            doctor = await self._repo.get_doctor(user.id)
            if doctor is None:
                raise unauthorized("Doctor profile missing")
        token = create_access_token(sub=user.id, role=active_role)
        return {
            "ok": True,
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "role": active_role,
            "roles": roles_of(user),
        }

    async def admin_login(self, *, email: str, password: str) -> dict:
        admin = await self._repo.get_admin_by_email(email)
        if admin is None:
            raise unauthorized("Invalid credentials")
        user = await self._repo.get_user(admin.id)
        if user is None or not verify_password(password, user.password_hash):
            raise unauthorized("Invalid credentials")
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

    async def soft_delete_user(self, user_id: UUID, role: str) -> None:
        if role not in ("patient", "doctor"):
            raise forbidden()
        user = await self._repo.get_user_by_id(user_id)
        if user is None:
            raise bad_request("User not found")
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        await self._repo.flush()

    async def request_reset_otp(self, phone: str) -> dict:
        db = self._repo.session
        code = await send_otp(db, phone=phone, purpose="reset")
        return {"ok": True, "dev_code": code or None}

    async def reset_password(self, *, phone: str, otp: str, new_password: str) -> dict:
        phone = normalize_phone(phone)
        db = self._repo.session
        if not await verify_otp(self._repo.session, phone=phone, purpose="reset", code=otp):
            raise bad_request("Invalid OTP")
        user = await self._repo.get_user_by_phone_not_deleted(phone)
        if user is None:
            raise bad_request("User not found")
        user.password_hash = hash_password(new_password)
        await self._repo.flush()
        return {"ok": True}

    async def ensure_admin(
        self,
        *,
        email: str,
        password: str,
        full_name: str = "Admin",
        admin_role: str = "super_admin",
    ) -> UUID:
        from sqlalchemy import select

        db = self._repo.session
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
        self._repo.add(user)
        await self._repo.flush()
        self._repo.add(AdminUser(id=user.id, email=email.lower(), full_name=full_name, admin_role=admin_role))
        await self._repo.flush()
        return user.id

    async def bootstrap_super_admin(self, *, email: str, password: str, full_name: str) -> UUID:
        if await self._repo.count_admins() > 0:
            raise forbidden("Admins already exist")
        return await self.ensure_admin(
            email=email, password=password, full_name=full_name, admin_role="super_admin"
        )
