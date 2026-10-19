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
