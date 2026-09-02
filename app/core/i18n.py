from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.deps import AuthUser, bearer, get_current_user
from app.persistence.sqlalchemy.deps import DbDep
from app.persistence.sqlalchemy.models import Profile
from app.persistence.sqlalchemy.serialize import row_dict
from fastapi.security import HTTPAuthorizationCredentials


async def optional_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbDep,
) -> AuthUser | None:
    if creds is None or not creds.credentials:
        return None
    try:
        return await get_current_user(creds, db)
    except Exception:
        return None


def parse_accept_language(header: str | None) -> str | None:
    if not header:
        return None
    # "am-ET,am;q=0.9,en;q=0.8" -> "am"
    first = header.split(",")[0].strip()
    if not first:
        return None
    return first.split(";")[0].strip().split("-")[0].lower() or None


async def resolve_lang(
    db: AsyncSession,
    *,
    lang: str | None,
    accept_language: str | None,
    user_id: UUID | None,
) -> str:
    if lang:
        return lang.lower()
    if user_id is not None:
        profile = (await db.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()
        if profile and profile.locale:
            return profile.locale.lower()
    header_lang = parse_accept_language(accept_language)
    if header_lang:
        return header_lang
    return "en"


async def lang_dep(
    db: DbDep,
    lang: Annotated[str | None, Query(description="Content language, e.g. en|am")] = None,
    accept_language: Annotated[str | None, Header()] = None,
    user: Annotated[AuthUser | None, Depends(optional_user)] = None,
) -> str:
    return await resolve_lang(
        db,
        lang=lang,
        accept_language=accept_language,
        user_id=user.id if user else None,
    )


LangDep = Annotated[str, Depends(lang_dep)]


async def translation_or_en(
    db: AsyncSession,
    *,
    model,
    id_column,
    entity_id,
    lang: str,
):
    """Load translation for lang; fall back to English."""
    row = (
        await db.execute(select(model).where(id_column == entity_id, model.language_code == lang))
    ).scalar_one_or_none()
    if row is None and lang != "en":
        row = (
            await db.execute(select(model).where(id_column == entity_id, model.language_code == "en"))
        ).scalar_one_or_none()
    return row


def cms_item(entity, translation) -> dict:
    item = row_dict(entity)
    item["translation"] = row_dict(translation) if translation else None
    item["lang_resolved"] = translation.language_code if translation else None
    return item
