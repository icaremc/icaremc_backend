from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.v1.schemas import PaymentInitiateOut, PaymentWebhookOut
from app.config import EnvironmentOptions, MySettings
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.persistence.sqlalchemy.models import Appointment, AppSubscription, CareSubscription, DoctorService

router = APIRouter(prefix="/payments", tags=["payments"])


class InitiateIn(BaseModel):
    kind: str  # appointment|app_subscription|care_subscription
    amount: Decimal
    currency: str = "ETB"
    appointment_id: UUID | None = None
    service_id: UUID | None = None
    doctor_id: UUID | None = None
    email: str = "patient@icaremc.app"
    first_name: str = "Patient"
    last_name: str = "User"


@router.post("/chapa/initiate")
async def initiate(body: InitiateIn, user: RequirePatient, db: DbDep) -> PaymentInitiateOut:
    tx_ref = f"icare-{body.kind}-{uuid4().hex[:16]}"
    if body.kind == "appointment" and body.appointment_id:
        appt = (
            await db.execute(
                select(Appointment).where(Appointment.id == body.appointment_id, Appointment.patient_id == user.id)
            )
        ).scalar_one_or_none()
        if appt is None:
            raise HTTPException(404)
        appt.chapa_tx_ref = tx_ref
        await db.flush()

    meta = {
        "kind": body.kind,
        "user_id": str(user.id),
        "appointment_id": str(body.appointment_id) if body.appointment_id else None,
        "service_id": str(body.service_id) if body.service_id else None,
        "doctor_id": str(body.doctor_id) if body.doctor_id else None,
    }

    if not MySettings.CHAPA_SECRET_KEY:
        return PaymentInitiateOut(tx_ref=tx_ref, checkout_url=None, dev=True, meta=meta)

    payload = {
        "amount": str(body.amount),
        "currency": body.currency,
        "email": body.email,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "tx_ref": tx_ref,
        "meta": meta,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MySettings.CHAPA_BASE_URL}/transaction/initialize",
            json=payload,
            headers={"Authorization": f"Bearer {MySettings.CHAPA_SECRET_KEY}"},
        )
        data = resp.json()
    return PaymentInitiateOut(tx_ref=tx_ref, chapa=data)


@router.post("/chapa/webhook")
async def chapa_webhook(
    request: Request,
    db: DbDep,
    chapa_signature: str | None = Header(default=None, alias="Chapa-Signature"),
) -> PaymentWebhookOut:
    body = await request.json()
    # Require signature whenever Chapa is configured or not in local DEVELOPMENT
    if MySettings.CHAPA_WEBHOOK_SECRET:
        if chapa_signature != MySettings.CHAPA_WEBHOOK_SECRET:
            raise HTTPException(401, "Bad signature")
    elif MySettings.CHAPA_SECRET_KEY or MySettings.ENVIRONMENT != EnvironmentOptions.DEVELOPMENT:
        raise HTTPException(401, "Webhook secret required")

    tx_ref = body.get("tx_ref") or body.get("data", {}).get("tx_ref")
    status = body.get("status") or body.get("data", {}).get("status")
    if status not in ("success", "successful"):
        return PaymentWebhookOut(ignored=True)
    if not tx_ref:
        raise HTTPException(400, "Missing tx_ref")

    appt = (await db.execute(select(Appointment).where(Appointment.chapa_tx_ref == tx_ref))).scalar_one_or_none()
    if appt:
        if appt.payment_status == "paid":
            return PaymentWebhookOut(type="appointment", idempotent=True)
        amount = Decimal(str(body.get("amount") or body.get("data", {}).get("amount") or appt.prepayment_amount or 0))
        appt.amount_paid = amount
        appt.payment_status = "paid"
        appt.payment_method = "chapa"
        await db.flush()
        return PaymentWebhookOut(type="appointment")

    existing_sub = (
        await db.execute(select(AppSubscription).where(AppSubscription.chapa_tx_ref == tx_ref))
    ).scalar_one_or_none()
    if existing_sub:
        return PaymentWebhookOut(type="app_subscription", idempotent=True)

    existing_care = (
        await db.execute(select(CareSubscription).where(CareSubscription.chapa_tx_ref == tx_ref))
    ).scalar_one_or_none()
    if existing_care:
        return PaymentWebhookOut(type="care_subscription", idempotent=True)

    meta = body.get("meta") or body.get("data", {}).get("meta") or {}
    kind = meta.get("kind")
    user_id = meta.get("user_id")
    if kind == "app_subscription" and user_id:
        now = datetime.now(UTC)
        db.add(
            AppSubscription(
                patient_id=UUID(user_id),
                plan="yearly",
                status="active",
                starts_at=now,
                ends_at=now + timedelta(days=365),
                amount_paid=Decimal(str(body.get("amount") or 0)),
                payment_method="chapa",
                chapa_tx_ref=tx_ref,
            )
        )
        await db.flush()
        return PaymentWebhookOut(type="app_subscription")

    if kind == "care_subscription" and user_id and meta.get("service_id") and meta.get("doctor_id"):
        service = (
            await db.execute(select(DoctorService).where(DoctorService.id == UUID(meta["service_id"])))
        ).scalar_one()
        now = datetime.now(UTC)
        db.add(
            CareSubscription(
                patient_id=UUID(user_id),
                doctor_id=UUID(meta["doctor_id"]),
                service_id=service.id,
                status="active",
                starts_at=now,
                ends_at=now + timedelta(days=30),
                visits_allowed=service.visits_per_period,
                amount_paid=Decimal(str(body.get("amount") or service.price)),
                payment_method="chapa",
                chapa_tx_ref=tx_ref,
            )
        )
        await db.flush()
        return PaymentWebhookOut(type="care_subscription")

    return PaymentWebhookOut(unmatched=True)
