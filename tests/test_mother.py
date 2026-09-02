from datetime import date, timedelta

from tests.conftest import auth_header
from tests.payment_helpers import pay_appointment


def test_profile_get_and_patch(client, patient_auth):
    h = auth_header(patient_auth["token"])
    profile = client.get("/api/v1/me/profile", headers=h)
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Test Mother"

    patched = client.patch("/api/v1/me/profile", headers=h, json={"locale": "am", "location": "Addis"})
    assert patched.status_code == 200
    assert patched.json()["locale"] == "am"
    assert patched.json()["location"] == "Addis"


def test_pregnancy_and_logs(client, patient_auth):
    h = auth_header(patient_auth["token"])
    created = client.post(
        "/api/v1/pregnancies",
        headers=h,
        json={"lmp_date": str(date.today() - timedelta(days=60)), "status": "active"},
    )
    assert created.status_code == 200
    preg_id = created.json()["id"]

    listed = client.get("/api/v1/pregnancies", headers=h)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    log = client.post(
        "/api/v1/pregnancy-logs",
        headers=h,
        json={"pregnancy_id": preg_id, "week_number": 8, "weight": 62.5, "symptoms": ["nausea"]},
    )
    assert log.status_code == 200
    logs = client.get("/api/v1/pregnancy-logs", headers=h, params={"pregnancy_id": preg_id})
    assert logs.status_code == 200
    assert len(logs.json()) == 1


def test_children_growth_milestones_vaccines(client, patient_auth):
    h = auth_header(patient_auth["token"])
    child = client.post(
        "/api/v1/children",
        headers=h,
        json={
            "local_id": "baby-1",
            "name": "Kid",
            "gender": "female",
            "birth_date": str(date.today() - timedelta(days=90)),
        },
    )
    assert child.status_code == 200

    kids = client.get("/api/v1/children", headers=h)
    assert len(kids.json()) == 1

    m = client.post(
        "/api/v1/child-measurements",
        headers=h,
        json={"child_local_id": "baby-1", "weight_kg": 5.2, "height_cm": 58},
    )
    assert m.status_code == 200
    assert client.get("/api/v1/child-measurements", headers=h, params={"child_local_id": "baby-1"}).json()

    ms = client.post(
        "/api/v1/child-milestones",
        headers=h,
        json={"child_local_id": "baby-1", "item_key": "smile"},
    )
    assert ms.status_code == 200

    v = client.post(
        "/api/v1/child-vaccines",
        headers=h,
        json={
            "child_local_id": "baby-1",
            "vaccine_key": "bcg",
            "vaccine_name": "BCG",
            "received": True,
            "date_received": str(date.today()),
        },
    )
    assert v.status_code == 200
    vaccines = client.get("/api/v1/child-vaccines", headers=h, params={"child_local_id": "baby-1"})
    assert len(vaccines.json()) == 1


def test_cms_reads_empty(client):
    assert client.get("/api/v1/cms/pregnancy-weeks").status_code == 200
    assert client.get("/api/v1/cms/child-growth-periods").status_code == 200
    assert client.get("/api/v1/cms/daily-tips").status_code == 200
    assert client.get("/api/v1/cms/symptoms").status_code == 200
    assert client.get("/api/v1/doctors/categories").status_code == 200
    assert client.get("/api/v1/settings/payment").status_code == 200


def test_wallet_and_notifications(client, patient_auth):
    h = auth_header(patient_auth["token"])
    wallet = client.get("/api/v1/wallet", headers=h)
    assert wallet.status_code == 200
    assert wallet.json()["wallet"] is not None

    notes = client.get("/api/v1/notifications", headers=h)
    assert notes.status_code == 200
    assert notes.json() == []


