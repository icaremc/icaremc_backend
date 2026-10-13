from datetime import date, timedelta
from tests.conftest import auth_header


def test_two_way_chat_push_notifications(client, patient_auth, doctor_auth, admin_auth):
    admin_h = auth_header(admin_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])

    # 1. Admin verifies doctor
    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )

    # 2. Doctor sets up service and FCM token
    client.patch("/api/v1/doctor/profile", headers=doctor_h, json={"fcm_token": "doctor_fcm_token_123"})
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "Consult", "price": "100.00"},
    ).json()

    # 3. Patient sets up FCM token and books appointment (which spawns ChatConversation)
    client.patch("/api/v1/profile", headers=patient_h, json={"fcm_token": "patient_fcm_token_456"})
    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=2)),
            "time_slot": "10:00",
            "service_id": service["id"],
        },
    )
    assert appt.status_code == 200

    # 4. Fetch conversation
    convos = client.get("/api/v1/doctor/chat/conversations", headers=doctor_h).json()
    assert len(convos) >= 1
    conv_id = convos[0]["id"]

    # 5. Patient sends message -> triggers push to doctor
    p_msg = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=patient_h,
        json={"body": "Hello Doctor! I have a question about my medication."},
    )
    assert p_msg.status_code == 200
    assert p_msg.json()["body"] == "Hello Doctor! I have a question about my medication."

    # 6. Doctor replies -> triggers push to patient
    d_msg = client.post(
        f"/api/v1/doctor/chat/conversations/{conv_id}/messages",
        headers=doctor_h,
        json={"body": "Please take it with food after breakfast."},
    )
    assert d_msg.status_code == 200
    assert d_msg.json()["body"] == "Please take it with food after breakfast."
