from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

from tests.conftest import auth_header


def test_doctor_payout_method_crud_and_default_switch(client, doctor_auth):
    doctor_h = auth_header(doctor_auth["token"])

    # 1. Create first payout method as default
    m1 = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={
            "holder_name": "Dr. Smith",
            "account_number": "1000123456",
            "bank_name": "Commercial Bank of Ethiopia",
            "bank_code": "cbe",
            "is_default": True,
        },
    )
    assert m1.status_code == 200, m1.text
    m1_data = m1.json()
    assert m1_data["is_default"] is True
    assert m1_data["holder_name"] == "Dr. Smith"

    # 2. Create second payout method and set it as default
    m2 = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={
            "holder_name": "Dr. Smith Telebirr",
            "account_number": "0911223344",
            "bank_name": "Telebirr",
            "bank_code": "telebirr",
            "is_default": True,
        },
    )
    assert m2.status_code == 200
    m2_data = m2.json()
    assert m2_data["is_default"] is True

    # Check that m1 was automatically unset as default
    methods = client.get("/api/v1/doctor/payout-methods", headers=doctor_h).json()
    m1_refreshed = next(m for m in methods if m["id"] == m1_data["id"])
    assert m1_refreshed["is_default"] is False

    # 3. Update m1 using PATCH
    patch_res = client.patch(
        f"/api/v1/doctor/payout-methods/{m1_data['id']}",
        headers=doctor_h,
        json={"holder_name": "Dr. John Smith", "is_default": True},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["holder_name"] == "Dr. John Smith"
    assert patch_res.json()["is_default"] is True

    # 4. Delete m2
    del_res = client.delete(f"/api/v1/doctor/payout-methods/{m2_data['id']}", headers=doctor_h)
    assert del_res.status_code == 200
    methods_after = client.get("/api/v1/doctor/payout-methods", headers=doctor_h).json()
    assert not any(m["id"] == m2_data["id"] for m in methods_after)


def test_patient_payout_method_crud(client, patient_auth):
    patient_h = auth_header(patient_auth["token"])

    # 1. Create patient payout method
    res1 = client.post(
        "/api/v1/wallet/payout-methods",
        headers=patient_h,
        json={
            "holder_name": "Patient User",
            "account_number": "1000987654",
            "bank_name": "Awash Bank",
            "bank_code": "awash",
            "is_default": True,
        },
    )
    assert res1.status_code == 200, res1.text
    p1 = res1.json()
    assert p1["holder_name"] == "Patient User"
    assert p1["is_default"] is True

    # 2. List patient payout methods
    list_res = client.get("/api/v1/wallet/payout-methods", headers=patient_h)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Update patient payout method
    patch_res = client.patch(
        f"/api/v1/wallet/payout-methods/{p1['id']}",
        headers=patient_h,
        json={"holder_name": "Patient Jane User"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["holder_name"] == "Patient Jane User"

    # 4. Delete patient payout method
    del_res = client.delete(f"/api/v1/wallet/payout-methods/{p1['id']}", headers=patient_h)
    assert del_res.status_code == 200


def test_doctor_payout_approval_with_chapa_transfer(client, doctor_auth, admin_auth):
    doctor_h = auth_header(doctor_auth["token"])
    admin_h = auth_header(admin_auth["token"])

    # Setup doctor payout method
    method = client.post(
        "/api/v1/doctor/payout-methods",
        headers=doctor_h,
        json={
            "holder_name": "Dr. Transfer Test",
            "account_number": "1000555666",
            "bank_name": "CBE",
            "bank_code": "853",
            "is_default": True,
        },
    ).json()

    # Credit doctor wallet first to allow payout
    from tests.conftest import async_engine
    import asyncio
    from app.persistence.sqlalchemy.models import DoctorWallet
    from sqlalchemy import select

    async def _fund():
        from app.persistence.sqlalchemy.connection import async_session_factory
        async with async_session_factory() as sess:
            wallet = (await sess.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == doctor_auth["user_id"]))).scalar_one_or_none()
            if not wallet:
                wallet = DoctorWallet(doctor_id=doctor_auth["user_id"])
                sess.add(wallet)
            wallet.available_balance += Decimal("1000.00")
            await sess.commit()

    asyncio.run(_fund())

    # Request payout
    payout_res = client.post(
        "/api/v1/doctor/payouts",
        headers=doctor_h,
        json={"amount": "500.00", "payout_method_id": method["id"], "note": "Withdrawal 500"},
    )
    assert payout_res.status_code == 200, payout_res.text
    payout = payout_res.json()
    assert payout["status"] == "pending"

    # Admin approves and triggers Chapa transfer
    action_res = client.post(
        f"/api/v1/admin/payout-requests/{payout['id']}",
        headers=admin_h,
        json={"status": "completed", "admin_note": "Approved and transferred via Chapa"},
    )
    assert action_res.status_code == 200, action_res.text
    updated = action_res.json()
    assert updated["status"] == "completed"
    assert updated["chapa_transfer_reference"] is not None
    assert updated["chapa_transfer_reference"].startswith("doc-payout-")


def test_patient_withdrawal_and_admin_chapa_approval(client, patient_auth, admin_auth):
    patient_h = auth_header(patient_auth["token"])
    admin_h = auth_header(admin_auth["token"])

    # Create patient payout method
    method = client.post(
        "/api/v1/wallet/payout-methods",
        headers=patient_h,
        json={
            "holder_name": "Abebech Gobena",
            "account_number": "0911000000",
            "bank_name": "Telebirr",
            "bank_code": "telebirr",
            "is_default": True,
        },
    ).json()

    # Fund patient wallet
    import asyncio
    from app.persistence.sqlalchemy.models import PatientWallet
    from sqlalchemy import select

    async def _fund_patient():
        from app.persistence.sqlalchemy.connection import async_session_factory
        async with async_session_factory() as sess:
            wallet = (await sess.execute(select(PatientWallet).where(PatientWallet.patient_id == patient_auth["user_id"]))).scalar_one_or_none()
            if not wallet:
                wallet = PatientWallet(patient_id=patient_auth["user_id"])
                sess.add(wallet)
            wallet.balance += Decimal("800.00")
            await sess.commit()

    asyncio.run(_fund_patient())

    # Patient requests withdrawal
    withdraw_res = client.post(
        "/api/v1/wallet/withdraw",
        headers=patient_h,
        json={"amount": "300.00", "payout_method_id": method["id"], "note": "Cashout"},
    )
    assert withdraw_res.status_code == 200, withdraw_res.text
    req = withdraw_res.json()
    assert req["status"] == "pending"
    assert req["payout_method_id"] == method["id"]

    # Check patient withdrawals list
    my_withdrawals = client.get("/api/v1/wallet/withdrawals", headers=patient_h)
    assert my_withdrawals.status_code == 200
    assert any(w["id"] == req["id"] for w in my_withdrawals.json())

    # Admin reviews patient withdrawals
    admin_list = client.get("/api/v1/admin/patient-withdrawals", headers=admin_h)
    assert admin_list.status_code == 200
    assert any(w["id"] == req["id"] for w in admin_list.json())

    review = client.get(f"/api/v1/admin/patient-withdrawals/{req['id']}", headers=admin_h)
    assert review.status_code == 200
    assert review.json()["payout_method"]["holder_name"] == "Abebech Gobena"

    # Admin approves patient withdrawal with Chapa transfer
    approve_res = client.post(
        f"/api/v1/admin/patient-withdrawals/{req['id']}",
        headers=admin_h,
        json={"status": "completed", "admin_note": "Sent via Telebirr Chapa"},
    )
    assert approve_res.status_code == 200, approve_res.text
    approved = approve_res.json()
    assert approved["status"] == "completed"
    assert approved["chapa_transfer_reference"] is not None
    assert approved["chapa_transfer_reference"].startswith("pat-payout-")