def test_book_appointment_flow(client, patient_auth, doctor_auth, admin_auth):
    admin_h = auth_header(admin_auth["token"])
    patient_h = auth_header(patient_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])

    verified = client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )
    assert verified.status_code == 200

    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "Consult", "price": "500.00", "duration_minutes": 30},
    )
    assert service.status_code == 200
    service_id = service.json()["id"]

    doctors = client.get("/api/v1/doctors")
    assert any(d["id"] == doctor_auth["user_id"] for d in doctors.json())

    detail = client.get(f"/api/v1/doctors/{doctor_auth['user_id']}")
    assert detail.status_code == 200
    assert len(detail.json()["services"]) == 1

    book = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=2)),
            "time_slot": "10:00",
            "service_id": service_id,
        },
    )
    assert book.status_code == 200, book.text
    appt_id = book.json()["id"]
    assert book.json()["payment_status"] in ("unpaid", "waived")
    pay_appointment(client, patient_auth["token"], appt_id, "500.00")

    mine = client.get("/api/v1/appointments", headers=patient_h)
    assert len(mine.json()) == 1

    convos = client.get("/api/v1/chat/conversations", headers=patient_h)
    assert len(convos.json()) == 1
    conv_id = convos.json()[0]["id"]

    msg = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=patient_h,
        json={"body": "hello doctor"},
    )
    assert msg.status_code == 200

    review = client.post(
        "/api/v1/reviews",
        headers=patient_h,
        json={"appointment_id": appt_id, "rating": "5", "comment": "great"},
    )
    assert review.status_code == 200


def test_cms_seeded_and_patient_cancel(client, patient_auth, doctor_auth, admin_auth):
    admin_h = auth_header(admin_auth["token"])
    patient_h = auth_header(patient_auth["token"])
    doctor_h = auth_header(doctor_auth["token"])

    week = client.post(
        "/api/v1/admin/pregnancy-weeks",
        headers=admin_h,
        json={"week_number": 20, "trimester": 2, "is_published": True},
    )
    assert week.status_code == 200
    client.post(
        f"/api/v1/admin/pregnancy-weeks/{week.json()['id']}/translations",
        headers=admin_h,
        json={"language_code": "en", "title": "Week 20", "baby": "Active"},
    )
    weeks = client.get("/api/v1/cms/pregnancy-weeks")
    assert weeks.status_code == 200
    assert any(w.get("week_number") == 20 for w in weeks.json())
    assert weeks.json()[0]["translation"] is not None or any(
        w.get("translation") for w in weeks.json()
    )

    assert client.get("/api/v1/cms/clinical-advice").status_code == 200
    assert client.get("/api/v1/cms/vaccine-schedule").status_code == 200
    legal = client.put(
        "/api/v1/admin/legal-documents",
        headers=admin_h,
        json={"slug": "tos", "locale": "en", "title": "Terms", "sections": []},
    )
    assert legal.status_code == 200
    assert client.get("/api/v1/cms/legal/tos").status_code == 200

    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=admin_h,
        json={"is_verified": True},
    )
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "CancelMe", "price": "150.00"},
    ).json()
    book = client.post(
        "/api/v1/appointments",
        headers=patient_h,
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=4)),
            "time_slot": "16:00",
            "service_id": service["id"],
        },
    )
    assert book.status_code == 200
    cancelled = client.post(
        f"/api/v1/appointments/{book.json()['id']}/cancel",
        headers=patient_h,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    child = client.post(
        "/api/v1/children",
        headers=patient_h,
        json={
            "local_id": "baby-patch",
            "name": "Kid2",
            "gender": "male",
            "birth_date": str(date.today() - timedelta(days=30)),
        },
    ).json()
    patched = client.patch(
        f"/api/v1/children/{child['id']}",
        headers=patient_h,
        json={
            "local_id": "baby-patch",
            "name": "Kid2 Updated",
            "gender": "male",
            "birth_date": str(date.today() - timedelta(days=30)),
        },
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Kid2 Updated"

    assert client.get("/api/v1/subscriptions/app", headers=patient_h).status_code == 200
    assert client.get("/api/v1/subscriptions/care", headers=patient_h).status_code == 200
    followups = client.get(
        "/api/v1/child-followups",
        headers=patient_h,
        params={"child_local_id": "baby-patch"},
    )
    assert followups.status_code == 200
