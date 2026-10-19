from uuid import UUID

from app.api.v1.schemas import RowOut, WalletBundleOut
from app.persistence.sqlalchemy.models import (
    PatientPayoutMethod,
    PatientWalletTransaction,
    PatientWalletWithdrawalRequest,
)
from app.resources.errors import bad_request, not_found
from app.resources.serialize import require_row, to_row, to_rows
from app.resources.wallets.repository import WalletRepository
from app.resources.wallets.schemas import (
    PatientPayoutMethodIn,
    PatientPayoutMethodUpdate,
    WithdrawIn,
)


class WalletService:
    def __init__(self, repo: WalletRepository) -> None:
        self._repo = repo

    async def patient_bundle(self, user_id: UUID) -> WalletBundleOut:
        wallet = await self._repo.get_patient_wallet(user_id)
        txs = await self._repo.list_patient_txs(user_id)
        return WalletBundleOut(wallet=to_row(wallet), transactions=to_rows(txs))

    async def list_payout_methods(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_payout_methods(user_id))

    async def create_payout_method(self, user_id: UUID, body: PatientPayoutMethodIn) -> RowOut:
        if body.is_default:
            await self._repo.unset_default_payout_methods(user_id)
        row = PatientPayoutMethod(patient_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def update_payout_method(self, user_id: UUID, method_id: UUID, body: PatientPayoutMethodUpdate) -> RowOut:
        row = await self._repo.get_payout_method(method_id, user_id)
        if row is None:
            raise not_found("Payout method not found")
        data = body.model_dump(exclude_unset=True)
        if data.get("is_default"):
            await self._repo.unset_default_payout_methods(user_id, exclude_id=method_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self._repo.flush()
        return require_row(row)

    async def delete_payout_method(self, user_id: UUID, method_id: UUID) -> RowOut:
        row = await self._repo.get_payout_method(method_id, user_id)
        if row is None:
            raise not_found("Payout method not found")
        await self._repo.delete(row)
        await self._repo.flush()
        return require_row(row)

    async def list_withdrawals(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_withdrawals(user_id))

    async def withdraw(self, user_id: UUID, body: WithdrawIn) -> RowOut:
        wallet = await self._repo.get_patient_wallet(user_id)
        if wallet is None or wallet.balance < body.amount:
            raise bad_request("Insufficient balance")

        payout_method_id = body.payout_method_id
        if payout_method_id is not None:
            method = await self._repo.get_payout_method(payout_method_id, user_id)
            if method is None:
                raise not_found("Selected payout method not found")
        else:
            # Fall back to default payout method if available
            methods = await self._repo.list_payout_methods(user_id)
            default_method = next((m for m in methods if m.is_default), methods[0] if methods else None)
            if default_method:
                payout_method_id = default_method.id

        # Deduct from patient wallet
        wallet.balance -= body.amount
        self._repo.add(
            PatientWalletTransaction(
                patient_id=user_id,
                amount=body.amount,
                is_credit=False,
                type="withdrawal_hold",
                note=f"Withdrawal request of {body.amount} ETB",
            )
        )

        req = PatientWalletWithdrawalRequest(
            patient_id=user_id,
            payout_method_id=payout_method_id,
            amount=body.amount,
            note=body.note,
            status="pending",
        )
        self._repo.add(req)
        await self._repo.flush()
        return require_row(req)
