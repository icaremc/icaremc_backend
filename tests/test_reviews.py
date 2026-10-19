from datetime import date, timedelta
from decimal import Decimal
import uuid

from tests.conftest import auth_header


def test_create_review_first_time_and_upsert_second_time(client, patient_auth, doctor_auth):
    patient_h = auth_header(patient_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])

    # Setup doctor service
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "Pediatric Consultation", "price": "300.00", "duration_minutes": 30},
    ).json()

    # Book appointment
    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=1)),
            "time_slot": "09:00",
            "service_id": service["id"],
        },
    ).json()

    # First time creating review
    res1 = client.post(
        "/api/v1/reviews",
        headers=patient_h,
        json={
            "appointment_id": appt["id"],
            "rating": "4.0",
            "comment": "Good doctor, on time.",
        },
    )
    assert res1.status_code == 200, res1.text
    review1 = res1.json()
    assert review1["appointment_id"] == appt["id"]
    assert Decimal(str(review1["rating"])) == Decimal("4.0")
    assert review1["comment"] == "Good doctor, on time."

    # Second time creating review on the SAME appointment (previously threw 500 error, now upserts)
    res2 = client.post(
        "/api/v1/reviews",
        headers=patient_h,
        json={
            "appointment_id": appt["id"],
            "rating": "5.0",
            "comment": "Updated: Excellent follow-up care!",
        },
    )
    assert res2.status_code == 200, res2.text
    review2 = res2.json()
    assert review2["id"] == review1["id"]  # Same review updated
    assert review2["appointment_id"] == appt["id"]
    assert Decimal(str(review2["rating"])) == Decimal("5.0")
    assert review2["comment"] == "Updated: Excellent follow-up care!"


def test_patient_fetch_reviews_with_filters(client, patient_auth, doctor_auth):
    patient_h = auth_header(patient_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])

    # Setup service & appointment
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "General Checkup", "price": "200.00", "duration_minutes": 20},
    ).json()

    appt = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=3)),
            "time_slot": "14:00",
            "service_id": service["id"],
        },
    ).json()

    # Before reviewing, single review endpoint returns 404
    not_yet_reviewed = client.get(f"/api/v1/appointments/{appt['id']}/review", headers=patient_h)
    assert not_yet_reviewed.status_code == 404

    # Post review
    post_res = client.post(
        "/api/v1/reviews",
        headers=patient_h,
        json={
            "appointment_id": appt["id"],
            "rating": "4.8",
            "comment": "Very attentive and kind.",
        },
    )
    assert post_res.status_code == 200

    # 1. Fetch by specific appointment endpoint
    single_res = client.get(f"/api/v1/appointments/{appt['id']}/review", headers=patient_h)
    assert single_res.status_code == 200
    assert single_res.json()["appointment_id"] == appt["id"]
    assert single_res.json()["comment"] == "Very attentive and kind."

    # 2. List all patient reviews via GET /api/v1/reviews
    all_res = client.get("/api/v1/reviews", headers=patient_h)
    assert all_res.status_code == 200
    items = all_res.json()
    assert len(items) >= 1
    assert any(r["appointment_id"] == appt["id"] for r in items)

    # 3. Filter by appointment_id query param
    by_appt = client.get("/api/v1/reviews", headers=patient_h, params={"appointment_id": appt["id"]})
    assert by_appt.status_code == 200
    assert len(by_appt.json()) == 1
    assert by_appt.json()[0]["appointment_id"] == appt["id"]

    # 4. Filter by doctor_id query param
    by_doc = client.get(
        "/api/v1/reviews",
        headers=patient_h,
        params={"doctor_id": doctor_auth["user_id"]},
    )
    assert by_doc.status_code == 200
    assert any(r["appointment_id"] == appt["id"] for r in by_doc.json())

    # 5. Doctor can also view their reviews
    doc_res = client.get("/api/v1/doctor/reviews", headers=doctor_h)
    assert doc_res.status_code == 200
    assert any(r["appointment_id"] == appt["id"] for r in doc_res.json())

    # 6. Non-existent appointment review returns 404
    non_existent = client.get(f"/api/v1/appointments/{uuid.uuid4()}/review", headers=patient_h)
    assert non_existent.status_code == 404
