from datetime import date, timedelta
from tests.conftest import auth_header


def test_appointment_notifications_lifecycle(client, patient_auth, doctor_auth, admin_auth):
    admin_h = auth_header(admin_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])

    # 1. Admin verifies doctor
    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )

    # 2. Setup doctor FCM token and service
    client.patch("/api/v1/doctor/profile", headers=doctor_h, json={"fcm_token": "doc_token_abc"})
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "Pediatric Consult", "price": "250.00"},
    ).json()

    # 3. Patient registers FCM token
    client.patch("/api/v1/profile", headers=patient_h, json={"fcm_token": "patient_token_xyz"})

    # 4. Patient books appointment -> Doctor receives notification
    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=3)),
            "time_slot": "09:00",
            "service_id": service["id"],
        },
    )
    assert appt.status_code == 200
    appt_id = appt.json()["id"]

    # Verify doctor received notification in their inbox
    doc_notifs = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "appointment_new" for n in doc_notifs)
    new_notif = next(n for n in doc_notifs if n["type"] == "appointment_new")
    assert "09:00" in new_notif["body"]

    # 5. Doctor confirms appointment -> Patient receives confirmed notification
    status_resp = client.post(
        f"/api/v1/doctor/appointments/{appt_id}/status",
        headers=doctor_h,
        json={"status": "confirmed"},
    )
    assert status_resp.status_code == 200

    patient_notifs = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "appointment_confirmed" for n in patient_notifs)

    # 6. Doctor completes appointment -> Patient receives review notification
    complete_resp = client.post(
        f"/api/v1/doctor/appointments/{appt_id}/status",
        headers=doctor_h,
        json={"status": "completed"},
    )
    assert complete_resp.status_code == 200

    patient_notifs_after = client.get("/api/v1/notifications", headers=patient_h).json()
    assert any(n["type"] == "appointment_completed" for n in patient_notifs_after)
    review_notif = next(n for n in patient_notifs_after if n["type"] == "appointment_completed")
    assert "review" in review_notif["body"].lower()

    # 7. Test patient cancellation notification
    # Book second appointment to test cancellation
    appt2 = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=4)),
            "time_slot": "14:00",
            "service_id": service["id"],
        },
    ).json()
    appt2_id = appt2["id"]

    cancel_resp = client.post(
        f"/api/v1/appointments/{appt2_id}/cancel",
        headers=patient_h,
    )
    assert cancel_resp.status_code == 200

    doc_notifs_after_cancel = client.get("/api/v1/doctor/notifications", headers=doctor_h).json()
    assert any(n["type"] == "appointment_cancelled" for n in doc_notifs_after_cancel)
