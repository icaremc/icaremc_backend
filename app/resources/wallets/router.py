from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.schemas import RowOut, WalletBundleOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.wallets.repository import SqlAlchemyWalletRepository
from app.resources.wallets.schemas import (
    PatientPayoutMethodIn,
    PatientPayoutMethodUpdate,
    WithdrawIn,
)
from app.resources.wallets.service import WalletService

router = APIRouter(tags=["mother"])


def get_wallet_service(db: DbDep) -> WalletService:
    return WalletService(SqlAlchemyWalletRepository(db))


WalletServiceDep = Annotated[WalletService, Depends(get_wallet_service)]


@router.get("/wallet")
async def wallet(user: RequirePatient, svc: WalletServiceDep) -> WalletBundleOut:
    return await svc.patient_bundle(user.id)


@router.get("/wallet/payout-methods")
async def list_payout_methods(user: RequirePatient, svc: WalletServiceDep) -> list[RowOut]:
    return await svc.list_payout_methods(user.id)


@router.post("/wallet/payout-methods")
async def create_payout_method(
    body: PatientPayoutMethodIn, user: RequirePatient, svc: WalletServiceDep
) -> RowOut:
    return await svc.create_payout_method(user.id, body)


@router.patch("/wallet/payout-methods/{method_id}")
async def update_payout_method(
    method_id: UUID,
    body: PatientPayoutMethodUpdate,
    user: RequirePatient,
    svc: WalletServiceDep,
) -> RowOut:
    return await svc.update_payout_method(user.id, method_id, body)


@router.delete("/wallet/payout-methods/{method_id}")
async def delete_payout_method(
    method_id: UUID, user: RequirePatient, svc: WalletServiceDep
) -> RowOut:
    return await svc.delete_payout_method(user.id, method_id)


@router.get("/wallet/withdrawals")
async def list_withdrawals(user: RequirePatient, svc: WalletServiceDep) -> list[RowOut]:
    return await svc.list_withdrawals(user.id)


@router.post("/wallet/withdraw")
async def wallet_withdraw(body: WithdrawIn, user: RequirePatient, svc: WalletServiceDep) -> RowOut:
    return await svc.withdraw(user.id, body)
