from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PatientPayoutMethodIn(BaseModel):
    holder_name: str
    account_number: str
    bank_name: str
    bank_code: str | None = None
    swift_code: str | None = None
    is_default: bool = False
    currency: str = "ETB"


class PatientPayoutMethodUpdate(BaseModel):
    holder_name: str | None = None
    account_number: str | None = None
    bank_name: str | None = None
    bank_code: str | None = None
    swift_code: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    currency: str | None = None


class WithdrawIn(BaseModel):
    amount: Decimal
    payout_method_id: UUID | None = None
    note: str | None = None
