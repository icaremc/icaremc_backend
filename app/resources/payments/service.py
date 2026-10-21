from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

import httpx

from app.api.v1.schemas import PaymentInitiateOut, PaymentWebhookOut
from app.config import EnvironmentOptions, MySettings
from app.persistence.sqlalchemy.models import (
    AppSubscription,
    CareProfilePayment,
    CareSubscription,
    ChildPayment,
)
from app.resources.errors import not_found, unauthorized, bad_request
from app.resources.payments.repository import PaymentRepository
from app.resources.payments.schemas import (
    ChildPaymentStatusOut,
    InitiateIn,
    PregnancyPaymentStatusOut,
)
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

        if (body.kind in ("child_registration", "child")) and body.child_id:
            child = await self._repo.get_child(body.child_id, user_id)
            if child is None:
                raise not_found("Child not found")
            if child.payment_status == "paid":
                raise bad_request("Child profile is already activated")
            child.payment_tx_ref = tx_ref
            self._repo.add(
                CareProfilePayment(
                    user_id=user_id,
                    payment_type="child",
                    child_id=child.id,
                    amount=body.amount,
                    currency=body.currency,
                    status="pending",
                    tx_ref=tx_ref,
                    payment_method="chapa",
                )
            )
            await self._repo.flush()

        if (body.kind in ("pregnancy_registration", "pregnancy")) and body.pregnancy_id:
            pregnancy = await self._repo.get_pregnancy(body.pregnancy_id, user_id)
            if pregnancy is None:
                raise not_found("Pregnancy not found")
            if pregnancy.payment_status == "paid":
                raise bad_request("Pregnancy profile is already activated")
            pregnancy.payment_tx_ref = tx_ref
            self._repo.add(
                CareProfilePayment(
                    user_id=user_id,
                    payment_type="pregnancy",
                    pregnancy_id=pregnancy.id,
                    amount=body.amount,
                    currency=body.currency,
                    status="pending",
                    tx_ref=tx_ref,
                    payment_method="chapa",
                )
            )
            await self._repo.flush()

        meta = {
            "kind": body.kind,
            "user_id": str(user_id),
            "appointment_id": str(body.appointment_id) if body.appointment_id else None,
            "service_id": str(body.service_id) if body.service_id else None,
            "doctor_id": str(body.doctor_id) if body.doctor_id else None,
            "child_id": str(body.child_id) if body.child_id else None,
            "pregnancy_id": str(body.pregnancy_id) if body.pregnancy_id else None,
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

    async def get_banks(self) -> dict[str, Any]:
        return await fetch_chapa_banks()

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

    def _verify_transfer_approval_signature(
        self, raw_body: bytes, body: Mapping[str, Any], chapa_signature: str | None
    ) -> None:
        import hashlib
        import hmac
        import json

        secret = (MySettings.CHAPA_TRANSFER_APPROVAL_SECRET or MySettings.CHAPA_WEBHOOK_SECRET).strip()
        if not secret:
            return

        # If Chapa sends an empty ping or setup check when saving the URL in the dashboard
        if not raw_body or body.get("event") == "ping" or body.get("type") == "test":
            return

        if not chapa_signature:
            raise unauthorized("Missing approval signature")

        sig = chapa_signature.strip()
        if sig.lower().startswith("bearer "):
            sig = sig[7:].strip()

        # 1. Direct secret match
        if sig == secret:
            return

        # 2. HMAC(key=secret, msg=secret) — Chapa's actual signing scheme for transfer approvals:
        #    they do NOT hash the body; instead they sign the secret string with itself.
        expected_self = hmac.new(secret.encode(), secret.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected_self):
            return

        # 3. HMAC over raw request bytes
        expected_raw = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected_raw):
            return

        # 4. HMAC over compact JSON
        expected_compact = None
        try:
            compact_json = json.dumps(body, separators=(",", ":")).encode("utf-8")
            expected_compact = hmac.new(secret.encode(), compact_json, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_compact):
                return
        except Exception:
            pass

        # 5. HMAC over standard JSON
        expected_std = None
        try:
            standard_json = json.dumps(body).encode("utf-8")
            expected_std = hmac.new(secret.encode(), standard_json, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig, expected_std):
                return
        except Exception:
            pass
            
        raise unauthorized("Bad approval signature")

    async def handle_transfer_approval(
        self, raw_body: bytes, body: Mapping[str, Any], chapa_signature: str | None
    ) -> dict[str, Any]:
        self._verify_transfer_approval_signature(raw_body, body, chapa_signature)
        reference = body.get("reference")
        if reference:
            payout = await self._repo.find_payout_by_reference(str(reference))
            if payout is not None:
                payout.status = "completed"
                payout.payment_date = datetime.now(UTC)
                await self._repo.flush()

                patient_id = getattr(payout, "patient_id", None)
                if patient_id:
                    await dispatch_notification(
                        db=self._repo.session,
                        user_id=patient_id,
                        title="Withdrawal Completed",
                        body=f"Your withdrawal request of {payout.amount} ETB has been completed.",
                        type="patient_withdrawal",
                        data={
                            "type": "withdrawal",
                            "screen": "patient_wallet",
                            "route": "/wallet",
                            "resource_id": str(payout.id),
                        },
                        is_urgent=True,
                    )
                doctor_id = getattr(payout, "doctor_id", None)
                if doctor_id:
                    await dispatch_notification(
                        db=self._repo.session,
                        user_id=doctor_id,
                        title="Payout Completed",
                        body=f"Your payout request of {payout.amount} ETB has been completed.",
                        type="doctor_payout",
                        data={
                            "type": "payout",
                            "screen": "doctor_wallet",
                            "route": "/doctor/wallet",
                            "resource_id": str(payout.id),
                        },
                        is_urgent=True,
                    )
        return {"status": "approved", "message": "Transfer approved"}

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
        care_payment = await self._repo.get_care_payment_by_tx(tx_ref)
        if care_payment and care_payment.status == "success":
            out_type = "pregnancy_registration" if (care_payment.payment_type == "pregnancy" or care_payment.pregnancy_id) else "child_registration"
            return PaymentWebhookOut(type=out_type, idempotent=True)

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

        is_pregnancy = (kind in ("pregnancy_registration", "pregnancy")) or (
            care_payment is not None and (care_payment.payment_type == "pregnancy" or care_payment.pregnancy_id is not None)
        )
        is_child = (kind in ("child_registration", "child")) or (
            care_payment is not None and (care_payment.payment_type == "child" or care_payment.child_id is not None)
        )

        if is_pregnancy:
            now = datetime.now(UTC)
            amount = Decimal(
                str(
                    body.get("amount")
                    or body.get("data", {}).get("amount")
                    or (care_payment.amount if care_payment else 0)
                )
            )
            pregnancy_id = (care_payment.pregnancy_id if care_payment else None) or (
                UUID(meta["pregnancy_id"]) if meta.get("pregnancy_id") else None
            )
            target_user_id = (care_payment.user_id if care_payment else None) or (
                UUID(user_id) if user_id else None
            )

            pregnancy = await self._repo.get_pregnancy_by_id(pregnancy_id) if pregnancy_id else None
            if pregnancy:
                pregnancy.payment_status = "paid"
                pregnancy.amount_paid = amount
                pregnancy.payment_method = "chapa"
                pregnancy.payment_tx_ref = tx_ref
                pregnancy.paid_at = now

            chapa_ref = str(body.get("reference") or body.get("data", {}).get("reference") or "")
            if care_payment:
                care_payment.status = "success"
                care_payment.completed_at = now
                if chapa_ref:
                    care_payment.chapa_reference = chapa_ref
                care_payment.raw_payload = dict(body)
            elif target_user_id and pregnancy_id:
                self._repo.add(
                    CareProfilePayment(
                        user_id=target_user_id,
                        payment_type="pregnancy",
                        pregnancy_id=pregnancy_id,
                        amount=amount,
                        status="success",
                        tx_ref=tx_ref,
                        chapa_reference=chapa_ref,
                        payment_method="chapa",
                        raw_payload=dict(body),
                        completed_at=now,
                    )
                )
            await self._repo.flush()

            # Push notification to Patient
            if target_user_id:
                await dispatch_notification(
                    db=self._repo.session,
                    user_id=target_user_id,
                    title="Pregnancy Profile Activated",
                    body="Payment received! Your pregnancy profile is now active.",
                    type="pregnancy_payment_confirmed",
                    data={
                        "type": "pregnancy",
                        "screen": "pregnancy_detail",
                        "route": f"/pregnancies/{pregnancy_id}" if pregnancy_id else "/pregnancies",
                        "resource_id": str(pregnancy_id) if pregnancy_id else None,
                        "pregnancy_id": str(pregnancy_id) if pregnancy_id else None,
                    },
                    is_urgent=True,
                )

            return PaymentWebhookOut(type="pregnancy_registration")

        if is_child:
            now = datetime.now(UTC)
            amount = Decimal(
                str(
                    body.get("amount")
                    or body.get("data", {}).get("amount")
                    or (care_payment.amount if care_payment else 0)
                )
            )
            child_id = (care_payment.child_id if care_payment else None) or (
                UUID(meta["child_id"]) if meta.get("child_id") else None
            )
            target_user_id = (care_payment.user_id if care_payment else None) or (
                UUID(user_id) if user_id else None
            )

            child = await self._repo.get_child_by_id(child_id) if child_id else None
            if child:
                child.payment_status = "paid"
                child.amount_paid = amount
                child.payment_method = "chapa"
                child.payment_tx_ref = tx_ref
                child.paid_at = now

            chapa_ref = str(body.get("reference") or body.get("data", {}).get("reference") or "")
            if care_payment:
                care_payment.status = "success"
                care_payment.completed_at = now
                if chapa_ref:
                    care_payment.chapa_reference = chapa_ref
                care_payment.raw_payload = dict(body)
            elif target_user_id and child_id:
                self._repo.add(
                    CareProfilePayment(
                        user_id=target_user_id,
                        payment_type="child",
                        child_id=child_id,
                        amount=amount,
                        status="success",
                        tx_ref=tx_ref,
                        chapa_reference=chapa_ref,
                        payment_method="chapa",
                        raw_payload=dict(body),
                        completed_at=now,
                    )
                )
            await self._repo.flush()

            # Push notification to Patient
            if target_user_id:
                child_name = getattr(child, "name", "your child") if child else "your child"
                await dispatch_notification(
                    db=self._repo.session,
                    user_id=target_user_id,
                    title="Child Profile Activated",
                    body=f"Payment received! {child_name}'s profile is now active.",
                    type="child_payment_confirmed",
                    data={
                        "type": "child",
                        "screen": "child_detail",
                        "route": f"/children/{child_id}" if child_id else "/children",
                        "resource_id": str(child_id) if child_id else None,
                        "child_id": str(child_id) if child_id else None,
                    },
                    is_urgent=True,
                )

            return PaymentWebhookOut(type="child_registration")

        return PaymentWebhookOut(unmatched=True)

    async def get_child_payment_status(self, child_id: UUID, user_id: UUID) -> ChildPaymentStatusOut:
        child = await self._repo.get_child(child_id, user_id)
        if child is None:
            raise not_found("Child not found")
        return ChildPaymentStatusOut(
            child_id=child.id,
            payment_status=child.payment_status or "unpaid",
            amount_paid=child.amount_paid,
            currency=child.currency or "ETB",
            payment_method=child.payment_method,
            paid_at=child.paid_at.isoformat() if child.paid_at else None,
            tx_ref=child.payment_tx_ref,
        )

    async def get_pregnancy_payment_status(self, pregnancy_id: UUID, user_id: UUID) -> PregnancyPaymentStatusOut:
        pregnancy = await self._repo.get_pregnancy(pregnancy_id, user_id)
        if pregnancy is None:
            raise not_found("Pregnancy not found")
        return PregnancyPaymentStatusOut(
            pregnancy_id=pregnancy.id,
            payment_status=pregnancy.payment_status or "unpaid",
            amount_paid=pregnancy.amount_paid,
            currency=pregnancy.currency or "ETB",
            payment_method=pregnancy.payment_method,
            paid_at=pregnancy.paid_at.isoformat() if pregnancy.paid_at else None,
            tx_ref=pregnancy.payment_tx_ref,
        )

    async def verify_transaction(self, tx_ref: str, user_id: UUID) -> dict[str, Any]:
        care_payment = await self._repo.get_care_payment_by_tx(tx_ref)
        if care_payment:
            if care_payment.user_id != user_id:
                raise not_found()
            if care_payment.status != "success" and MySettings.CHAPA_SECRET_KEY:
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(
                            f"{MySettings.CHAPA_BASE_URL}/transaction/verify/{tx_ref}",
                            headers={"Authorization": f"Bearer {MySettings.CHAPA_SECRET_KEY}"},
                        )
                        if resp.status_code == 200:
                            vdata = resp.json()
                            status_val = vdata.get("status") or (vdata.get("data") or {}).get("status")
                            if status_val in ("success", "successful"):
                                now = datetime.now(UTC)
                                care_payment.status = "success"
                                care_payment.completed_at = now
                                care_payment.raw_payload = vdata
                                if care_payment.payment_type == "pregnancy" or care_payment.pregnancy_id is not None:
                                    pregnancy = await self._repo.get_pregnancy_by_id(care_payment.pregnancy_id)
                                    if pregnancy:
                                        pregnancy.payment_status = "paid"
                                        pregnancy.amount_paid = care_payment.amount
                                        pregnancy.payment_method = "chapa"
                                        pregnancy.payment_tx_ref = tx_ref
                                        pregnancy.paid_at = now
                                else:
                                    child = await self._repo.get_child_by_id(care_payment.child_id)
                                    if child:
                                        child.payment_status = "paid"
                                        child.amount_paid = care_payment.amount
                                        child.payment_method = "chapa"
                                        child.payment_tx_ref = tx_ref
                                        child.paid_at = now
                                await self._repo.flush()
                except Exception:
                    pass
            is_pregnancy = care_payment.payment_type == "pregnancy" or care_payment.pregnancy_id is not None
            res = {
                "ok": True,
                "kind": "pregnancy_registration" if is_pregnancy else "child_registration",
                "tx_ref": tx_ref,
                "status": care_payment.status,
            }
            if is_pregnancy:
                res["pregnancy_id"] = str(care_payment.pregnancy_id)
            else:
                res["child_id"] = str(care_payment.child_id)
            return res

        appt = await self._repo.get_appointment_by_tx(tx_ref)
        if appt and appt.patient_id == user_id:
            return {"ok": True, "kind": "appointment", "tx_ref": tx_ref, "status": appt.payment_status}

        return {"ok": True, "tx_ref": tx_ref, "status": "unknown"}



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


