from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import Appointment, AppSubscription, CareSubscription, DoctorService


class PaymentRepository(Protocol):
    async def get_patient_appointment(self, appointment_id: UUID, patient_id: UUID) -> Appointment | None: ...
    async def get_appointment_by_tx(self, tx_ref: str) -> Appointment | None: ...
    async def get_app_sub_by_tx(self, tx_ref: str) -> AppSubscription | None: ...
    async def get_care_sub_by_tx(self, tx_ref: str) -> CareSubscription | None: ...
    async def get_service(self, service_id: UUID) -> DoctorService: ...
    async def find_payout_by_reference(self, reference: str) -> object | None: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...
    @property
    def session(self) -> AsyncSession: ...


class SqlAlchemyPaymentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self.session = db

    async def get_patient_appointment(self, appointment_id: UUID, patient_id: UUID) -> Appointment | None:
        return (
            await self._db.execute(
                select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == patient_id)
            )
        ).scalar_one_or_none()

    async def get_appointment_by_tx(self, tx_ref: str) -> Appointment | None:
        return (await self._db.execute(select(Appointment).where(Appointment.chapa_tx_ref == tx_ref))).scalar_one_or_none()

    async def get_app_sub_by_tx(self, tx_ref: str) -> AppSubscription | None:
        return (
            await self._db.execute(select(AppSubscription).where(AppSubscription.chapa_tx_ref == tx_ref))
        ).scalar_one_or_none()

    async def get_care_sub_by_tx(self, tx_ref: str) -> CareSubscription | None:
        return (
            await self._db.execute(select(CareSubscription).where(CareSubscription.chapa_tx_ref == tx_ref))
        ).scalar_one_or_none()

    async def get_service(self, service_id: UUID) -> DoctorService:
        return (await self._db.execute(select(DoctorService).where(DoctorService.id == service_id))).scalar_one()

    async def find_payout_by_reference(self, reference: str) -> object | None:
        from app.persistence.sqlalchemy.models import DoctorPayoutRequest, PatientWalletWithdrawalRequest
        doc = (
            await self._db.execute(
                select(DoctorPayoutRequest).where(DoctorPayoutRequest.chapa_transfer_reference == reference)
            )
        ).scalar_one_or_none()
        if doc is not None:
            return doc
        pat = (
            await self._db.execute(
                select(PatientWalletWithdrawalRequest).where(
                    PatientWalletWithdrawalRequest.chapa_transfer_reference == reference
                )
            )
        ).scalar_one_or_none()
        return pat

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
