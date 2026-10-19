from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

import httpx

from app.api.v1.schemas import PaymentInitiateOut, PaymentWebhookOut
from app.config import EnvironmentOptions, MySettings
from app.persistence.sqlalchemy.models import AppSubscription, CareSubscription
from app.resources.errors import not_found, unauthorized, bad_request
from app.resources.payments.repository import PaymentRepository
from app.resources.payments.schemas import InitiateIn
from app.resources.push.service import dispatch_notification

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
        if body.return_url:
            payload["return_url"] = body.return_url

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{MySettings.CHAPA_BASE_URL}/transaction/initialize",
                json=payload,
                headers={"Authorization": f"Bearer {MySettings.CHAPA_SECRET_KEY}"},
            )
            data = resp.json()
            checkout_url = (data.get("data") or {}).get("checkout_url")
        return PaymentInitiateOut(tx_ref=tx_ref, checkout_url=checkout_url, chapa=data)

    async def execute_transfer(
        self,
        *,
        account_name: str,
        account_number: str,
        amount: Decimal,
        currency: str = "ETB",
        bank_code: str | None = None,
        reference: str,
    ) -> dict[str, Any]:
        return await execute_chapa_transfer(
            account_name=account_name,
            account_number=account_number,
            amount=amount,
            currency=currency,
            bank_code=bank_code,
            reference=reference,
        )

    def _verify_webhook_signature(self, raw_body: bytes, chapa_signature: str | None) -> None:
        import hmac
        import hashlib
        if MySettings.CHAPA_WEBHOOK_SECRET:
            if not chapa_signature:
                raise unauthorized("Missing signature")
            expected_hash = hmac.new(
                MySettings.CHAPA_WEBHOOK_SECRET.encode(),
                raw_body,
                hashlib.sha256
            ).hexdigest()
            if chapa_signature != expected_hash and chapa_signature != MySettings.CHAPA_WEBHOOK_SECRET:
                raise unauthorized("Bad signature")
        # elif MySettings.CHAPA_SECRET_KEY or MySettings.ENVIRONMENT != EnvironmentOptions.DEVELOPMENT:
        #     raise unauthorized("Webhook secret required")

    async def handle_webhook(self, raw_body: bytes, body: Mapping[str, object], chapa_signature: str | None) -> PaymentWebhookOut:
        self._verify_webhook_signature(raw_body, chapa_signature)
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

            # Push notification to Patient
            await dispatch_notification(
                db=self._repo.session,
                user_id=appt.patient_id,
                title="Payment Confirmed",
                body=f"Prepayment of {amount} ETB received for your appointment on {appt.appointment_date}.",
                type="payment_confirmed",
                data={
                    "type": "payment",
                    "screen": "appointment_detail",
                    "route": f"/appointments/{appt.id}",
                    "resource_id": str(appt.id),
                    "appointment_id": str(appt.id),
                },
                is_urgent=True,
            )

            # Push notification to Doctor
            patient_name = appt.patient_name or "A patient"
            await dispatch_notification(
                db=self._repo.session,
                user_id=appt.doctor_id,
                title="Appointment Payment Received",
                body=f"{patient_name} completed payment of {amount} ETB for {appt.appointment_date} at {appt.time_slot}.",
                type="appointment_paid",
                data={
                    "type": "appointment",
                    "screen": "doctor_appointment_detail",
                    "route": f"/doctor/appointments/{appt.id}",
                    "resource_id": str(appt.id),
                    "appointment_id": str(appt.id),
                },
                is_urgent=True,
            )

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

            # Push notification to Patient
            await dispatch_notification(
                db=self._repo.session,
                user_id=UUID(user_id),
                title="Subscription Active",
                body="Your iCare app subscription is now active. Enjoy full premium care features!",
                type="subscription_active",
                data={
                    "type": "subscription",
                    "screen": "subscriptions",
                    "route": "/subscriptions",
                    "resource_id": str(user_id),
                },
                is_urgent=True,
            )

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

            # Push notification to Patient
            svc_name = getattr(service, "name", "Care")
            await dispatch_notification(
                db=self._repo.session,
                user_id=UUID(user_id),
                title="Care Plan Active",
                body=f"Your {svc_name} care plan has been activated.",
                type="care_subscription_active",
                data={
                    "type": "care_subscription",
                    "screen": "care_subscription_detail",
                    "route": "/subscriptions/care",
                    "resource_id": str(meta.get("service_id")),
                },
                is_urgent=True,
            )

            # Push notification to Doctor
            await dispatch_notification(
                db=self._repo.session,
                user_id=UUID(meta["doctor_id"]),
                title="New Care Subscription",
                body=f"A patient has enrolled in your {svc_name} care program.",
                type="doctor_care_subscription_new",
                data={
                    "type": "care_subscription",
                    "screen": "doctor_care_subscriptions",
                    "route": "/doctor/care-subscriptions",
                    "resource_id": str(meta.get("service_id")),
                },
                is_urgent=True,
            )

            return PaymentWebhookOut(type="care_subscription")

        return PaymentWebhookOut(unmatched=True)


async def execute_chapa_transfer(
    *,
    account_name: str,
    account_number: str,
    amount: Decimal,
    currency: str = "ETB",
    bank_code: str | None = None,
    reference: str,
) -> dict[str, Any]:
    """
    Executes a transfer/disbursement to a bank or Telebirr account using Chapa's Transfers API.
    If CHAPA_SECRET_KEY is empty (e.g. testing / development), simulates a successful transfer.
    """
    code = bank_code or "telebirr"

    payload: dict[str, Any] = {
        "account_name": account_name,
        "account_number": str(account_number),
        "amount": str(amount),
        "currency": currency,
        "reference": reference,
        "bank_code": code,
    }

    if not MySettings.CHAPA_SECRET_KEY:
        return {
            "status": "success",
            "message": "Transfer queued successfully (simulated)",
            "data": {
                "reference": reference,
                "status": "success",
                "simulated": True,
            },
        }

    url = f"{MySettings.CHAPA_BASE_URL.rstrip('/')}/transfers"
    headers = {
        "Authorization": f"Bearer {MySettings.CHAPA_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400 or data.get("status") not in ("success", "successful"):
                err_msg = data.get("message") or f"Chapa transfer failed with status {resp.status_code}"
                raise bad_request(f"Chapa transfer error: {err_msg}")
            return data
    except httpx.RequestError as exc:
        raise bad_request(f"Chapa network error: {str(exc)}") from exc
