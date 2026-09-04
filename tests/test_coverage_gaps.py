"""Coverage for previously thin/missing routes and local vendor skip paths."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import asyncio

from app.jobs.reminders import run_followup_reminders, run_vaccine_reminders
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import (
    AdminDocument,
    ChildFollowupVisit,
    ChildFollowupVisitTemplate,
    ChildVaccineRecord,
    PatientWallet,
    VaccineDoseSchedule,
)
from app.resources.push.fcm import send_fcm
from tests.conftest import auth_header
from tests.payment_helpers import pay_appointment


def test_wallet_withdraw(client, patient_auth):
    h = auth_header(patient_auth["token"])
    uid = UUID(patient_auth["user_id"])

    async def _seed() -> None:
        async with async_session_factory() as db:
            wallet = await db.get(PatientWallet, uid)
            if wallet is None:
                db.add(PatientWallet(patient_id=uid, balance=Decimal("150.00")))
            else:
                wallet.balance = Decimal("150.00")
            await db.commit()

    asyncio.run(_seed())

    bad = client.post("/api/v1/wallet/withdraw", headers=h, json={"amount": "999.00"})
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/wallet/withdraw",
        headers=h,
        json={"amount": "50.00", "note": "cash out"},
    )
    assert ok.status_code == 200
    assert Decimal(ok.json()["amount"]) == Decimal("50.00")


def test_notification_mark_read(client, patient_auth, admin_auth):
    patient_h = auth_header(patient_auth["token"])
    admin_h = auth_header(admin_auth["token"])
    client.post(
        "/api/v1/push/notify",
        headers=admin_h,
        json={
            "user_id": patient_auth["user_id"],
            "title": "ReadMe",
            "body": "please read",
            "type": "test",
        },
    )
    notes = client.get("/api/v1/notifications", headers=patient_h).json()
    note = next(n for n in notes if n["title"] == "ReadMe")
    assert note.get("read_at") is None

    read = client.post(f"/api/v1/notifications/{note['id']}/read", headers=patient_h)
    assert read.status_code == 200
    assert read.json()["read_at"] is not None


def test_doctor_patch_service_delete_slot_affiliate_version_reviews_payouts(
    client, patient_auth, doctor_auth, admin_auth
):
    admin_h = auth_header(admin_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])

    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )

    version = client.get("/api/v1/doctor/settings/version")
    assert version.status_code == 200
    assert isinstance(version.json(), dict)

    hospital = client.post(
        "/api/v1/admin/hospitals",
        headers=admin_h,
        json={"name": "Affiliate Hosp", "slug": "aff-hosp", "is_active": True},
    ).json()
    aff = client.post(
        f"/api/v1/doctor/hospitals/{hospital['id']}/affiliate",
        headers=doctor_h,
        params={"is_primary": True},
    )
    assert aff.status_code == 200
    assert aff.json()["hospital_id"] == hospital["id"]

    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "ANC", "price": "400.00", "duration_minutes": 20},
    ).json()
    patched = client.patch(
        f"/api/v1/doctor/services/{service['id']}",
        headers=doctor_h,
        json={"name": "ANC Plus", "price": "450.00", "duration_minutes": 25},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "ANC Plus"
    assert Decimal(patched.json()["price"]) == Decimal("450.00")

    slot = client.post(
        "/api/v1/doctor/slots",
        headers=doctor_h,
        json={
            "day_of_week": 2,
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "slot_duration_minutes": 30,
        },
    ).json()
    deleted = client.delete(f"/api/v1/doctor/slots/{slot['id']}", headers=doctor_h)
    assert deleted.status_code == 200

    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=2)),
            "time_slot": "10:30",
            "service_id": service["id"],
        },
    ).json()
    pay_appointment(client, patient_auth["token"], appt["id"], "450.00")
    client.post(
        f"/api/v1/doctor/appointments/{appt['id']}/status",
        headers=doctor_h,
        json={"status": "completed"},
    )

    review = client.post(
        "/api/v1/reviews",
        headers=patient_h,
        json={"appointment_id": appt["id"], "rating": "5", "comment": "great"},
    )
    assert review.status_code == 200
    reviews = client.get("/api/v1/doctor/reviews", headers=doctor_h)
    assert reviews.status_code == 200
    assert any(r["appointment_id"] == appt["id"] for r in reviews.json())

    method = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={
            "holder_name": "Doc Tor",
            "account_number": "1000999888",
            "bank_name": "CBE",
            "is_default": True,
        },
    ).json()
    payout = client.post(
        "/api/v1/doctor/payouts",
        headers=doctor_h,
        json={"amount": "100.00", "payout_method_id": method["id"]},
    )
    assert payout.status_code == 200
    listed = client.get("/api/v1/doctor/payouts", headers=doctor_h)
    assert listed.status_code == 200
    assert any(p["id"] == payout.json()["id"] for p in listed.json())


def test_admin_document_deliver(client, admin_auth, doctor_auth):
    admin_h = auth_header(admin_auth["token"])
    doc_id = uuid4()

    async def _seed() -> None:
        async with async_session_factory() as db:
            db.add(
                AdminDocument(
                    id=doc_id,
                    title="Guide",
                    storage_path="/docs/guide.pdf",
                    file_name="guide.pdf",
                    uploaded_by=UUID(admin_auth["user_id"]),
                )
            )
            await db.commit()

    asyncio.run(_seed())

    listed = client.get("/api/v1/admin/documents", headers=admin_h)
    assert listed.status_code == 200
    assert any(d["id"] == str(doc_id) for d in listed.json())

    delivered = client.post(
        f"/api/v1/admin/documents/{doc_id}/deliver",
        headers=admin_h,
        params={"recipient_id": doctor_auth["user_id"]},
    )
    assert delivered.status_code == 200
    assert delivered.json()["document_id"] == str(doc_id)
    assert delivered.json()["recipient_id"] == doctor_auth["user_id"]


def test_send_fcm_skips_without_key():
    result = asyncio.run(send_fcm("token", "t", "b", {"k": 1}))
    assert result == {"ok": False, "skipped": True}


def test_sms_otp_dev_path_returns_code(client, unique_phone):
    phone = unique_phone("93")
    otp = client.post("/api/v1/auth/patient/otp", json={"phone": phone})
    assert otp.status_code == 200
    body = otp.json()
    assert body["ok"] is True
    assert body["dev_code"] == "123456"


def test_chapa_dev_initiate_without_secret(client, patient_auth, doctor_auth, admin_auth):
    admin_h = auth_header(admin_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])
    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "PayDev", "price": "200.00"},
    ).json()
    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=4)),
            "time_slot": "15:00",
            "service_id": service["id"],
        },
    ).json()
    init = client.post(
        "/api/v1/payments/chapa/initiate",
        headers=patient_h,
        json={
            "kind": "appointment",
            "amount": "200.00",
            "appointment_id": appt["id"],
        },
    )
    assert init.status_code == 200
    body = init.json()
    assert body["ok"] is True
    assert body.get("dev") is True or body.get("checkout_url")


def test_reminder_job_followup_and_vaccine(client, patient_auth):
    uid = UUID(patient_auth["user_id"])

    async def _seed_and_run() -> tuple[int, int]:
        async with async_session_factory() as db:
            template = ChildFollowupVisitTemplate(
                code=f"t-{uuid4().hex[:8]}",
                label="6-week",
                sort_order=1,
                offset_days=42,
                is_published=True,
            )
            db.add(template)
            await db.flush()
            db.add(
                ChildFollowupVisit(
                    user_id=uid,
                    child_local_id="rem-baby",
                    template_id=template.id,
                    due_date=date.today(),
                    status="scheduled",
                )
            )
            db.add(
                VaccineDoseSchedule(
                    code="bcg-rem",
                    display_name="BCG",
                    dose_number=1,
                    series_code="bcg",
                    eligible_from_days=0,
                    is_published=True,
                )
            )
            db.add(
                ChildVaccineRecord(
                    user_id=uid,
                    child_local_id="rem-baby",
                    vaccine_key="bcg-rem",
                    vaccine_name="BCG",
                    received=False,
                )
            )
            await db.commit()
        followups = await run_followup_reminders()
        vaccines = await run_vaccine_reminders()
        return followups, vaccines

    followups, vaccines = asyncio.run(_seed_and_run())
    assert followups >= 1
    assert vaccines >= 1

    notes = client.get("/api/v1/notifications", headers=auth_header(patient_auth["token"])).json()
    assert any(n["type"] == "followup_reminder" for n in notes)
    assert any(n["type"] == "vaccine_reminder" for n in notes)
