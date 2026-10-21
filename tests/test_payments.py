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


def test_child_payment_flow(client, patient_auth):
    patient_h = auth_header(patient_auth["token"])

    # 1. Create a child -> starts as unpaid
    child_res = client.post(
        "/api/v1/children",
        headers=patient_h,
        json={
            "name": "Little Abebe",
            "gender": "male",
            "birth_date": str(date.today() - timedelta(days=30)),
        },
    )
    assert child_res.status_code == 200
    child = child_res.json()
    assert child["payment_status"] == "unpaid"
    child_id = child["id"]

    # 2. Check child payment status endpoint
    status_res = client.get(
        f"/api/v1/payments/children/{child_id}/status",
        headers=patient_h,
    )
    assert status_res.status_code == 200
    assert status_res.json()["payment_status"] == "unpaid"

    # 3. Initiate payment via Chapa (dev mode)
    init_res = client.post(
        "/api/v1/payments/chapa/initiate",
        headers=patient_h,
        json={
            "kind": "child_registration",
            "amount": "500.00",
            "child_id": child_id,
        },
    )
    assert init_res.status_code == 200
    init_body = init_res.json()
    assert init_body["ok"] is True
    assert init_body["dev"] is True
    tx_ref = init_body["tx_ref"]
    assert "child_registration" in tx_ref

    # 4. Trigger Chapa Webhook
    webhook_res = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": tx_ref,
            "status": "success",
            "amount": "500.00",
            "reference": "CHAPA-TEST-12345",
            "meta": {
                "kind": "child_registration",
                "user_id": patient_auth["user_id"],
                "child_id": child_id,
            },
        },
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json().get("type") == "child_registration"

    # 5. Idempotent webhook check
    webhook_dup = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": tx_ref,
            "status": "success",
            "amount": "500.00",
        },
    )
    assert webhook_dup.status_code == 200
    assert webhook_dup.json().get("idempotent") is True

    # 6. Verify child is now paid
    child_after = client.get(f"/api/v1/children/{child_id}", headers=patient_h).json()
    assert child_after["payment_status"] == "paid"
    assert float(child_after["amount_paid"]) == 500.0
    assert child_after["payment_method"] == "chapa"
    assert child_after["payment_tx_ref"] == tx_ref

    # 7. Check verify transaction endpoint
    verify_res = client.get(f"/api/v1/payments/verify/{tx_ref}", headers=patient_h)
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "success"

    # 8. Check patient received confirmation notification
    p_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "child_payment_confirmed" for n in p_notifs)


def test_admin_child_payment_management(client, patient_auth, admin_auth):
    patient_h = auth_header(patient_auth["token"])
    admin_h = auth_header(admin_auth["token"])

    # 1. Create a child
    child = client.post(
        "/api/v1/children",
        headers=patient_h,
        json={
            "name": "Sara Admin Test",
            "gender": "female",
            "birth_date": str(date.today() - timedelta(days=60)),
        },
    ).json()
    child_id = child["id"]
    assert child["payment_status"] == "unpaid"

    # 2. Admin manually activates child
    act_res = client.post(
        f"/api/v1/admin/children/{child_id}/activate",
        headers=admin_h,
        json={"amount": "450.00", "payment_method": "cash_receipt"},
    )
    assert act_res.status_code == 200
    activated = act_res.json()
    assert activated["payment_status"] == "paid"
    assert float(activated["amount_paid"]) == 450.0
    assert activated["payment_method"] == "cash_receipt"

    # 3. Admin queries child payments list
    payments_res = client.get(
        "/api/v1/admin/child-payments",
        headers=admin_h,
        params={"child_id": child_id},
    )
    assert payments_res.status_code == 200
    payments = payments_res.json()["payments"]
    assert len(payments) >= 1
    assert payments[0]["child_id"] == child_id
    assert payments[0]["status"] == "success"
    assert float(payments[0]["amount"]) == 450.0


