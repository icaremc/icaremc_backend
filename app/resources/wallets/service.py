from uuid import UUID

from app.api.v1.schemas import RowOut, WalletBundleOut
from app.persistence.sqlalchemy.models import PatientWalletWithdrawalRequest
from app.resources.errors import bad_request
from app.resources.serialize import require_row, to_row, to_rows
from app.resources.wallets.repository import WalletRepository
from app.resources.wallets.schemas import WithdrawIn


class WalletService:
    def __init__(self, repo: WalletRepository) -> None:
        self._repo = repo

    async def patient_bundle(self, user_id: UUID) -> WalletBundleOut:
        wallet = await self._repo.get_patient_wallet(user_id)
        txs = await self._repo.list_patient_txs(user_id)
        return WalletBundleOut(wallet=to_row(wallet), transactions=to_rows(txs))

    async def withdraw(self, user_id: UUID, body: WithdrawIn) -> RowOut:
        wallet = await self._repo.get_patient_wallet(user_id)
        if wallet is None or wallet.balance < body.amount:
            raise bad_request("Insufficient balance")
        req = PatientWalletWithdrawalRequest(patient_id=user_id, amount=body.amount, note=body.note)
        self._repo.add(req)
        await self._repo.flush()
        return require_row(req)
