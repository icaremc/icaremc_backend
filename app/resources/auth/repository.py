from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import AdminUser, DoctorProfile, DoctorReferral, DoctorWallet, PatientWallet, Profile, User


class AuthRepository(Protocol):
    @property
    def session(self) -> AsyncSession: ...
    async def get_user_by_phone(self, phone: str) -> User | None: ...
    async def get_user_by_phone_not_deleted(self, phone: str) -> User | None: ...
    async def get_user_by_id(self, user_id: UUID) -> User | None: ...
    async def get_admin_by_email(self, email: str) -> AdminUser | None: ...
    async def get_user(self, user_id: UUID) -> User | None: ...
    async def get_profile(self, user_id: UUID) -> Profile | None: ...
    async def get_doctor(self, user_id: UUID) -> DoctorProfile | None: ...
    async def get_doctor_by_referral(self, code: str) -> DoctorProfile | None: ...
    async def referral_code_taken(self, code: str) -> bool: ...
    async def count_admins(self) -> int: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyAuthRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.session = db

    async def get_user_by_phone(self, phone: str) -> User | None:
        return (
            await self.session.execute(
                select(User).where(User.phone == phone, User.deleted_at.is_(None), User.is_active.is_(True))
            )
        ).scalar_one_or_none()

    async def get_user_by_phone_not_deleted(self, phone: str) -> User | None:
        return (
            await self.session.execute(select(User).where(User.phone == phone, User.deleted_at.is_(None)))
        ).scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return (await self.session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    async def get_admin_by_email(self, email: str) -> AdminUser | None:
        return (
            await self.session.execute(
                select(AdminUser).where(AdminUser.email == email.lower(), AdminUser.is_active.is_(True))
            )
        ).scalar_one_or_none()

    async def get_user(self, user_id: UUID) -> User | None:
        return (
            await self.session.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        ).scalar_one_or_none()

    async def get_profile(self, user_id: UUID) -> Profile | None:
        return (await self.session.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()

    async def get_doctor(self, user_id: UUID) -> DoctorProfile | None:
        return (await self.session.execute(select(DoctorProfile).where(DoctorProfile.id == user_id))).scalar_one_or_none()

    async def get_doctor_by_referral(self, code: str) -> DoctorProfile | None:
        return (
            await self.session.execute(select(DoctorProfile).where(DoctorProfile.referral_code == code))
        ).scalar_one_or_none()

    async def referral_code_taken(self, code: str) -> bool:
        return (await self.get_doctor_by_referral(code)) is not None

    async def count_admins(self) -> int:
        from sqlalchemy import func

        return (await self.session.execute(select(func.count()).select_from(AdminUser))).scalar_one()

    def add(self, obj: object) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        await self.session.flush()
