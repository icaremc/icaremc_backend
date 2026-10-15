from datetime import date, timedelta
from tests.conftest import auth_header


def test_doctor_verification_push_notification(client, admin_auth, doctor_auth):
    admin_h = auth_header(admin_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])

    # Doctor sets FCM token
    client.patch("/api/v1/doctor/profile", headers=doctor_h, json={"fcm_token": "doctor_fcm_verified"})

    # Admin verifies doctor
    res = client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )
    assert res.status_code == 200

    # Doctor should receive exactly 1 in-app notification
    notifs = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    verified_notifs = [n for n in notifs if n["type"] == "doctor_verified"]
    assert len(verified_notifs) == 1

    # Admin verifies doctor again with is_verified=True -> should NOT duplicate
    res_dup = client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )
    assert res_dup.status_code == 200
    notifs_after_dup = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    verified_after = [n for n in notifs_after_dup if n["type"] == "doctor_verified"]
    assert len(verified_after) == 1

    # Admin removes approval of doctor status
    res_unverify = client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": False},
    )
    assert res_unverify.status_code == 200

    # Doctor should receive revocation notification
    notifs_after_unverify = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "doctor_unverified" for n in notifs_after_unverify)


def test_doctor_payout_push_notification(client, admin_auth, doctor_auth, patient_auth):
    from tests.payment_helpers import pay_appointment

    admin_h = auth_header(admin_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])

    # First verify doctor
    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )

    # Doctor sets up service
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "Specialist Consult", "price": "500.00"},
    ).json()

    # Patient books and pays for appointment
    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=2)),
            "time_slot": "10:00",
            "service_id": service["id"],
        },
    ).json()
    pay_appointment(client, patient_auth["token"], appt["id"], "500.00")

    # Doctor completes appointment to credit wallet
    client.post(
        f"/api/v1/doctor/appointments/{appt['id']}/status",
        headers=doctor_h,
        json={"status": "completed"},
    )

    # Setup payout method
    pm = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={"holder_name": "Dr Test", "account_number": "100012345678", "bank_name": "CBE"},
    ).json()

    # Doctor creates payout request
    payout_req = client.post(
        "/api/v1/doctor/payouts",
        headers=doctor_h,
        json={"amount": "200.00", "payout_method_id": pm["id"]},
    )
    assert payout_req.status_code == 200
    req_id = payout_req.json()["id"]

    # Admin approves payout request
    action = client.post(
        f"/api/v1/admin/payout-requests/{req_id}",
        headers=admin_h,
        json={"status": "approved", "admin_note": "Approved by finance"},
    )
    assert action.status_code == 200

    # Doctor should receive payout approval notification
    notifs = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "doctor_payout" for n in notifs)


def test_admin_grant_membership_notification(client, admin_auth, patient_auth):
    admin_h = auth_header(admin_auth["token"])
    patient_h = auth_header(patient_auth["token"])

    # Admin grants membership
    grant = client.post(
        "/api/v1/admin/membership/grant",
        headers=admin_h,
        json={"patient_id": patient_auth["user_id"], "days": 30, "amount_paid": "0.00"},
    )
    assert grant.status_code == 200

    # Patient should receive notification
    notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "subscription_active" for n in notifs)


def test_admin_broadcast_and_direct_notice(client, admin_auth, patient_auth, doctor_auth):
    admin_h = auth_header(admin_auth["token"])
    patient_h = auth_header(patient_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])

    # 1. Admin sends direct notice to patient
    notice = client.post(
        f"/api/v1/admin/users/{patient_auth['user_id']}/notify",
        headers=admin_h,
        json={
            "title": "Welcome to New Care Program",
            "body": "A personalized care plan is available for you.",
            "route": "/care-plans",
            "screen": "care_plans",
            "is_urgent": True,
        },
    )
    assert notice.status_code == 200

    p_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "care_admin_notice" for n in p_notifs)
    item = next(n for n in p_notifs if n["type"] == "care_admin_notice")
    assert item["title"] == "Welcome to New Care Program"

    # 2. Admin broadcasts to all users
    bcast = client.post(
        "/api/v1/admin/broadcast",
        headers=admin_h,
        json={
            "title": "System Maintenance Notice",
            "body": "We will have maintenance on Sunday at 2 AM UTC.",
            "target_role": "all",
            "is_urgent": False,
        },
    )
    assert bcast.status_code == 200
    assert bcast.json()["count"] >= 2

    # Check that both patient and doctor have broadcast in their in-app notifications
    p_notifs_after = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "care_admin_broadcast" for n in p_notifs_after)

    d_notifs_after = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "care_admin_broadcast" for n in d_notifs_after)
