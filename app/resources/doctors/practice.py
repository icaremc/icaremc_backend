from uuid import UUID

from app.api.v1.schemas import OkOut, RowOut, WalletBundleOut
from app.core.services.booking_finance import request_doctor_payout
from app.persistence.sqlalchemy.models import (
    DoctorAvailabilitySlot,
    DoctorHospitalAffiliation,
    DoctorPayoutMethod,
    DoctorService,
)
from app.resources.doctors.practice_repository import PracticeRepository
from app.resources.doctors.practice_schemas import (
    PayoutIn,
    PayoutMethodIn,
    ProfileUpdate,
    ServiceIn,
    SlotIn,
)
from app.resources.errors import bad_request, not_found
from app.resources.serialize import require_row, to_row, to_rows


class PracticeService:
    def __init__(self, repo: PracticeRepository) -> None:
        self._repo = repo

    async def me(self, user_id: UUID) -> RowOut:
        row = await self._repo.get_profile(user_id)
        if row is None:
            raise not_found()
        return require_row(row)

    async def patch_me(self, user_id: UUID, body: ProfileUpdate) -> RowOut:
        row = await self._repo.require_profile(user_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self._repo.flush()
        return require_row(row)

    async def list_services(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_services(user_id))

    async def create_service(self, user_id: UUID, body: ServiceIn) -> RowOut:
        row = DoctorService(doctor_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def patch_service(self, service_id: UUID, user_id: UUID, body: ServiceIn) -> RowOut:
        row = await self._repo.get_service(service_id, user_id)
        if row is None:
            raise not_found()
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self._repo.flush()
        return require_row(row)

    async def delete_service(self, service_id: UUID, user_id: UUID) -> OkOut:
        if await self._repo.open_bookings_for_service(service_id):
            raise bad_request("Service has open bookings")
        row = await self._repo.get_service(service_id, user_id)
        if row is None:
            raise not_found()
        await self._repo.delete(row)
        await self._repo.flush()
        return OkOut()

    async def list_slots(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_slots(user_id))

    async def create_slot(self, user_id: UUID, body: SlotIn) -> RowOut:
        row = DoctorAvailabilitySlot(doctor_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def delete_slot(self, slot_id: UUID, user_id: UUID) -> OkOut:
        row = await self._repo.get_slot(slot_id, user_id)
        if row is None:
            raise not_found()
        await self._repo.delete(row)
        await self._repo.flush()
        return OkOut()

    async def wallet(self, user_id: UUID) -> WalletBundleOut:
        w = await self._repo.get_wallet(user_id)
        txs = await self._repo.list_wallet_txs(user_id)
        return WalletBundleOut(wallet=to_row(w), transactions=to_rows(txs))

    async def list_payout_methods(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_payout_methods(user_id))

    async def create_payout_method(self, user_id: UUID, body: PayoutMethodIn) -> RowOut:
        row = DoctorPayoutMethod(doctor_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def create_payout(self, user_id: UUID, body: PayoutIn) -> RowOut:
        try:
            req = await request_doctor_payout(
                self._repo.session,
                doctor_id=user_id,
                amount=body.amount,
                payout_method_id=body.payout_method_id,
                note=body.note,
            )
        except ValueError as exc:
            raise bad_request(str(exc)) from exc
        return require_row(req)

    async def list_payouts(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_payouts(user_id))

    async def referrals(self, user_id: UUID) -> dict[str, object]:
        doctor = await self._repo.require_profile(user_id)
        refs = await self._repo.list_referrals(user_id)
        commissions = await self._repo.list_commissions(user_id)
        return {
            "referral_code": doctor.referral_code,
            "referrals": to_rows(refs),
            "commissions": to_rows(commissions),
        }

    async def hospitals(self) -> list[RowOut]:
        return to_rows(await self._repo.list_hospitals())

    async def affiliate(self, hospital_id: UUID, user_id: UUID, is_primary: bool) -> RowOut:
        row = DoctorHospitalAffiliation(doctor_id=user_id, hospital_id=hospital_id, is_primary=is_primary)
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)
