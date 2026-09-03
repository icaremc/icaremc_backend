from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.schemas import RowOut, WalletBundleOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.wallets.repository import SqlAlchemyWalletRepository
from app.resources.wallets.schemas import WithdrawIn
from app.resources.wallets.service import WalletService

router = APIRouter(tags=["mother"])


def get_wallet_service(db: DbDep) -> WalletService:
    return WalletService(SqlAlchemyWalletRepository(db))


WalletServiceDep = Annotated[WalletService, Depends(get_wallet_service)]


@router.get("/wallet")
async def wallet(user: RequirePatient, svc: WalletServiceDep) -> WalletBundleOut:
    return await svc.patient_bundle(user.id)


@router.post("/wallet/withdraw")
async def wallet_withdraw(body: WithdrawIn, user: RequirePatient, svc: WalletServiceDep) -> RowOut:
    return await svc.withdraw(user.id, body)