def test_pregnancy_payment_flow(client, patient_auth):
    patient_h = auth_header(patient_auth["token"])

    # 1. Create a pregnancy -> starts as unpaid
    preg_res = client.post(
        "/api/v1/pregnancies",
        headers=patient_h,
        json={
            "lmp_date": str(date.today() - timedelta(days=60)),
            "edd": str(date.today() + timedelta(days=220)),
            "pregnancy_number": 1,
            "is_first_pregnancy": True,
        },
    )
    assert preg_res.status_code == 200
    preg = preg_res.json()
    assert preg["payment_status"] == "unpaid"
    pregnancy_id = preg["id"]

    # 2. Check pregnancy payment status endpoint
    status_res = client.get(
        f"/api/v1/payments/pregnancies/{pregnancy_id}/status",
        headers=patient_h,
    )
    assert status_res.status_code == 200
    assert status_res.json()["payment_status"] == "unpaid"

    # 3. Initiate payment via Chapa (dev mode)
    init_res = client.post(
        "/api/v1/payments/chapa/initiate",
        headers=patient_h,
        json={
            "kind": "pregnancy_registration",
            "amount": "500.00",
            "pregnancy_id": pregnancy_id,
        },
    )
    assert init_res.status_code == 200
    init_body = init_res.json()
    assert init_body["ok"] is True
    assert init_body["dev"] is True
    tx_ref = init_body["tx_ref"]
    assert "pregnancy_registration" in tx_ref

    # 4. Trigger Chapa Webhook
    webhook_res = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": tx_ref,
            "status": "success",
            "amount": "500.00",
            "reference": "CHAPA-TEST-PREG-12345",
            "meta": {
                "kind": "pregnancy_registration",
                "user_id": patient_auth["user_id"],
                "pregnancy_id": pregnancy_id,
            },
        },
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json().get("type") == "pregnancy_registration"

    # 5. Idempotent webhook check
    webhook_dup = client.post(
        "/api/v1/payments/chapa/webhook",
        json={
            "tx_ref": tx_ref,
            "status": "success",
            "amount": "500.00",
        },
    )
    assert webhook_dup.status_code == 200
    assert webhook_dup.json().get("idempotent") is True

    # 6. Verify pregnancy is now paid via status endpoint
    status_after = client.get(
        f"/api/v1/payments/pregnancies/{pregnancy_id}/status",
        headers=patient_h,
    ).json()
    assert status_after["payment_status"] == "paid"
    assert float(status_after["amount_paid"]) == 500.0
    assert status_after["payment_method"] == "chapa"
    assert status_after["tx_ref"] == tx_ref

    # 7. Check verify transaction endpoint
    verify_res = client.get(f"/api/v1/payments/verify/{tx_ref}", headers=patient_h)
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "success"
    assert verify_res.json()["pregnancy_id"] == pregnancy_id

    # 8. Check patient received confirmation notification
    p_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "pregnancy_payment_confirmed" for n in p_notifs)


def test_admin_pregnancy_payment_management(client, patient_auth, admin_auth):
    patient_h = auth_header(patient_auth["token"])
    admin_h = auth_header(admin_auth["token"])

    # 1. Create a pregnancy
    preg = client.post(
        "/api/v1/pregnancies",
        headers=patient_h,
        json={
            "lmp_date": str(date.today() - timedelta(days=90)),
            "edd": str(date.today() + timedelta(days=190)),
            "pregnancy_number": 2,
        },
    ).json()
    pregnancy_id = preg["id"]
    assert preg["payment_status"] == "unpaid"

    # 2. Admin manually activates pregnancy
    act_res = client.post(
        f"/api/v1/admin/pregnancies/{pregnancy_id}/activate",
        headers=admin_h,
        json={"amount": "450.00", "payment_method": "cash_receipt"},
    )
    assert act_res.status_code == 200
    activated = act_res.json()
    assert activated["payment_status"] == "paid"
    assert float(activated["amount_paid"]) == 450.0
    assert activated["payment_method"] == "cash_receipt"

    # 3. Admin queries care profile payments list filtered by pregnancy_id
    payments_res = client.get(
        "/api/v1/admin/care-profile-payments",
        headers=admin_h,
        params={"pregnancy_id": pregnancy_id},
    )
    assert payments_res.status_code == 200
    payments = payments_res.json()["payments"]
    assert len(payments) >= 1
    assert payments[0]["pregnancy_id"] == pregnancy_id
    assert payments[0]["payment_type"] == "pregnancy"
    assert payments[0]["status"] == "success"
    assert float(payments[0]["amount"]) == 450.0

