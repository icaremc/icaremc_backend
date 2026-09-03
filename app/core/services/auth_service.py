from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.resources.auth.repository import SqlAlchemyAuthRepository
from app.resources.auth.service import AuthService
from app.resources.errors import AppError


def _svc(db: AsyncSession) -> AuthService:
    return AuthService(SqlAlchemyAuthRepository(db))


def _unwrap(fn):
    async def inner(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except AppError as exc:
            return {"ok": False, "detail": exc.detail}

    return inner


async def phone_taken(db: AsyncSession, phone: str, role: str | None = None) -> bool:
    return await _svc(db).phone_taken(phone, role=role)


async def request_signup_otp(db: AsyncSession, phone: str, purpose: str = "signup") -> dict:
    return await _svc(db).request_signup_otp(phone, purpose=purpose)


async def register_patient(db: AsyncSession, **kwargs) -> dict:
    try:
        return await _svc(db).register_patient(**kwargs)
    except AppError as exc:
        return {"ok": False, "detail": exc.detail}


async def register_doctor(db: AsyncSession, **kwargs) -> dict:
    try:
        return await _svc(db).register_doctor(**kwargs)
    except AppError as exc:
        return {"ok": False, "detail": exc.detail}


async def login(db: AsyncSession, **kwargs) -> dict:
    try:
        return await _svc(db).login(**kwargs)
    except AppError as exc:
        return {"ok": False, "detail": exc.detail}


async def admin_login(db: AsyncSession, **kwargs) -> dict:
    try:
        return await _svc(db).admin_login(**kwargs)
    except AppError as exc:
        return {"ok": False, "detail": exc.detail}


async def soft_delete_user(db: AsyncSession, user_id: UUID) -> None:
    user = await _svc(db)._repo.get_user_by_id(user_id)
    role = user.role if user else "patient"
    await _svc(db).soft_delete_user(user_id, role)


async def reset_password(db: AsyncSession, **kwargs) -> dict:
    try:
        return await _svc(db).reset_password(**kwargs)
    except AppError as exc:
        return {"ok": False, "detail": exc.detail}


async def ensure_admin(db: AsyncSession, **kwargs) -> UUID:
    return await _svc(db).ensure_admin(**kwargs)
