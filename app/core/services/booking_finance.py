from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    Appointment,
    AppSetting,
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
    # Only credit verified paid amount — never fall back to total_amount for unpaid bookings
    gross_amount = appt.amount_paid if appt.payment_status == "paid" else Decimal("0")
    if gross_amount <= 0:
        appt.status = "completed"
        await db.flush()
        return

    # Platform commission deduction configured under app_settings id="finance"
    finance = (
        await db.execute(select(AppSetting).where(AppSetting.id == "finance"))
    ).scalar_one_or_none()
    commission_percent = Decimal("0")
    if finance and isinstance(finance.data, dict):
        raw = finance.data.get("platformCommissionPercent", finance.data.get("platform_commission_percent", 10))
        try:
            commission_percent = Decimal(str(raw))
        except (ValueError, TypeError, ArithmeticError):
            commission_percent = Decimal("10")

    if commission_percent < Decimal("0"):
        commission_percent = Decimal("0")
    elif commission_percent > Decimal("100"):
        commission_percent = Decimal("100")

    commission_amount = (gross_amount * (commission_percent / Decimal("100"))).quantize(Decimal("0.01"))
    net_amount = gross_amount - commission_amount

    wallet = (await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == appt.doctor_id))).scalar_one_or_none()
    if wallet is None:
        wallet = DoctorWallet(doctor_id=appt.doctor_id)
        db.add(wallet)
        await db.flush()
    wallet.available_balance += net_amount

    note = None
    if commission_percent > 0:
        note = (
            f"Appointment fee ETB {gross_amount:.2f} less {commission_percent}% platform commission "
            f"(ETB {commission_amount:.2f})"
        )

    db.add(
        WalletTransaction(
            doctor_id=appt.doctor_id,
            amount=net_amount,
            is_credit=True,
            type="appointment_earning",
            appointment_id=appt.id,
            note=note,
        )
    )
    appt.status = "completed"
    await db.flush()


async def cancel_appointment(db: AsyncSession, appt: Appointment, *, cancelled_by: str) -> None:
    if appt.status == "cancelled":
        return
    paid = appt.amount_paid or Decimal("0")
    was_completed = appt.status == "completed"
    appt.status = "cancelled"
    appt.cancelled_by = cancelled_by

    if paid <= 0:
        await db.flush()
        return

    if cancelled_by == "patient":
        await _refund_patient(db, appt, paid)
        appt.payment_status = "refunded"
        await db.flush()
        return

    if cancelled_by == "doctor":
        # ponytail: never mint patient credit without a funding source
        if was_completed:
            wallet = (
                await db.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == appt.doctor_id))
            ).scalar_one_or_none()
            earning_tx = (
                await db.execute(
                    select(WalletTransaction).where(
                        WalletTransaction.appointment_id == appt.id,
                        WalletTransaction.type == "appointment_earning",
                    )
                )
            ).scalar_one_or_none()
            clawback = earning_tx.amount if earning_tx else paid
            if wallet is None or wallet.available_balance < clawback:
                raise ValueError("Insufficient doctor balance to refund patient")
            wallet.available_balance -= clawback
            db.add(
                WalletTransaction(
                    doctor_id=appt.doctor_id,
                    amount=clawback,
                    is_credit=False,
                    type="cancel_penalty",
                    appointment_id=appt.id,
                )
            )
        await _refund_patient(db, appt, paid)
        appt.payment_status = "refunded"
    await db.flush()


async def _refund_patient(db: AsyncSession, appt: Appointment, paid: Decimal) -> None:
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
