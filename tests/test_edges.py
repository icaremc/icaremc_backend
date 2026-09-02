from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.config import MySettings
from app.core.security.tokens import hash_password
from app.core.services.booking_finance import cancel_appointment, credit_doctor_on_complete
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import (
    Appointment,
    DoctorProfile,
    DoctorWallet,
    PatientWallet,
    Profile,
    User,
)
from tests.conftest import auth_header
from tests.payment_helpers import pay_appointment


def _verify_doctor(client, admin_token: str, doctor_id: str) -> None:
    client.post(
        f"/api/v1/admin/doctors/{doctor_id}/verify",
        headers=auth_header(admin_token),
        json={"is_verified": True},
    )


def test_book_ignores_client_amount_paid(client, patient_auth, doctor_auth, admin_auth):
    _verify_doctor(client, admin_auth["token"], doctor_auth["user_id"])
    service = client.post(
        "/api/v1/doctor/services",
        headers=auth_header(doctor_auth["token"]),
        json={"name": "IgnorePay", "price": "400.00"},
    ).json()
    book = client.post(
        "/api/v1/appointments",
        headers=auth_header(patient_auth["token"]),
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=5)),
            "time_slot": "09:30",
            "service_id": service["id"],
            "amount_paid": "99999.00",
            "chapa_tx_ref": "fake-paid",
            "payment_method": "cash",
        },
    )
    assert book.status_code == 200, book.text
    body = book.json()
    assert Decimal(str(body["amount_paid"])) == Decimal("0")
    assert body["payment_status"] in ("unpaid", "waived")
    assert body.get("chapa_tx_ref") in (None, "")


def test_webhook_rejects_bad_signature_when_configured(client, patient_auth, monkeypatch):
    monkeypatch.setattr(MySettings, "CHAPA_SECRET_KEY", "CHASECK_TEST-x")
    monkeypatch.setattr(MySettings, "CHAPA_WEBHOOK_SECRET", "whsec-test")
    bad = client.post(
        "/api/v1/payments/chapa/webhook",
        json={"tx_ref": "x", "status": "success", "amount": "1"},
    )
    assert bad.status_code == 401
    ok = client.post(
        "/api/v1/payments/chapa/webhook",
        headers={"Chapa-Signature": "whsec-test"},
        json={
            "tx_ref": f"icare-sig-{uuid4().hex[:8]}",
            "status": "success",
            "amount": "1",
            "meta": {"kind": "app_subscription", "user_id": patient_auth["user_id"]},
        },
    )
    assert ok.status_code == 200


def test_dual_role_wrong_password_rejected(client, unique_phone):
    phone = unique_phone("95")
    potp = client.post("/api/v1/auth/patient/otp", json={"phone": phone}).json()["dev_code"]
    assert (
        client.post(
            "/api/v1/auth/patient/signup",
            json={"phone": phone, "password": "secret12", "otp": potp, "full_name": "Dual"},
        ).status_code
        == 200
    )
    dotp = client.post("/api/v1/auth/doctor/otp", json={"phone": phone}).json()["dev_code"]
    bad = client.post(
        "/api/v1/auth/doctor/signup",
        json={
            "phone": phone,
            "password": "other-password",
            "otp": dotp,
            "first_name": "X",
            "last_name": "Y",
        },
    )
    assert bad.status_code == 400
    assert "password" in bad.json()["detail"].lower()


def test_double_book_same_slot_conflict(client, patient_auth, doctor_auth, admin_auth, unique_phone):
    _verify_doctor(client, admin_auth["token"], doctor_auth["user_id"])
    service = client.post(
        "/api/v1/doctor/services",
        headers=auth_header(doctor_auth["token"]),
        json={"name": "Slot", "price": "100.00"},
    ).json()
    day = str(date.today() + timedelta(days=6))
    payload = {
        "doctor_id": doctor_auth["user_id"],
        "appointment_date": day,
        "time_slot": "16:00",
        "service_id": service["id"],
    }
    first = client.post("/api/v1/appointments", headers=auth_header(patient_auth["token"]), json=payload)
    assert first.status_code == 200, first.text

    phone = unique_phone("96")
    otp = client.post("/api/v1/auth/patient/otp", json={"phone": phone}).json()["dev_code"]
    other = client.post(
        "/api/v1/auth/patient/signup",
        json={"phone": phone, "password": "secret12", "otp": otp, "full_name": "Other"},
    ).json()
    second = client.post(
        "/api/v1/appointments",
        headers=auth_header(other["access_token"]),
        json=payload,
    )
    assert second.status_code == 409


