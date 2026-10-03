from tests.conftest import auth_header


def test_admin_dashboard_and_users(client, admin_auth, patient_auth, doctor_auth):
    h = auth_header(admin_auth["token"])
    dash = client.get("/api/v1/admin/dashboard", headers=h)
    assert dash.status_code == 200
    body = dash.json()
    assert body["profiles"] >= 1
    assert body["doctors"] >= 1

    users = client.get("/api/v1/admin/users", headers=h)
    assert users.status_code == 200
    assert any(u["id"] == patient_auth["user_id"] for u in users.json())

    detail = client.get(f"/api/v1/admin/users/{patient_auth['user_id']}", headers=h)
    assert detail.status_code == 200
    assert detail.json()["profile"]["id"] == patient_auth["user_id"]


def test_admin_settings_hospitals_categories(client, admin_auth):
    h = auth_header(admin_auth["token"])
    put = client.put(
        "/api/v1/admin/settings/payment",
        headers=h,
        json={"data": {"provider": "chapa", "currency": "ETB"}},
    )
    assert put.status_code == 200
    got = client.get("/api/v1/admin/settings/payment", headers=h)
    assert got.json()["data"]["provider"] == "chapa"

    hospital = client.post(
        "/api/v1/admin/hospitals",
        headers=h,
        json={"name": "Black Lion", "slug": "black-lion", "city": "Addis"},
    )
    assert hospital.status_code == 200
    hospitals = client.get("/api/v1/admin/hospitals", headers=h)
    assert any(x["slug"] == "black-lion" for x in hospitals.json())

    cat = client.post(
        "/api/v1/admin/doctor-categories",
        headers=h,
        json={"name": "Obstetrics", "slug": "obstetrics", "care_focus": "pregnancy"},
    )
    assert cat.status_code == 200


def test_admin_cms_and_legal(client, admin_auth):
    h = auth_header(admin_auth["token"])
    week = client.post(
        "/api/v1/admin/pregnancy-weeks",
        headers=h,
        json={"week_number": 12, "trimester": 1, "is_published": True},
    )
    assert week.status_code == 200
    week_id = week.json()["id"]
    tr = client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h,
        json={"language_code": "en", "title": "Week 12", "baby": "Growing"},
    )
    assert tr.status_code == 200

    legal = client.put(
        "/api/v1/admin/legal-documents",
        headers=h,
        json={"slug": "privacy", "locale": "en", "title": "Privacy", "sections": [{"title": "A"}]},
    )
    assert legal.status_code == 200
    docs = client.get("/api/v1/admin/legal-documents", headers=h)
    assert any(d["slug"] == "privacy" for d in docs.json())


def test_admin_membership_grant_revoke(client, admin_auth, patient_auth):
    h = auth_header(admin_auth["token"])
    grant = client.post(
        "/api/v1/admin/membership/grant",
        headers=h,
        json={"patient_id": patient_auth["user_id"], "days": 30, "amount_paid": "0"},
    )
    assert grant.status_code == 200
    sub_id = grant.json()["id"]
    listed = client.get("/api/v1/admin/membership", headers=h)
    assert any(s["id"] == sub_id for s in listed.json())
    revoke = client.post(f"/api/v1/admin/membership/{sub_id}/revoke", headers=h)
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "cancelled"


def test_admin_activity_and_requires_auth(client, admin_auth):
    h = auth_header(admin_auth["token"])
    assert client.get("/api/v1/admin/activity/admin", headers=h).status_code == 200
    assert client.get("/api/v1/admin/dashboard").status_code == 401


def test_admin_verify_doctor_and_list_appointments(client, admin_auth, doctor_auth, patient_auth):
    h = auth_header(admin_auth["token"])
    doctors = client.get("/api/v1/admin/doctors", headers=h)
    assert doctors.status_code == 200
    assert any(d["id"] == doctor_auth["user_id"] for d in doctors.json())

    verified = client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=h,
        json={"is_verified": True},
    )
    assert verified.status_code == 200
    assert verified.json()["is_verified"] is True

    service = client.post(
        "/api/v1/doctor/services",
        headers=auth_header(doctor_auth["token"]),
        json={"name": "AdminListVisit", "price": "100.00"},
    ).json()
    from datetime import date, timedelta

    book = client.post(
        "/api/v1/appointments",
        headers=auth_header(patient_auth["token"]),
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=5)),
            "time_slot": "09:30",
            "service_id": service["id"],
        },
    )
    assert book.status_code == 200
    appts = client.get("/api/v1/admin/appointments", headers=h)
    assert appts.status_code == 200
    assert any(a["id"] == book.json()["id"] for a in appts.json())


