from datetime import date, time, timedelta
from decimal import Decimal

from tests.conftest import auth_header
from tests.payment_helpers import pay_appointment


def test_doctor_profile_and_services_slots(client, doctor_auth):
    h = auth_header(doctor_auth["token"])
    me = client.get("/api/v1/doctor/me", headers=h)
    assert me.status_code == 200
    assert me.json()["first_name"] == "Doc"

    patched = client.patch("/api/v1/doctor/me", headers=h, json={"bio": "Experienced OB"})
    assert patched.status_code == 200
    assert patched.json()["bio"] == "Experienced OB"

    service = client.post(
        "/api/v1/doctor/services",
        headers=h,
        json={"name": "ANC", "price": "800.00", "duration_minutes": 30},
    )
    assert service.status_code == 200
    service_id = service.json()["id"]

    services = client.get("/api/v1/doctor/services", headers=h)
    assert len(services.json()) == 1

    slot = client.post(
        "/api/v1/doctor/slots",
        headers=h,
        json={
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "12:00:00",
            "slot_duration_minutes": 30,
        },
    )
    assert slot.status_code == 200
    assert client.get("/api/v1/doctor/slots", headers=h).json()

    deleted = client.delete(f"/api/v1/doctor/services/{service_id}", headers=h)
    assert deleted.status_code == 200


def test_doctor_appointment_complete_and_wallet(client, patient_auth, doctor_auth, admin_auth):
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
        json={"name": "Visit", "price": "300.00"},
    ).json()

    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=1)),
            "time_slot": "11:00",
            "service_id": service["id"],
        },
    )
    assert appt.status_code == 200
    appt_id = appt.json()["id"]
    pay_appointment(client, patient_auth["token"], appt_id, "300.00")

    confirm = client.post(
        f"/api/v1/doctor/appointments/{appt_id}/status",
        headers=doctor_h,
        json={"status": "confirmed"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    complete = client.post(
        f"/api/v1/doctor/appointments/{appt_id}/status",
        headers=doctor_h,
        json={"status": "completed"},
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"

    wallet = client.get("/api/v1/doctor/wallet", headers=doctor_h)
    assert wallet.status_code == 200
    assert Decimal(wallet.json()["wallet"]["available_balance"]) >= Decimal("300")


def test_doctor_payout_methods_and_request(client, doctor_auth):
    h = auth_header(doctor_auth["token"])
    method = client.post(
        "/api/v1/doctor/payout-methods",
        headers=h,
        json={
            "holder_name": "Doc Tor",
            "account_number": "1000123456",
            "bank_name": "CBE",
            "is_default": True,
        },
    )
    assert method.status_code == 200
    methods = client.get("/api/v1/doctor/payout-methods", headers=h)
    assert len(methods.json()) == 1

    # insufficient balance
    bad = client.post(
        "/api/v1/doctor/payouts",
        headers=h,
        json={"amount": "50.00", "payout_method_id": method.json()["id"]},
    )
    assert bad.status_code == 400


def test_doctor_referrals_and_notifications(client, doctor_auth):
    h = auth_header(doctor_auth["token"])
    refs = client.get("/api/v1/doctor/referrals", headers=h)
    assert refs.status_code == 200
    assert refs.json()["referral_code"]

    notes = client.get("/api/v1/doctor/notifications", headers=h)
    assert notes.status_code == 200


def test_doctor_chat_reply(client, patient_auth, doctor_auth, admin_auth):
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
        json={"name": "ChatVisit", "price": "100.00"},
    ).json()
    client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=3)),
            "time_slot": "14:00",
            "service_id": service["id"],
        },
    )
    convos = client.get("/api/v1/doctor/chat/conversations", headers=doctor_h)
    assert len(convos.json()) == 1
    conv_id = convos.json()[0]["id"]
    reply = client.post(
        f"/api/v1/doctor/chat/conversations/{conv_id}/messages",
        headers=doctor_h,
        json={"body": "see you then"},
    )
    assert reply.status_code == 200


def test_doctor_hospitals_public(client, admin_auth):
    h = auth_header(admin_auth["token"])
    client.post(
        "/api/v1/admin/hospitals",
        headers=h,
        json={"name": "Public Hosp", "slug": "public-hosp", "city": "Addis", "is_active": True},
    )
    listed = client.get("/api/v1/doctor/hospitals")
    assert listed.status_code == 200
    assert any(x["slug"] == "public-hosp" for x in listed.json())