def test_care_subscription_initiate_and_webhook(client, patient_auth, doctor_auth, admin_auth):
    _verify_doctor(client, admin_auth["token"], doctor_auth["user_id"])
    service = client.post(
        "/api/v1/doctor/services",
        headers=auth_header(doctor_auth["token"]),
        json={"name": "CarePlan", "price": "1200.00", "visits_per_period": 4},
    ).json()
    init = client.post(
        "/api/v1/payments/chapa/initiate",
        headers=auth_header(patient_auth["token"]),
        json={
            "kind": "care_subscription",
            "amount": "1200.00",
            "service_id": service["id"],
            "doctor_id": doctor_auth["user_id"],
        },
    )
    assert init.status_code == 200, init.text
    body = init.json()
    assert body["dev"] is True
    meta = body["meta"]
    webhook = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": body["tx_ref"],
            "status": "success",
            "amount": "1200.00",
            "meta": meta,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json().get("type") == "care_subscription"
    listed = client.get("/api/v1/subscriptions/care", headers=auth_header(patient_auth["token"]))
    assert listed.status_code == 200
    assert any(s["service_id"] == service["id"] for s in listed.json())


def test_doctor_cancel_after_complete_refunds(client, patient_auth, doctor_auth, admin_auth):
    _verify_doctor(client, admin_auth["token"], doctor_auth["user_id"])
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "CancelMe", "price": "150.00"},
    ).json()
    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=7)),
            "time_slot": "11:30",
            "service_id": service["id"],
        },
    ).json()
    pay_appointment(client, patient_auth["token"], appt["id"], "150.00")
    assert (
        client.post(
            f"/api/v1/doctor/appointments/{appt['id']}/status",
            headers=doctor_h,
            json={"status": "completed"},
        ).status_code
        == 200
    )
    cancelled = client.post(
        f"/api/v1/doctor/appointments/{appt['id']}/status",
        headers=doctor_h,
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200, cancelled.text
    wallet = client.get("/api/v1/wallet", headers=patient_h).json()["wallet"]
    assert Decimal(str(wallet["balance"])) >= Decimal("150")


def test_doctor_cancel_completed_without_balance_fails(client):
    import asyncio

    async def _run() -> None:
        async with async_session_factory() as db:
            patient = User(
                phone=f"p-{uuid4().hex[:10]}",
                password_hash=hash_password("x"),
                role="patient",
                roles=["patient"],
            )
            doctor = User(
                phone=f"d-{uuid4().hex[:10]}",
                password_hash=hash_password("x"),
                role="doctor",
                roles=["doctor"],
            )
            db.add_all([patient, doctor])
            await db.flush()
            db.add(Profile(id=patient.id, full_name="P", phone=patient.phone))
            db.add(
                DoctorProfile(
                    id=doctor.id,
                    first_name="D",
                    last_name="R",
                    specialty="G",
                    hospital="",
                    referral_code=f"T{uuid4().hex[:6].upper()}",
                )
            )
            await db.flush()
            db.add(PatientWallet(patient_id=patient.id, balance=Decimal("0")))
            db.add(DoctorWallet(doctor_id=doctor.id, available_balance=Decimal("0")))
            appt = Appointment(
                doctor_id=doctor.id,
                patient_id=patient.id,
                appointment_date=date.today() + timedelta(days=1),
                time_slot="08:00",
                status="confirmed",
                total_amount=Decimal("50"),
                amount_paid=Decimal("50"),
                payment_status="paid",
            )
            db.add(appt)
            await db.flush()
            await credit_doctor_on_complete(db, appt)
            wallet = await db.get(DoctorWallet, doctor.id)
            assert wallet is not None
            wallet.available_balance = Decimal("0")
            await db.flush()
            try:
                await cancel_appointment(db, appt, cancelled_by="doctor")
                raise AssertionError("expected ValueError")
            except ValueError as exc:
                assert "Insufficient" in str(exc)
            await db.rollback()

    asyncio.run(_run())


def test_push_creates_notification_without_fcm(client, patient_auth, admin_auth):
    payload = {
        "user_id": patient_auth["user_id"],
        "title": "EdgePush",
        "body": "stored even if FCM skipped",
        "type": "test",
    }
    res = client.post("/api/v1/push/notify", json=payload, headers=auth_header(admin_auth["token"]))
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["fcm"].get("skipped") is True
    notes = client.get("/api/v1/notifications", headers=auth_header(patient_auth["token"]))
    assert any(n["title"] == "EdgePush" for n in notes.json())
