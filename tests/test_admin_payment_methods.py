from decimal import Decimal
import uuid

from tests.conftest import auth_header


def test_admin_fetch_payment_methods(client, doctor_auth, patient_auth, admin_auth):
    doctor_h = auth_header(doctor_auth["token"])
    patient_h = auth_header(patient_auth["token"])
    admin_h = auth_header(admin_auth["token"])

    # 1. Create a doctor payout method
    doc_pm_res = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={
            "holder_name": "Dr. Admin Test",
            "account_number": "1000998877",
            "bank_name": "Commercial Bank of Ethiopia",
            "bank_code": "cbe",
            "is_default": True,
        },
    )
    assert doc_pm_res.status_code == 200, doc_pm_res.text
    doc_pm = doc_pm_res.json()
    doc_pm_id = doc_pm["id"]

    # 2. Create a patient payout method
    pat_pm_res = client.post(
        "/api/v1/wallet/payout-methods",
        headers=patient_h,
        json={
            "holder_name": "Patient Admin Test",
            "account_number": "0911554433",
            "bank_name": "Telebirr",
            "bank_code": "telebirr",
            "is_default": True,
        },
    )
    assert pat_pm_res.status_code == 200, pat_pm_res.text
    pat_pm = pat_pm_res.json()
    pat_pm_id = pat_pm["id"]

    # 3. Test Admin fetching doctor payment method using method id
    # /api/v1/admin/payment-methods/{id}
    res = client.get(f"/api/v1/admin/payment-methods/{doc_pm_id}", headers=admin_h)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == doc_pm_id
    assert data["holder_name"] == "Dr. Admin Test"
    assert data["bank_name"] == "Commercial Bank of Ethiopia"
    assert data["account_number"] == "1000998877"
    assert data["user_type"] == "doctor"
    assert data["doctor_id"] == doctor_auth["user_id"]

    # /api/v1/admin/payout-methods/{id} alias
    alias_res = client.get(f"/api/v1/admin/payout-methods/{doc_pm_id}", headers=admin_h)
    assert alias_res.status_code == 200
    assert alias_res.json()["id"] == doc_pm_id

    # 4. Test Admin fetching patient payment method using method id
    res_pat = client.get(f"/api/v1/admin/payment-methods/{pat_pm_id}", headers=admin_h)
    assert res_pat.status_code == 200, res_pat.text
    pat_data = res_pat.json()
    assert pat_data["id"] == pat_pm_id
    assert pat_data["holder_name"] == "Patient Admin Test"
    assert pat_data["bank_name"] == "Telebirr"
    assert pat_data["user_type"] == "patient"
    assert pat_data["patient_id"] == patient_auth["user_id"]

    # 5. Test Admin fetching payment methods using user's ID
    # Passing doctor_id to /admin/payment-methods/{id}
    res_by_doc_id = client.get(f"/api/v1/admin/payment-methods/{doctor_auth['user_id']}", headers=admin_h)
    assert res_by_doc_id.status_code == 200
    doc_methods = res_by_doc_id.json()
    assert isinstance(doc_methods, list)
    assert any(m["id"] == doc_pm_id for m in doc_methods)

    # Passing patient_id to /admin/payment-methods/{id}
    res_by_pat_id = client.get(f"/api/v1/admin/payment-methods/{patient_auth['user_id']}", headers=admin_h)
    assert res_by_pat_id.status_code == 200
    pat_methods = res_by_pat_id.json()
    assert isinstance(pat_methods, list)
    assert any(m["id"] == pat_pm_id for m in pat_methods)

    # 6. Test specific user payment-methods endpoints
    res_user_methods = client.get(f"/api/v1/admin/users/{patient_auth['user_id']}/payment-methods", headers=admin_h)
    assert res_user_methods.status_code == 200
    assert any(m["id"] == pat_pm_id for m in res_user_methods.json())

    res_doc_methods = client.get(f"/api/v1/admin/doctors/{doctor_auth['user_id']}/payment-methods", headers=admin_h)
    assert res_doc_methods.status_code == 200
    assert any(m["id"] == doc_pm_id for m in res_doc_methods.json())

    # 7. Test Admin listing / filtering payment methods
    res_filter_doc = client.get(f"/api/v1/admin/payment-methods?doctor_id={doctor_auth['user_id']}", headers=admin_h)
    assert res_filter_doc.status_code == 200
    assert any(m["id"] == doc_pm_id for m in res_filter_doc.json())

    res_filter_pat = client.get(f"/api/v1/admin/payment-methods?patient_id={patient_auth['user_id']}", headers=admin_h)
    assert res_filter_pat.status_code == 200
    assert any(m["id"] == pat_pm_id for m in res_filter_pat.json())

    # 8. Test /api/v1/payments/payment-methods/{id} endpoint
    payments_res = client.get(f"/api/v1/payments/payment-methods/{doc_pm_id}", headers=admin_h)
    assert payments_res.status_code == 200
    assert payments_res.json()["id"] == doc_pm_id

    # 9. Test non-existent ID returns 404
    random_id = str(uuid.uuid4())
    res_404 = client.get(f"/api/v1/admin/payment-methods/{random_id}", headers=admin_h)
    assert res_404.status_code == 404

    # 10. Security: Non-admin users cannot access admin payment-methods endpoints
    res_forbidden_doc = client.get(f"/api/v1/admin/payment-methods/{doc_pm_id}", headers=doctor_h)
    assert res_forbidden_doc.status_code == 403

    res_forbidden_pat = client.get(f"/api/v1/admin/payment-methods/{pat_pm_id}", headers=patient_h)
    assert res_forbidden_pat.status_code == 403

    res_unauth = client.get(f"/api/v1/admin/payment-methods/{doc_pm_id}")
    assert res_unauth.status_code == 401


