from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MySettings
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import get_db
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
async def initiate(body: InitiateIn, user: RequirePatient, db: AsyncSession = Depends(get_db)):
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

    if not MySettings.CHAPA_SECRET_KEY:
        return {"ok": True, "tx_ref": tx_ref, "checkout_url": None, "dev": True}

    payload = {
        "amount": str(body.amount),
        "currency": body.currency,
        "email": body.email,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "tx_ref": tx_ref,
        "meta": {"kind": body.kind, "user_id": str(user.id)},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MySettings.CHAPA_BASE_URL}/transaction/initialize",
            json=payload,
            headers={"Authorization": f"Bearer {MySettings.CHAPA_SECRET_KEY}"},
        )
        data = resp.json()
    return {"ok": True, "tx_ref": tx_ref, "chapa": data}


@router.post("/chapa/webhook")
async def chapa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    chapa_signature: str | None = Header(default=None, alias="Chapa-Signature"),
):
    # ponytail: verify signature when CHAPA_WEBHOOK_SECRET set
    body = await request.json()
    if MySettings.CHAPA_WEBHOOK_SECRET and chapa_signature != MySettings.CHAPA_WEBHOOK_SECRET:
        raise HTTPException(401, "Bad signature")

    tx_ref = body.get("tx_ref") or body.get("data", {}).get("tx_ref")
    status = body.get("status") or body.get("data", {}).get("status")
    if status not in ("success", "successful"):
        return {"ok": True, "ignored": True}

    appt = (await db.execute(select(Appointment).where(Appointment.chapa_tx_ref == tx_ref))).scalar_one_or_none()
    if appt:
        amount = Decimal(str(body.get("amount") or body.get("data", {}).get("amount") or appt.prepayment_amount or 0))
        appt.amount_paid = amount
        appt.payment_status = "paid"
        appt.payment_method = "chapa"
        await db.flush()
        return {"ok": True, "type": "appointment"}

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
        return {"ok": True, "type": "app_subscription"}

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
        return {"ok": True, "type": "care_subscription"}

    return {"ok": True, "unmatched": True}
