from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import PatientWallet, PatientWalletTransaction


class WalletRepository(Protocol):
    async def get_patient_wallet(self, user_id: UUID) -> PatientWallet | None: ...
    async def list_patient_txs(self, user_id: UUID) -> list[PatientWalletTransaction]: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyWalletRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
