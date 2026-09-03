from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.subscriptions.repository import SqlAlchemySubscriptionRepository
from app.resources.subscriptions.service import SubscriptionService

router = APIRouter(tags=["mother"])


def get_subscription_service(db: DbDep) -> SubscriptionService:
    return SubscriptionService(SqlAlchemySubscriptionRepository(db))


SubscriptionServiceDep = Annotated[SubscriptionService, Depends(get_subscription_service)]


@router.get("/subscriptions/app")
async def app_subscription(user: RequirePatient, svc: SubscriptionServiceDep) -> RowOut | None:
    return await svc.app_subscription(user.id)


@router.get("/subscriptions/care")
async def care_subscriptions(user: RequirePatient, svc: SubscriptionServiceDep) -> list[RowOut]:
    return await svc.care_subscriptions(user.id)
