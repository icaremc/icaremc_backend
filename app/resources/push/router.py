from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.schemas import PushOut
from app.core.security.deps import RequireAdmin
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.push.repository import SqlAlchemyPushRepository
from app.resources.push.schemas import PushIn
from app.resources.push.service import PushService

router = APIRouter(prefix="/push", tags=["push"])


def get_push_service(db: DbDep) -> PushService:
    return PushService(SqlAlchemyPushRepository(db))


PushServiceDep = Annotated[PushService, Depends(get_push_service)]


@router.post("/notify")
async def notify(body: PushIn, user: RequireAdmin, svc: PushServiceDep) -> PushOut:
    return await svc.notify(body)
