from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, OAuth2PasswordBearer
from sqlalchemy import select

from app.core.security.tokens import decode_access_token
from app.core.services.roles import has_role, roles_of
from app.persistence.sqlalchemy.deps import DbDep
from app.persistence.sqlalchemy.models import AdminUser, User
from app.resources.errors import forbidden, unauthorized

bearer = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


@dataclass
class AuthUser:
    id: UUID
    role: str
    roles: list[str]
    admin_role: str | None = None


async def get_current_user(
    token: Annotated[str | None, Depends(bearer)],
    db: DbDep,
) -> AuthUser:
    if not token:
        raise unauthorized("Not authenticated")
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise unauthorized("Invalid token") from exc
    user_id = UUID(payload["sub"])
    role = payload.get("role")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None or not has_role(user, role):
        raise unauthorized("User not found")
    admin_role = None
    if role == "admin":
        admin = (
            await db.execute(select(AdminUser).where(AdminUser.id == user_id, AdminUser.is_active.is_(True)))
        ).scalar_one_or_none()
        if admin is None:
            raise forbidden("Admin inactive")
        admin_role = admin.admin_role
    return AuthUser(id=user.id, role=role, roles=roles_of(user), admin_role=admin_role)


def require_roles(*roles: str):
    async def _dep(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
        if user.role not in roles:
            raise forbidden()
        return user

    return _dep


RequirePatient = Annotated[AuthUser, Depends(require_roles("patient"))]
RequireDoctor = Annotated[AuthUser, Depends(require_roles("doctor"))]
RequireAdmin = Annotated[AuthUser, Depends(require_roles("admin"))]
RequireAny = Annotated[AuthUser, Depends(get_current_user)]