def test_admin_create_admin_and_patch_hospital(client, admin_auth):
    h = auth_header(admin_auth["token"])
    created = client.post(
        "/api/v1/admin/admins",
        headers=h,
        json={
            "email": "viewer@test.icaremc.app",
            "password": "viewerpass1",
            "full_name": "Viewer",
            "admin_role": "viewer",
        },
    )
    assert created.status_code == 200, created.text
    admins = client.get("/api/v1/admin/admins", headers=h)
    assert any(a["email"] == "viewer@test.icaremc.app" for a in admins.json())

    hospital = client.post(
        "/api/v1/admin/hospitals",
        headers=h,
        json={"name": "St Paul", "slug": "st-paul", "city": "Addis"},
    )
    assert hospital.status_code == 200
    hid = hospital.json()["id"]
    patched = client.patch(
        f"/api/v1/admin/hospitals/{hid}",
        headers=h,
        json={"name": "St Paul Hospital", "slug": "st-paul", "city": "Addis Ababa"},
    )
    assert patched.status_code == 200
    assert patched.json()["city"] == "Addis Ababa"

    category = client.post(
        "/api/v1/admin/doctor-categories",
        headers=h,
        json={
            "name": "Cardiology",
            "slug": "cardiology",
            "care_focus": "both",
            "translations": [
                {"language_code": "en", "name": "Cardiology"},
                {"language_code": "am", "name": "የልብ ህክምና"},
            ],
        },
    )
    assert category.status_code == 200, category.text
    cid = category.json()["id"]
    patched_cat = client.patch(
        f"/api/v1/admin/doctor-categories/{cid}",
        headers=h,
        json={"name": "Heart Care", "slug": "heart-care", "sort_order": 3},
    )
    assert patched_cat.status_code == 200, patched_cat.text
    assert patched_cat.json()["name"] == "Heart Care"
    assert patched_cat.json()["sort_order"] == 3


