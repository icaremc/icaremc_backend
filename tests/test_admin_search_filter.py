from datetime import date, timedelta
from tests.conftest import auth_header


def test_admin_users_search_filter_pagination(client, admin_auth, patient_auth, doctor_auth):
    h = auth_header(admin_auth["token"])

    # 1. Base list
    res = client.get("/api/v1/admin/users?limit=10&offset=0", headers=h)
    assert res.status_code == 200
    all_users = res.json()
    assert len(all_users) >= 1

    # 2. Search by patient name
    res_search = client.get("/api/v1/admin/users?search=Mother", headers=h)
    assert res_search.status_code == 200
    matched = res_search.json()
    assert len(matched) >= 1
    assert any(u["id"] == patient_auth["user_id"] for u in matched)

    # 3. Search with non-matching string
    res_empty = client.get("/api/v1/admin/users?search=nonexistent_xyz_9999", headers=h)
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0

    # 4. Filter by role
    res_patient = client.get("/api/v1/admin/users?role=patient", headers=h)
    assert res_patient.status_code == 200
    assert any(u["id"] == patient_auth["user_id"] for u in res_patient.json())

    # 5. Pagination offset
    res_page1 = client.get("/api/v1/admin/users?limit=1&offset=0", headers=h)
    assert res_page1.status_code == 200
    assert len(res_page1.json()) <= 1


def test_admin_appointments_search_filter_pagination(client, admin_auth, doctor_auth, patient_auth):
    h = auth_header(admin_auth["token"])

    # Create service and book appointment
    service = client.post(
        "/api/v1/doctor/services",
        headers=auth_header(doctor_auth["token"]),
        json={"name": "SearchVisit", "price": "150.00"},
    ).json()

    book = client.post(
        "/api/v1/appointments",
        headers=auth_header(patient_auth["token"]),
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=7)),
            "time_slot": "10:00",
            "service_id": service["id"],
        },
    )
    assert book.status_code == 200
    appt_id = book.json()["id"]

    # Filter by status=pending
    res = client.get("/api/v1/admin/appointments?status=pending", headers=h)
    assert res.status_code == 200
    appts = res.json()["appointments"]
    assert any(a["id"] == appt_id for a in appts)

    # Filter by doctor_id
    res_doc = client.get(f"/api/v1/admin/appointments?doctor_id={doctor_auth['user_id']}", headers=h)
    assert res_doc.status_code == 200
    assert any(a["id"] == appt_id for a in res_doc.json()["appointments"])

    # Filter by patient_id
    res_pat = client.get(f"/api/v1/admin/appointments?patient_id={patient_auth['user_id']}", headers=h)
    assert res_pat.status_code == 200
    assert any(a["id"] == appt_id for a in res_pat.json()["appointments"])

    # Non-matching status
    res_cancelled = client.get(f"/api/v1/admin/appointments?doctor_id={doctor_auth['user_id']}&status=cancelled", headers=h)
    assert res_cancelled.status_code == 200
    assert not any(a["id"] == appt_id for a in res_cancelled.json()["appointments"])


def test_admin_children_search_filter_pagination(client, admin_auth, patient_auth):
    h = auth_header(admin_auth["token"])
    p_header = auth_header(patient_auth["token"])

    # Create a child
    created_child = client.post(
        "/api/v1/children",
        headers=p_header,
        json={
            "name": "LittleSara",
            "gender": "female",
            "birth_date": "2024-01-15",
        },
    )
    assert created_child.status_code == 200
    child_id = created_child.json()["id"]

    # 1. Search by child name
    res_search = client.get("/api/v1/admin/children?search=LittleSara", headers=h)
    assert res_search.status_code == 200
    children = res_search.json()["children"]
    assert any(c["id"] == child_id for c in children)

    # 2. Filter by gender
    res_female = client.get("/api/v1/admin/children?gender=female", headers=h)
    assert res_female.status_code == 200
    assert any(c["id"] == child_id for c in res_female.json()["children"])

    res_male = client.get(f"/api/v1/admin/children?user_id={patient_auth['user_id']}&gender=male", headers=h)
    assert res_male.status_code == 200
    assert not any(c["id"] == child_id for c in res_male.json()["children"])

    # 3. Filter by user_id
    res_user = client.get(f"/api/v1/admin/children?user_id={patient_auth['user_id']}", headers=h)
    assert res_user.status_code == 200
    assert any(c["id"] == child_id for c in res_user.json()["children"])


def test_admin_activity_logs_search_and_filter(client, admin_auth):
    h = auth_header(admin_auth["token"])

    # Fetch logs with limit & offset
    res = client.get("/api/v1/admin/activity-logs?limit=5&offset=0", headers=h)
    assert res.status_code == 200
    body = res.json()
    assert "logs" in body
    assert "pagination" in body
    assert body["pagination"]["limit"] == 5
    assert body["pagination"]["offset"] == 0

    # Search with nonexistent term
    res_empty = client.get("/api/v1/admin/activity-logs?search=xyz_nonexistent_action_1234", headers=h)
    assert res_empty.status_code == 200
    assert len(res_empty.json()["logs"]) == 0
    assert res_empty.json()["pagination"]["total"] == 0


def test_admin_referrals_search_filter(client, admin_auth, doctor_auth, patient_auth):
    h = auth_header(admin_auth["token"])

    # Apply doctor's referral code to patient
    doc_res = client.get(f"/api/v1/admin/doctors/{doctor_auth['user_id']}/referral-stats", headers=h)
    assert doc_res.status_code == 200
    ref_code = doc_res.json()["referral_code"]

    apply_res = client.post(
        f"/api/v1/admin/users/{patient_auth['user_id']}/referral",
        headers=h,
        json={"code": ref_code},
    )
    assert apply_res.status_code == 200

    # 1. Search referrals by referral code
    res_search = client.get(f"/api/v1/admin/referrals?search={ref_code}", headers=h)
    assert res_search.status_code == 200
    assert any(r["referral_code"] == ref_code for r in res_search.json())

    # 2. Filter referrals by doctor_id
    res_doc = client.get(f"/api/v1/admin/referrals?doctor_id={doctor_auth['user_id']}", headers=h)
    assert res_doc.status_code == 200
    assert any(r["doctor_id"] == doctor_auth["user_id"] for r in res_doc.json())


def test_admin_wallet_transactions_filter(client, admin_auth, doctor_auth):
    h = auth_header(admin_auth["token"])

    # Wallet transactions query
    res = client.get(f"/api/v1/admin/wallet-transactions?doctor_id={doctor_auth['user_id']}&limit=10&offset=0", headers=h)
    assert res.status_code == 200
    assert "transactions" in res.json()
