from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    PatientPayoutMethod,
    PatientWallet,
    PatientWalletTransaction,
    PatientWalletWithdrawalRequest,
)


class WalletRepository(Protocol):
    async def get_patient_wallet(self, user_id: UUID) -> PatientWallet | None: ...
    async def list_patient_txs(self, user_id: UUID) -> list[PatientWalletTransaction]: ...
    async def list_payout_methods(self, user_id: UUID) -> list[PatientPayoutMethod]: ...
    async def get_payout_method(self, method_id: UUID, user_id: UUID) -> PatientPayoutMethod | None: ...
    async def unset_default_payout_methods(self, user_id: UUID, exclude_id: UUID | None = None) -> None: ...
    async def list_withdrawals(self, user_id: UUID) -> list[PatientWalletWithdrawalRequest]: ...
    async def get_withdrawal(self, request_id: UUID, user_id: UUID) -> PatientWalletWithdrawalRequest | None: ...
    async def delete(self, obj: object) -> None: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...
    @property
    def session(self) -> AsyncSession: ...


class SqlAlchemyWalletRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @property
    def session(self) -> AsyncSession:
        return self._db

    async def get_patient_wallet(self, user_id: UUID) -> PatientWallet | None:
        return (
            await self._db.execute(select(PatientWallet).where(PatientWallet.patient_id == user_id))
        ).scalar_one_or_none()

    async def list_patient_txs(self, user_id: UUID) -> list[PatientWalletTransaction]:
        return list(
            (
                await self._db.execute(
                    select(PatientWalletTransaction)
                    .where(PatientWalletTransaction.patient_id == user_id)
                    .order_by(PatientWalletTransaction.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def list_payout_methods(self, user_id: UUID) -> list[PatientPayoutMethod]:
        return list(
            (
                await self._db.execute(
                    select(PatientPayoutMethod)
                    .where(PatientPayoutMethod.patient_id == user_id)
                    .order_by(PatientPayoutMethod.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def get_payout_method(self, method_id: UUID, user_id: UUID) -> PatientPayoutMethod | None:
        return (
            await self._db.execute(
                select(PatientPayoutMethod).where(
                    PatientPayoutMethod.id == method_id,
                    PatientPayoutMethod.patient_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def unset_default_payout_methods(self, user_id: UUID, exclude_id: UUID | None = None) -> None:
        stmt = select(PatientPayoutMethod).where(
            PatientPayoutMethod.patient_id == user_id,
            PatientPayoutMethod.is_default.is_(True),
        )
        if exclude_id is not None:
            stmt = stmt.where(PatientPayoutMethod.id != exclude_id)
        for m in (await self._db.execute(stmt)).scalars().all():
            m.is_default = False

    async def list_withdrawals(self, user_id: UUID) -> list[PatientWalletWithdrawalRequest]:
        return list(
            (
                await self._db.execute(
                    select(PatientWalletWithdrawalRequest)
                    .where(PatientWalletWithdrawalRequest.patient_id == user_id)
                    .order_by(PatientWalletWithdrawalRequest.created_at.desc())
                )
            )
            .scalars()
            .all()
        )

    async def get_withdrawal(self, request_id: UUID, user_id: UUID) -> PatientWalletWithdrawalRequest | None:
        return (
            await self._db.execute(
                select(PatientWalletWithdrawalRequest).where(
                    PatientWalletWithdrawalRequest.id == request_id,
                    PatientWalletWithdrawalRequest.patient_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def delete(self, obj: object) -> None:
        await self._db.delete(obj)

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