def test_admin_cms_lists_and_payout_reject(client, admin_auth, doctor_auth, patient_auth):
    from datetime import date, timedelta
    from decimal import Decimal

    from tests.payment_helpers import pay_appointment

    h = auth_header(admin_auth["token"])
    assert client.get("/api/v1/admin/child-growth-periods", headers=h).status_code == 200
    assert client.get("/api/v1/admin/followup-templates", headers=h).status_code == 200
    assert client.get("/api/v1/admin/pregnancy-weeks", headers=h).status_code == 200
    assert client.get("/api/v1/admin/activity/platform", headers=h).status_code == 200
    assert client.get("/api/v1/admin/wallet-transactions", headers=h).status_code == 200
    assert client.get("/api/v1/admin/documents", headers=h).status_code == 200

    doctor_h = auth_header(doctor_auth["token"])
    client.post(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/verify",
        headers=h,
        json={"is_verified": True},
    )
    service = client.post(
        "/api/v1/doctor/services",
        headers=doctor_h,
        json={"name": "PayoutVisit", "price": "200.00"},
    ).json()
    appt = client.post(
        "/api/v1/appointments",
        headers=auth_header(patient_auth["token"]),
        json={
            "doctor_id": doctor_auth["user_id"],
            "appointment_date": str(date.today() + timedelta(days=6)),
            "time_slot": "15:00",
            "service_id": service["id"],
        },
    )
    assert appt.status_code == 200
    pay_appointment(client, patient_auth["token"], appt.json()["id"], "200.00")
    client.post(
        f"/api/v1/doctor/appointments/{appt.json()['id']}/status",
        headers=doctor_h,
        json={"status": "completed"},
    )
    method = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={
            "holder_name": "Doc Tor",
            "account_number": "1000999",
            "bank_name": "CBE",
            "is_default": True,
        },
    ).json()
    req = client.post(
        "/api/v1/doctor/payouts",
        headers=doctor_h,
        json={"amount": "50.00", "payout_method_id": method["id"]},
    )
    assert req.status_code == 200, req.text
    listed = client.get("/api/v1/admin/payout-requests", headers=h)
    assert any(r["id"] == req.json()["id"] for r in listed.json())
    rejected = client.post(
        f"/api/v1/admin/payout-requests/{req.json()['id']}",
        headers=h,
        json={"status": "rejected", "admin_note": "docs missing"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    wallet = client.get("/api/v1/doctor/wallet", headers=doctor_h).json()["wallet"]
    assert Decimal(wallet["available_balance"]) >= Decimal("200")


def test_admin_replace_doctor_booking(client, admin_auth, doctor_auth):
    h = auth_header(admin_auth["token"])
    doctor_id = doctor_auth["user_id"]
    res = client.patch(
        f"/api/v1/admin/doctors/{doctor_id}/booking",
        headers=h,
        json={
            "services": [
                {"name": "Admin consult", "price": "150.00", "is_active": True},
            ]
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "services" in body
    assert any(s["name"] == "Admin consult" for s in body["services"])


def test_admin_replace_doctor_booking_not_found(client, admin_auth):
    h = auth_header(admin_auth["token"])
    missing = "00000000-0000-4000-8000-000000000099"
    res = client.patch(
        f"/api/v1/admin/doctors/{missing}/booking",
        headers=h,
        json={"services": []},
    )
    assert res.status_code == 404


def test_admin_patch_appointment_status(client, admin_auth, doctor_auth, patient_auth):
    h = auth_header(admin_auth["token"])
    # create via doctor flow if appointments exist; otherwise skip gracefully
    listed = client.get("/api/v1/admin/appointments", headers=h)
    assert listed.status_code == 200
    rows = listed.json()
    if not rows:
        return
    appt_id = rows[0]["id"]
    res = client.patch(
        f"/api/v1/admin/appointments/{appt_id}",
        headers=h,
        json={"status": "confirmed"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "confirmed"


def test_admin_patch_admin_self_forbidden_role(client, admin_auth):
    h = auth_header(admin_auth["token"])
    me = admin_auth["user_id"]
    res = client.patch(
        f"/api/v1/admin/admins/{me}",
        headers=h,
        json={"admin_role": "viewer"},
    )
    assert res.status_code == 400


def test_admin_create_document_and_list_deliveries(client, admin_auth, doctor_auth):
    h = auth_header(admin_auth["token"])
    created = client.post(
        "/api/v1/admin/documents",
        headers=h,
        json={
            "title": "Clinic agreement",
            "category": "agreement",
            "storage_path": "/static/uploads/test.pdf",
            "file_name": "test.pdf",
            "mime_type": "application/pdf",
        },
    )
    assert created.status_code == 200, created.text
    doc_id = created.json()["id"]
    delivered = client.post(
        f"/api/v1/admin/documents/{doc_id}/deliver",
        headers=h,
        params={"recipient_id": doctor_auth["user_id"]},
    )
    assert delivered.status_code == 200, delivered.text
    history = client.get(
        f"/api/v1/admin/doctors/{doctor_auth['user_id']}/document-deliveries",
        headers=h,
    )
    assert history.status_code == 200
    assert any(row["document_id"] == doc_id for row in history.json())

def test_admin_referrals_and_commissions_empty(client, admin_auth):
    h = auth_header(admin_auth["token"])
    refs = client.get("/api/v1/admin/referrals", headers=h)
    assert refs.status_code == 200
    assert isinstance(refs.json(), list)

    commissions = client.get("/api/v1/admin/referral-commissions", headers=h)
    assert commissions.status_code == 200
    assert isinstance(commissions.json(), list)


def test_admin_referral_settings_via_settings_row(client, admin_auth):
    h = auth_header(admin_auth["token"])
    put = client.put(
        "/api/v1/admin/settings/referral",
        headers=h,
        json={"data": {"commissionPercent": 20}},
    )
    assert put.status_code == 200
    got = client.get("/api/v1/admin/settings/referral", headers=h)
    assert got.status_code == 200
    assert got.json()["data"]["commissionPercent"] == 20


def test_admin_doctor_referral_stats(client, admin_auth, doctor_auth):
    h = auth_header(admin_auth["token"])
    res = client.get(f"/api/v1/admin/doctors/{doctor_auth['user_id']}/referral-stats", headers=h)
    assert res.status_code == 200
    body = res.json()
    assert "referral_code" in body
    assert "referred_count" in body
    assert "total_commission" in body
def test_admin_get_appointment_not_found(client, admin_auth):
    h = auth_header(admin_auth["token"])
    missing = "00000000-0000-4000-8000-000000000099"
    res = client.get(f"/api/v1/admin/appointments/{missing}", headers=h)
    assert res.status_code == 404


def test_admin_list_children(client, admin_auth):
    h = auth_header(admin_auth["token"])
    res = client.get("/api/v1/admin/children", headers=h)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_admin_get_child_not_found(client, admin_auth):
    h = auth_header(admin_auth["token"])
    missing = "00000000-0000-4000-8000-000000000099"
    res = client.get(f"/api/v1/admin/children/{missing}", headers=h)
    assert res.status_code == 404


def test_admin_pregnancy_week_patch_delete(client, admin_auth):
    h = auth_header(admin_auth["token"])
    week = client.post(
        "/api/v1/admin/pregnancy-weeks",
        headers=h,
        json={"week_number": 20, "trimester": 2, "is_published": False},
    )
    assert week.status_code == 200, week.text
    week_id = week.json()["id"]

    patched = client.patch(
        f"/api/v1/admin/pregnancy-weeks/{week_id}",
        headers=h,
        json={"is_published": True, "image_note": "mid pregnancy"},
    )
    assert patched.status_code == 200
    assert patched.json()["is_published"] is True

    tr = client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h,
        json={"language_code": "en", "title": "Week 20"},
    )
    assert tr.status_code == 200
    tr2 = client.post(
        f"/api/v1/admin/pregnancy-weeks/{week_id}/translations",
        headers=h,
        json={"language_code": "en", "title": "Week 20 updated", "subtitle": "Halfway"},
    )
    assert tr2.status_code == 200
    assert tr2.json()["title"] == "Week 20 updated"

    deleted = client.delete(f"/api/v1/admin/pregnancy-weeks/{week_id}", headers=h)
    assert deleted.status_code == 204


def test_admin_child_growth_period_crud(client, admin_auth):
    h = auth_header(admin_auth["token"])
    created = client.post(
        "/api/v1/admin/child-growth-periods",
        headers=h,
        json={
            "age_months": 6,
            "age_label": "6 months",
            "age_group": "infant",
            "is_published": True,
            "translations": [
                {
                    "language_code": "en",
                    "title": "Six months",
                    "milestones": [{"key": "sit"}],
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    period_id = created.json()["id"]
    assert len(created.json()["child_growth_period_translations"]) == 1

    got = client.get(f"/api/v1/admin/child-growth-periods/{period_id}", headers=h)
    assert got.status_code == 200
    assert got.json()["age_months"] == 6

    patched = client.patch(
        f"/api/v1/admin/child-growth-periods/{period_id}",
        headers=h,
        json={
            "age_label": "Half year",
            "translations": [
                {"language_code": "en", "title": "Six months", "subtitle": "Sitting"},
                {"language_code": "am", "title": "ስድስት ወር"},
            ],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["age_label"] == "Half year"
    assert len(patched.json()["child_growth_period_translations"]) == 2

    deleted = client.delete(f"/api/v1/admin/child-growth-periods/{period_id}", headers=h)
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/admin/child-growth-periods/{period_id}", headers=h)
    assert missing.status_code == 404


def test_admin_followup_template_crud(client, admin_auth):
    h = auth_header(admin_auth["token"])
    created = client.post(
        "/api/v1/admin/followup-templates",
        headers=h,
        json={
            "code": "visit_test_6mo",
            "label": "6 month visit",
            "offset_months": 6,
            "is_published": True,
            "label_translations": {"en": {"name": "6 month visit"}},
        },
    )
    assert created.status_code == 200, created.text
    template_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/admin/followup-templates/{template_id}",
        headers=h,
        json={"label": "6-month check-up", "sort_order": 10},
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "6-month check-up"
    assert patched.json()["sort_order"] == 10

    deleted = client.delete(f"/api/v1/admin/followup-templates/{template_id}", headers=h)
    assert deleted.status_code == 204


def test_admin_daily_tips_crud(client, admin_auth):
    h = auth_header(admin_auth["token"])
    created = client.post(
        "/api/v1/admin/daily-tips",
        headers=h,
        json={
            "week_number": 8,
            "day_number": 3,
            "category": "nutrition",
            "is_active": True,
            "translations": [
                {
                    "language_code": "en",
                    "title": "Drink water",
                    "content": "Stay hydrated this week.",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    tip_id = created.json()["id"]
    assert created.json()["week_number"] == 8
    assert len(created.json()["daily_tip_translations"]) == 1

    listed = client.get("/api/v1/admin/daily-tips", headers=h)
    assert listed.status_code == 200
    assert any(row["id"] == tip_id for row in listed.json())

    got = client.get(f"/api/v1/admin/daily-tips/{tip_id}", headers=h)
    assert got.status_code == 200
    assert got.json()["day_number"] == 3

    patched = client.patch(
        f"/api/v1/admin/daily-tips/{tip_id}",
        headers=h,
        json={
            "is_active": False,
            "translations": [
                {
                    "language_code": "en",
                    "title": "Drink water",
                    "content": "Updated tip body.",
                },
                {
                    "language_code": "am",
                    "title": "Water am",
                    "content": "Updated am body.",
                },
            ],
        },
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    assert len(patched.json()["daily_tip_translations"]) == 2

    tr = client.post(
        f"/api/v1/admin/daily-tips/{tip_id}/translations",
        headers=h,
        json={"language_code": "om", "title": "Water om", "content": "Updated om body."},
    )
    assert tr.status_code == 200

    deleted = client.delete(f"/api/v1/admin/daily-tips/{tip_id}", headers=h)
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/admin/daily-tips/{tip_id}", headers=h)
    assert missing.status_code == 404
