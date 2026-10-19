from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request

from app.api.v1.schemas import ChapaBanksOut, PaymentInitiateOut, PaymentWebhookOut
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
) -> PaymentWebhookOut:
    sig = request.headers.get("x-chapa-signature") or request.headers.get("chapa-signature")
    raw_body = await request.body()
    body = await request.json()
    return await svc.handle_webhook(raw_body, body, sig)


@router.get("/chapa/banks")
@router.get("/banks")
async def get_banks(svc: PaymentServiceDep) -> ChapaBanksOut:
    return await svc.get_banks()


@router.get("/chapa/transfer-approval")
@router.get("/transfer-approval")
async def chapa_transfer_approval_get() -> dict[str, str]:
    return {"status": "ok", "message": "Transfer approval endpoint active"}


@router.post("/chapa/transfer-approval")
@router.post("/transfer-approval")
async def chapa_transfer_approval(
    request: Request,
    svc: PaymentServiceDep,
) -> dict[str, Any]:
    sig = (
        request.headers.get("chapa-signature")
        or request.headers.get("x-chapa-signature")
        or request.headers.get("x-chapa-secret")
        or request.headers.get("authorization")
    )
    raw_body = await request.body()
    try:
        body = await request.json() if raw_body else {}
    except Exception:
        body = {}
    return await svc.handle_transfer_approval(raw_body, body, sig)
