from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    Appointment,
    DoctorWallet,
    PatientWallet,
    PatientWalletTransaction,
    WalletTransaction,
)


async def credit_doctor_on_complete(db: AsyncSession, appt: Appointment) -> None:
    if appt.status == "completed":
        return
    existing = (
        await db.execute(
            select(WalletTransaction).where(
                WalletTransaction.appointment_id == appt.id,
                WalletTransaction.type == "appointment_earning",
            )
        )
    ).scalar_one_or_none()
    if existing:
        return
    amount = appt.amount_paid or appt.total_amount or Decimal("0")
    if amount <= 0:
        appt.status = "completed"
        await db.flush()
        return
    wallet = (await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == appt.doctor_id))).scalar_one_or_none()
    if wallet is None:
        wallet = DoctorWallet(doctor_id=appt.doctor_id)
        db.add(wallet)
        await db.flush()
    wallet.available_balance += amount
    db.add(
        WalletTransaction(
            doctor_id=appt.doctor_id,
            amount=amount,
            is_credit=True,
            type="appointment_earning",
            appointment_id=appt.id,
        )
    )
    appt.status = "completed"
    await db.flush()


async def cancel_appointment(db: AsyncSession, appt: Appointment, *, cancelled_by: str) -> None:
    if appt.status == "cancelled":
        return
    appt.status = "cancelled"
    appt.cancelled_by = cancelled_by
    paid = appt.amount_paid or Decimal("0")
    if cancelled_by == "patient" and paid > 0:
        wallet = (
            await db.execute(select(PatientWallet).where(PatientWallet.patient_id == appt.patient_id))
        ).scalar_one_or_none()
        if wallet is None:
            wallet = PatientWallet(patient_id=appt.patient_id)
            db.add(wallet)
            await db.flush()
        wallet.balance += paid
        db.add(
            PatientWalletTransaction(
                patient_id=appt.patient_id,
                amount=paid,
                is_credit=True,
                type="appointment_refund",
                appointment_id=appt.id,
            )
        )
        appt.payment_status = "waived"
    if cancelled_by == "doctor" and paid > 0:
        wallet = (
            await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == appt.doctor_id))
        ).scalar_one_or_none()
        if wallet and wallet.available_balance >= paid:
            wallet.available_balance -= paid
            db.add(
                WalletTransaction(
                    doctor_id=appt.doctor_id,
                    amount=paid,
                    is_credit=False,
                    type="cancel_penalty",
                    appointment_id=appt.id,
                )
            )
        patient_wallet = (
            await db.execute(select(PatientWallet).where(PatientWallet.patient_id == appt.patient_id))
        ).scalar_one_or_none()
        if patient_wallet is None:
            patient_wallet = PatientWallet(patient_id=appt.patient_id)
            db.add(patient_wallet)
            await db.flush()
        patient_wallet.balance += paid
        db.add(
            PatientWalletTransaction(
                patient_id=appt.patient_id,
                amount=paid,
                is_credit=True,
                type="appointment_refund",
                appointment_id=appt.id,
            )
        )
    await db.flush()


async def request_doctor_payout(
    db: AsyncSession,
    *,
    doctor_id,
    amount: Decimal,
    payout_method_id,
    note: str | None = None,
):
    from app.persistence.sqlalchemy.models import DoctorPayoutRequest

    wallet = (await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == doctor_id))).scalar_one_or_none()
    if wallet is None or wallet.available_balance < amount:
        raise ValueError("Insufficient balance")
    wallet.available_balance -= amount
    wallet.pending_balance += amount
    req = DoctorPayoutRequest(
        doctor_id=doctor_id,
        payout_method_id=payout_method_id,
        amount=amount,
        note=note,
        status="pending",
    )
    db.add(req)
    await db.flush()
    db.add(
        WalletTransaction(
            doctor_id=doctor_id,
            amount=amount,
            is_credit=False,
            type="payout_hold",
            payout_request_id=req.id,
        )
    )
    await db.flush()
    return req