async def fetch_chapa_banks() -> dict[str, Any]:
    """
    Fetches the list of supported banks and bank codes from the Chapa API.
    """
    if not MySettings.CHAPA_SECRET_KEY:
        raise bad_request("Chapa secret key is not configured")

    url = f"{MySettings.CHAPA_BASE_URL.rstrip('/')}/banks"
    headers = {
        "Authorization": f"Bearer {MySettings.CHAPA_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            data = resp.json() if resp.content else {}
            if resp.status_code >= 400 or (
                isinstance(data, dict)
                and data.get("status")
                and data.get("status") not in ("success", "successful")
            ):
                err_msg = (
                    data.get("message")
                    if isinstance(data, dict)
                    else None
                ) or f"Chapa banks request failed with status {resp.status_code}"
                raise bad_request(f"Chapa error: {err_msg}")

            if isinstance(data, dict):
                banks = data.get("data")
                if isinstance(banks, list):
                    for bank in banks:
                        if isinstance(bank, dict):
                            code = bank.get("code") or bank.get("slug") or str(bank.get("id", ""))
                            bank.setdefault("code", code)
                            bank.setdefault("bank_code", code)
                return data

            if isinstance(data, list):
                for bank in data:
                    if isinstance(bank, dict):
                        code = bank.get("code") or bank.get("slug") or str(bank.get("id", ""))
                        bank.setdefault("code", code)
                        bank.setdefault("bank_code", code)
                return {
                    "status": "success",
                    "message": "Banks retrieved",
                    "data": data,
                }

            return {
                "status": "success",
                "message": "Banks retrieved",
                "data": [],
            }
    except httpx.RequestError as exc:
        raise bad_request(f"Chapa network error: {str(exc)}") from exc
