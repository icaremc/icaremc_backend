from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    Appointment,
    DoctorAvailabilitySlot,
    DoctorPayoutMethod,
    DoctorPayoutRequest,
    DoctorProfile,
    DoctorReferral,
    DoctorReferralCommission,
    DoctorService,
    DoctorWallet,
    Hospital,
    WalletTransaction,
)

class PracticeRepository(Protocol):
    async def get_profile(self, user_id: UUID) -> DoctorProfile | None: ...
    async def require_profile(self, user_id: UUID) -> DoctorProfile: ...
    async def list_services(self, user_id: UUID) -> list[DoctorService]: ...
    async def get_service(self, service_id: UUID, user_id: UUID) -> DoctorService | None: ...
    async def open_bookings_for_service(self, service_id: UUID) -> int: ...
    async def delete(self, obj: object) -> None: ...
    async def list_slots(self, user_id: UUID) -> list[DoctorAvailabilitySlot]: ...
    async def get_slot(self, slot_id: UUID, user_id: UUID) -> DoctorAvailabilitySlot | None: ...
    async def get_wallet(self, user_id: UUID) -> DoctorWallet | None: ...
    async def list_wallet_txs(self, user_id: UUID) -> list[WalletTransaction]: ...
    async def list_payout_methods(self, user_id: UUID) -> list[DoctorPayoutMethod]: ...
    async def list_payouts(self, user_id: UUID) -> list[DoctorPayoutRequest]: ...
    async def list_referrals(self, user_id: UUID) -> list[DoctorReferral]: ...
    async def list_commissions(self, user_id: UUID) -> list[DoctorReferralCommission]: ...
    async def list_hospitals(self) -> list[Hospital]: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...
    @property
    def session(self) -> AsyncSession: ...


class SqlAlchemyPracticeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.session = db

    async def get_profile(self, user_id: UUID) -> DoctorProfile | None:
        return (await self.session.execute(select(DoctorProfile).where(DoctorProfile.id == user_id))).scalar_one_or_none()

    async def require_profile(self, user_id: UUID) -> DoctorProfile:
        return (await self.session.execute(select(DoctorProfile).where(DoctorProfile.id == user_id))).scalar_one()

    async def list_services(self, user_id: UUID) -> list[DoctorService]:
        return list(
            (await self.session.execute(select(DoctorService).where(DoctorService.doctor_id == user_id))).scalars().all()
        )

    async def get_service(self, service_id: UUID, user_id: UUID) -> DoctorService | None:
        return (
            await self.session.execute(
                select(DoctorService).where(DoctorService.id == service_id, DoctorService.doctor_id == user_id)
            )
        ).scalar_one_or_none()

    async def open_bookings_for_service(self, service_id: UUID) -> int:
        return int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Appointment)
                    .where(
                        Appointment.service_id == service_id,
                        Appointment.status.in_(["pending", "confirmed", "awaiting_patient_confirmation"]),
                    )
                )
            ).scalar_one()
        )

    async def delete(self, obj: object) -> None:
        await self.session.delete(obj)

    async def list_slots(self, user_id: UUID) -> list[DoctorAvailabilitySlot]:
        return list(
            (
                await self.session.execute(
                    select(DoctorAvailabilitySlot).where(DoctorAvailabilitySlot.doctor_id == user_id)
                )
            )
            .scalars()
            .all()
        )

    async def get_slot(self, slot_id: UUID, user_id: UUID) -> DoctorAvailabilitySlot | None:
        return (
            await self.session.execute(
                select(DoctorAvailabilitySlot).where(
                    DoctorAvailabilitySlot.id == slot_id,
                    DoctorAvailabilitySlot.doctor_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def get_wallet(self, user_id: UUID) -> DoctorWallet | None:
        return (await self.session.execute(select(DoctorWallet).where(DoctorWallet.doctor_id == user_id))).scalar_one_or_none()

    async def list_wallet_txs(self, user_id: UUID) -> list[WalletTransaction]:
        return list(
            (
                await self.session.execute(
                    select(WalletTransaction)
                    .where(WalletTransaction.doctor_id == user_id)
                    .order_by(WalletTransaction.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def list_payout_methods(self, user_id: UUID) -> list[DoctorPayoutMethod]:
        return list(
            (
                await self.session.execute(select(DoctorPayoutMethod).where(DoctorPayoutMethod.doctor_id == user_id))
            )
            .scalars()
            .all()
        )

    async def list_payouts(self, user_id: UUID) -> list[DoctorPayoutRequest]:
        return list(
            (
                await self.session.execute(select(DoctorPayoutRequest).where(DoctorPayoutRequest.doctor_id == user_id))
            )
            .scalars()
            .all()
        )

    async def list_referrals(self, user_id: UUID) -> list[DoctorReferral]:
        return list(
            (await self.session.execute(select(DoctorReferral).where(DoctorReferral.doctor_id == user_id))).scalars().all()
        )

    async def list_commissions(self, user_id: UUID) -> list[DoctorReferralCommission]:
        return list(
            (
                await self.session.execute(
                    select(DoctorReferralCommission).where(DoctorReferralCommission.doctor_id == user_id)
                )
            )
            .scalars()
            .all()
        )

    async def list_hospitals(self) -> list[Hospital]:
        return list(
            (await self.session.execute(select(Hospital).where(Hospital.is_active.is_(True)))).scalars().all()
        )

    def add(self, obj: object) -> None:
        self.session.add(obj)

    async def flush(self) -> None:
        await self.session.flush()


