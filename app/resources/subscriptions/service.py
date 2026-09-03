from uuid import UUID

from app.api.v1.schemas import RowOut
from app.resources.serialize import to_row, to_rows
from app.resources.subscriptions.repository import SubscriptionRepository


class SubscriptionService:
    def __init__(self, repo: SubscriptionRepository) -> None:
        self._repo = repo

    async def app_subscription(self, user_id: UUID) -> RowOut | None:
        return to_row(await self._repo.active_app(user_id))

    async def care_subscriptions(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_care(user_id))
