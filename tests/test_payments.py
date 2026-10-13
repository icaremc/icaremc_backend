from datetime import date, timedelta

from tests.conftest import auth_header


def test_chapa_initiate_dev_mode(client, patient_auth, doctor_auth, admin_auth):
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
        json={"name": "PayVisit", "price": "250.00"},
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
            "amount": "250.00",
            "appointment_id": appt["id"],
        },
    )
    assert init.status_code == 200
    body = init.json()
    assert body["ok"] is True
    assert body["dev"] is True
    assert body["tx_ref"]

    webhook = client.post(
        "/api/v1/payments/chapa/webhook",
        json={"tx_ref": body["tx_ref"], "status": "success", "amount": "250.00"},
    )
    assert webhook.status_code == 200
    assert webhook.json()["ok"] is True

    # Check notifications
    p_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "payment_confirmed" for n in p_notifs)

    d_notifs = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "appointment_paid" for n in d_notifs)


def test_chapa_webhook_app_subscription(client, patient_auth):
    patient_h = auth_header(patient_auth["token"])
    webhook = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": "icare-app-test-ref",
            "status": "success",
            "amount": "999.00",
            "meta": {"kind": "app_subscription", "user_id": patient_auth["user_id"]},
        },
    )
    assert webhook.status_code == 200
    assert webhook.json().get("type") == "app_subscription"
    sub = client.get("/api/v1/subscriptions/app", headers=patient_h)
    assert sub.status_code == 200
    assert sub.json() is not None
    assert sub.json()["status"] == "active"

    # Check patient notification
    p_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "subscription_active" for n in p_notifs)


def test_chapa_webhook_care_subscription(client, patient_auth, doctor_auth, admin_auth):
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
        json={"name": "Monthly Maternal Care", "price": "1200.00"},
    ).json()

    webhook = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": "icare-care-sub-ref",
            "status": "success",
            "amount": "1200.00",
            "meta": {
                "kind": "care_subscription",
                "user_id": patient_auth["user_id"],
                "doctor_id": doctor_auth["user_id"],
                "service_id": service["id"],
            },
        },
    )
    assert webhook.status_code == 200
    assert webhook.json().get("type") == "care_subscription"

    # Check patient notification
    p_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "care_subscription_active" for n in p_notifs)

    # Check doctor notification
    d_notifs = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "doctor_care_subscription_new" for n in d_notifs)
