from decimal import Decimal

from pydantic import BaseModel


class WithdrawIn(BaseModel):
    amount: Decimal
    note: str | None = None
