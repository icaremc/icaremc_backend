from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import User


def has_role(user: User, role: str) -> bool:
    roles = list(user.roles or [])
    if role in roles:
        return True
    # ponytail: legacy single-role rows until backfill
    return user.role == role


def ensure_roles(user: User, *roles: str) -> None:
    current = list(user.roles or [])
    for role in roles:
        if role not in current:
            current.append(role)
    user.roles = current
    if user.role not in current:
        user.role = current[0]


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    return (
        await db.execute(select(User).where(User.phone == phone, User.deleted_at.is_(None), User.is_active.is_(True)))
    ).scalar_one_or_none()


def roles_of(user: User) -> list[str]:
    roles = list(user.roles or [])
    if user.role and user.role not in roles:
        roles.append(user.role)
    return roles
