from app.resources.settings.repository import SettingsRepository


class SettingsService:
    def __init__(self, repo: SettingsRepository) -> None:
        self._repo = repo

    async def get_public(self, setting_id: str) -> dict[str, object]:
        row = await self._repo.get(setting_id)
        return row.data if row else {}
