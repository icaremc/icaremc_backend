from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security.tokens import (
    create_access_token,
    hash_password,
    verify_and_update_password,
    verify_password,
)
from app.core.services.booking_finance import cancel_appointment, credit_doctor_on_complete
from app.core.services.sms_otp import normalize_phone
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import (
    Appointment,
    AppSetting,
    DoctorProfile,
    DoctorWallet,
    PatientWallet,
    Profile,
    User,
    WalletTransaction,
)


def test_normalize_phone():
    assert normalize_phone("0912345678") == "251912345678"
    assert normalize_phone("+251911000000") == "251911000000"


def test_password_hash_roundtrip():
    hashed = hash_password("abc12345")
    assert hashed.startswith("$argon2id$")
    assert verify_password("abc12345", hashed)
    assert not verify_password("nope", hashed)


def test_legacy_bcrypt_verification_and_upgrade():
    import bcrypt

    raw_password = "mySecretPassword123!"
    legacy_hash = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()
    assert legacy_hash.startswith(("$2a$", "$2b$"))

    # Can verify directly
    assert verify_password(raw_password, legacy_hash)
    assert not verify_password("wrong_password", legacy_hash)

    # verify_and_update verifies and returns new argon2 hash
    valid, updated_hash = verify_and_update_password(raw_password, legacy_hash)
    assert valid is True
    assert updated_hash is not None
    assert updated_hash.startswith("$argon2id$")
    # Newly upgraded hash verifies correctly
    assert verify_password(raw_password, updated_hash)

    # Calling verify_and_update on an already up-to-date Argon2 hash should not rehash
    valid_again, no_update = verify_and_update_password(raw_password, updated_hash)
    assert valid_again is True
    assert no_update is None


def test_jwt_contains_role():
    import jwt
    from app.config import MySettings

    uid = uuid4()
    token = create_access_token(sub=uid, role="patient")
    payload = jwt.decode(token, MySettings.JWT_SECRET, algorithms=[MySettings.JWT_ALGORITHM])
    assert payload["sub"] == str(uid)
    assert payload["role"] == "patient"


def test_credit_and_cancel_patient(client):
    # uses client fixture so schema/truncate are ready; run finance logic in TestClient's loop via sync helpers
    import asyncio

    async def _run() -> None:
        async with async_session_factory() as db:
            patient = User(
                phone=f"p-{uuid4().hex[:10]}",
                password_hash=hash_password("x"),
                role="patient",
                roles=["patient"],
            )
            doctor = User(
                phone=f"d-{uuid4().hex[:10]}",
                password_hash=hash_password("x"),
                role="doctor",
                roles=["doctor"],
            )
            db.add_all([patient, doctor])
            await db.flush()
            db.add(Profile(id=patient.id, full_name="P", phone=patient.phone))
            db.add(
                DoctorProfile(
                    id=doctor.id,
                    first_name="D",
                    last_name="R",
                    specialty="G",
                    hospital="",
                    referral_code=f"T{uuid4().hex[:6].upper()}",
                )
            )
            await db.flush()
            db.add(PatientWallet(patient_id=patient.id, balance=Decimal("0")))
            db.add(DoctorWallet(doctor_id=doctor.id, available_balance=Decimal("0")))
            appt = Appointment(
                doctor_id=doctor.id,
                patient_id=patient.id,
                appointment_date=date.today() + timedelta(days=1),
                time_slot="09:00",
                status="confirmed",
                total_amount=Decimal("200"),
                amount_paid=Decimal("200"),
                payment_status="paid",
            )
            db.add(appt)
            await db.flush()

            await credit_doctor_on_complete(db, appt)
            await db.refresh(appt)
            assert appt.status == "completed"
            wallet = await db.get(DoctorWallet, doctor.id)
            assert wallet is not None
            assert wallet.available_balance == Decimal("200")

            appt2 = Appointment(
                doctor_id=doctor.id,
                patient_id=patient.id,
                appointment_date=date.today() + timedelta(days=2),
                time_slot="10:00",
                status="confirmed",
                total_amount=Decimal("100"),
                amount_paid=Decimal("100"),
                payment_status="paid",
            )
            db.add(appt2)
            await db.flush()
            await cancel_appointment(db, appt2, cancelled_by="patient")
            await db.refresh(appt2)
            assert appt2.status == "cancelled"
            pw = await db.get(PatientWallet, patient.id)
            assert pw is not None
            assert pw.balance == Decimal("100")
            await db.commit()

    asyncio.run(_run())


def test_platform_commission_deduction_and_cancellation(client):
    import asyncio
    from sqlalchemy import select

    async def _run() -> None:
        async with async_session_factory() as db:
            # Seed 10% platform commission setting
            db.add(AppSetting(id="finance", data={"platformCommissionPercent": 10}))

            user_d = User(
                phone=f"d-{uuid4().hex[:10]}",
                password_hash=hash_password("x"),
                role="doctor",
                roles=["doctor"],
            )
            user_p = User(
                phone=f"p-{uuid4().hex[:10]}",
                password_hash=hash_password("x"),
                role="patient",
                roles=["patient"],
            )
            db.add_all([user_d, user_p])
            await db.flush()

            doctor = DoctorProfile(
                id=user_d.id,
                first_name="Doc",
                last_name="Commission",
                specialty="General",
                hospital="Test Clinic",
                referral_code=f"C{uuid4().hex[:6].upper()}",
            )
            patient = Profile(id=user_p.id, full_name="Pat Commission", phone=user_p.phone)
            db.add_all([doctor, patient])
            await db.flush()

            db.add(DoctorWallet(doctor_id=doctor.id, available_balance=Decimal("0")))
            db.add(PatientWallet(patient_id=patient.id, balance=Decimal("0")))

            # Appointment with 500 ETB paid
            appt = Appointment(
                doctor_id=doctor.id,
                patient_id=patient.id,
                appointment_date=date.today() + timedelta(days=1),
                time_slot="11:00",
                status="confirmed",
                total_amount=Decimal("500"),
                amount_paid=Decimal("500"),
                payment_status="paid",
            )
            db.add(appt)
            await db.flush()

            # Credit doctor on complete -> 10% commission deducted: 500 - 50 = 450 ETB net
            await credit_doctor_on_complete(db, appt)
            await db.refresh(appt)
            assert appt.status == "completed"

            wallet = await db.get(DoctorWallet, doctor.id)
            assert wallet is not None
            assert wallet.available_balance == Decimal("450.00")

            tx = (
                await db.execute(
                    select(WalletTransaction).where(
                        WalletTransaction.appointment_id == appt.id,
                        WalletTransaction.type == "appointment_earning",
                    )
                )
            ).scalar_one()
            assert tx.amount == Decimal("450.00")
            assert tx.is_credit is True
            assert "10% platform commission" in (tx.note or "")
            assert "ETB 50.00" in (tx.note or "")

            # Doctor cancels after completion -> clawback is the net 450, patient refunded full 500
            await cancel_appointment(db, appt, cancelled_by="doctor")
            await db.refresh(wallet)
            assert wallet.available_balance == Decimal("0.00")

            pw = await db.get(PatientWallet, patient.id)
            assert pw is not None
            assert pw.balance == Decimal("500.00")

            cancel_tx = (
                await db.execute(
                    select(WalletTransaction).where(
                        WalletTransaction.appointment_id == appt.id,
                        WalletTransaction.type == "cancel_penalty",
                    )
                )
            ).scalar_one()
            assert cancel_tx.amount == Decimal("450.00")
            assert cancel_tx.is_credit is False

            await db.commit()

    asyncio.run(_run())
