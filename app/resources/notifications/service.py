from datetime import UTC, datetime
from uuid import UUID

from app.api.v1.schemas import RowOut
from app.resources.errors import not_found
from app.resources.notifications.repository import NotificationRepository
from app.resources.serialize import require_row, to_rows


class NotificationService:
    def __init__(self, repo: NotificationRepository) -> None:
        self._repo = repo

    async def list_for_user(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_for_user(user_id))

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> RowOut:
        row = await self._repo.get_for_user(notification_id, user_id)
        if row is None:
            raise not_found()
        row.read_at = datetime.now(UTC)
        await self._repo.flush()
        return require_row(row)
