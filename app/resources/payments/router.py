from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.api.v1.schemas import PaymentInitiateOut, PaymentWebhookOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.payments.repository import SqlAlchemyPaymentRepository
from app.resources.payments.schemas import InitiateIn
from app.resources.payments.service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_service(db: DbDep) -> PaymentService:
    return PaymentService(SqlAlchemyPaymentRepository(db))


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


@router.post("/chapa/initiate")
async def initiate(body: InitiateIn, user: RequirePatient, svc: PaymentServiceDep) -> PaymentInitiateOut:
    return await svc.initiate(user.id, body)


@router.post("/chapa/webhook")
async def chapa_webhook(
    request: Request,
    svc: PaymentServiceDep,
    chapa_signature: str | None = Header(default=None, alias="Chapa-Signature"),
) -> PaymentWebhookOut:
    body = await request.json()
    return await svc.handle_webhook(body, chapa_signature)
