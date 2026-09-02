from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security.tokens import create_access_token, hash_password, verify_password
from app.core.services.booking_finance import cancel_appointment, credit_doctor_on_complete
from app.core.services.sms_otp import normalize_phone
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import (
    Appointment,
    DoctorProfile,
    DoctorWallet,
    PatientWallet,
    Profile,
    User,
)


def test_normalize_phone():
    assert normalize_phone("0912345678") == "251912345678"
    assert normalize_phone("+251911000000") == "251911000000"


def test_password_hash_roundtrip():
    hashed = hash_password("abc12345")
    assert verify_password("abc12345", hashed)
    assert not verify_password("nope", hashed)


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
