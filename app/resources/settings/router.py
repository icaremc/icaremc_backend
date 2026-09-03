from typing import Annotated

from fastapi import APIRouter, Depends

from app.persistence.sqlalchemy.deps import DbDep
from app.resources.settings.repository import SqlAlchemySettingsRepository
from app.resources.settings.service import SettingsService

router = APIRouter(tags=["mother"])


def get_settings_service(db: DbDep) -> SettingsService:
    return SettingsService(SqlAlchemySettingsRepository(db))


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]


@router.get("/settings/{setting_id}")
async def get_setting(setting_id: str, svc: SettingsServiceDep) -> dict[str, object]:
    return await svc.get_public(setting_id)
