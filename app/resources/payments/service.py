from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Mapping
from uuid import UUID, uuid4

import httpx

from app.api.v1.schemas import PaymentInitiateOut, PaymentWebhookOut
from app.config import EnvironmentOptions, MySettings
from app.persistence.sqlalchemy.models import AppSubscription, CareSubscription
from app.resources.errors import not_found, unauthorized, bad_request
from app.resources.payments.repository import PaymentRepository
from app.resources.payments.schemas import InitiateIn

class PaymentService:
    def __init__(self, repo: PaymentRepository) -> None:
        self._repo = repo

    async def initiate(self, user_id: UUID, body: InitiateIn) -> PaymentInitiateOut:
        tx_ref = f"icare-{body.kind}-{uuid4().hex[:16]}"
        if body.kind == "appointment" and body.appointment_id:
            appt = await self._repo.get_patient_appointment(body.appointment_id, user_id)
            if appt is None:
                raise not_found()
            appt.chapa_tx_ref = tx_ref
            await self._repo.flush()

        meta = {
            "kind": body.kind,
            "user_id": str(user_id),
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

    def _verify_webhook_signature(self, chapa_signature: str | None) -> None:
        if MySettings.CHAPA_WEBHOOK_SECRET:
            if chapa_signature != MySettings.CHAPA_WEBHOOK_SECRET:
                raise unauthorized("Bad signature")
        elif MySettings.CHAPA_SECRET_KEY or MySettings.ENVIRONMENT != EnvironmentOptions.DEVELOPMENT:
            raise unauthorized("Webhook secret required")

    async def handle_webhook(self, body: Mapping[str, object], chapa_signature: str | None) -> PaymentWebhookOut:
        self._verify_webhook_signature(chapa_signature)
        tx_ref = body.get("tx_ref") or body.get("data", {}).get("tx_ref")
        status = body.get("status") or body.get("data", {}).get("status")
        if status not in ("success", "successful"):
            return PaymentWebhookOut(ignored=True)
        if not tx_ref:
            raise bad_request("Missing tx_ref")

        appt = await self._repo.get_appointment_by_tx(tx_ref)
        if appt:
            if appt.payment_status == "paid":
                return PaymentWebhookOut(type="appointment", idempotent=True)
            amount = Decimal(str(body.get("amount") or body.get("data", {}).get("amount") or appt.prepayment_amount or 0))
            appt.amount_paid = amount
            appt.payment_status = "paid"
            appt.payment_method = "chapa"
            await self._repo.flush()
            return PaymentWebhookOut(type="appointment")

        if await self._repo.get_app_sub_by_tx(tx_ref):
            return PaymentWebhookOut(type="app_subscription", idempotent=True)
        if await self._repo.get_care_sub_by_tx(tx_ref):
            return PaymentWebhookOut(type="care_subscription", idempotent=True)

        meta = body.get("meta") or body.get("data", {}).get("meta") or {}
        kind = meta.get("kind")
        user_id = meta.get("user_id")
        if kind == "app_subscription" and user_id:
            now = datetime.now(UTC)
            self._repo.add(
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
            await self._repo.flush()
            return PaymentWebhookOut(type="app_subscription")

        if kind == "care_subscription" and user_id and meta.get("service_id") and meta.get("doctor_id"):
            service = await self._repo.get_service(UUID(meta["service_id"]))
            now = datetime.now(UTC)
            self._repo.add(
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
            await self._repo.flush()
            return PaymentWebhookOut(type="care_subscription")

        return PaymentWebhookOut(unmatched=True)