def test_admin_patient_withdrawals_filters_and_pagination(client, patient_auth, admin_auth):
    patient_h = auth_header(patient_auth["token"])
    admin_h = auth_header(admin_auth["token"])

    # 1. Create payout method
    pm = client.post(
        "/api/v1/wallet/payout-methods",
        headers=patient_h,
        json={
            "holder_name": "Abebech Filter Test",
            "account_number": "0911778899",
            "bank_name": "Telebirr",
            "bank_code": "telebirr",
            "is_default": True,
        },
    ).json()

    # 2. Fund patient wallet
    import asyncio
    from app.persistence.sqlalchemy.models import PatientWallet
    from sqlalchemy import select

    async def _fund():
        from app.persistence.sqlalchemy.connection import async_session_factory
        async with async_session_factory() as sess:
            wallet = (await sess.execute(select(PatientWallet).where(PatientWallet.patient_id == patient_auth["user_id"]))).scalar_one_or_none()
            if not wallet:
                wallet = PatientWallet(patient_id=patient_auth["user_id"])
                sess.add(wallet)
            wallet.balance += Decimal("10000.00")
            await sess.commit()

    asyncio.run(_fund())

    # 3. Create three withdrawal requests with different amounts and notes
    w1 = client.post(
        "/api/v1/wallet/withdraw",
        headers=patient_h,
        json={"amount": "100.00", "payout_method_id": pm["id"], "note": "School fee request"},
    ).json()

    w2 = client.post(
        "/api/v1/wallet/withdraw",
        headers=patient_h,
        json={"amount": "250.00", "payout_method_id": pm["id"], "note": "Medical emergency urgent"},
    ).json()

    w3 = client.post(
        "/api/v1/wallet/withdraw",
        headers=patient_h,
        json={"amount": "500.00", "payout_method_id": pm["id"], "note": "House rent"},
    ).json()

    # 4. Default listing returns list and includes X-Total-Count header
    res_all = client.get("/api/v1/admin/patient-withdrawals", headers=admin_h)
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert isinstance(all_data, list)
    assert len(all_data) >= 3
    assert "X-Total-Count" in res_all.headers
    assert int(res_all.headers["X-Total-Count"]) >= 3

    # Check enrichment fields
    first_item = all_data[0]
    assert "patient_name" in first_item
    assert "patient_phone" in first_item
    assert "payout_method" in first_item

    # 5. Filter by status
    res_status = client.get("/api/v1/admin/patient-withdrawals?status=pending", headers=admin_h)
    assert res_status.status_code == 200
    assert all(w["status"] == "pending" for w in res_status.json())

    # 6. Filter by patient_id
    res_patient = client.get(f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}", headers=admin_h)
    assert res_patient.status_code == 200
    assert all(w["patient_id"] == patient_auth["user_id"] for w in res_patient.json())

    # 7. Filter by payout_method_id
    res_pm = client.get(f"/api/v1/admin/patient-withdrawals?payout_method_id={pm['id']}", headers=admin_h)
    assert res_pm.status_code == 200
    assert all(w["payout_method_id"] == pm["id"] for w in res_pm.json())

    # 8. Filter by min_amount and max_amount
    res_amount = client.get(
        f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}&min_amount=200&max_amount=300",
        headers=admin_h,
    )
    assert res_amount.status_code == 200
    amount_data = res_amount.json()
    assert len(amount_data) == 1
    assert float(amount_data[0]["amount"]) == 250.0

    # 9. Search filter
    res_search = client.get(
        f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}&search=urgent",
        headers=admin_h,
    )
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert len(search_data) == 1
    assert "emergency urgent" in search_data[0]["note"]

    # 10. Pagination with limit and offset
    res_p1 = client.get(
        f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}&limit=1&offset=0",
        headers=admin_h,
    )
    assert res_p1.status_code == 200
    p1_items = res_p1.json()
    assert len(p1_items) == 1
    assert res_p1.headers["X-Limit"] == "1"
    assert res_p1.headers["X-Offset"] == "0"

    res_p2 = client.get(
        f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}&limit=1&offset=1",
        headers=admin_h,
    )
    assert res_p2.status_code == 200
    p2_items = res_p2.json()
    assert len(p2_items) == 1
    assert p1_items[0]["id"] != p2_items[0]["id"]

    # 11. Pagination with page and page_size
    res_page = client.get(
        f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}&page=2&page_size=1",
        headers=admin_h,
    )
    assert res_page.status_code == 200
    page_items = res_page.json()
    assert len(page_items) == 1
    assert page_items[0]["id"] == p2_items[0]["id"]

    # 12. Envelope response format
    res_envelope = client.get(
        f"/api/v1/admin/patient-withdrawals?patient_id={patient_auth['user_id']}&envelope=true&limit=2",
        headers=admin_h,
    )
    assert res_envelope.status_code == 200
    env_data = res_envelope.json()
    assert "withdrawals" in env_data
    assert "total" in env_data
    assert env_data["total"] == 3
    assert len(env_data["withdrawals"]) == 2
    assert env_data["limit"] == 2
    assert env_data["offset"] == 0
