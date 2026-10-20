from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class InitiateIn(BaseModel):
    kind: str
    amount: Decimal
    currency: str = "ETB"
    appointment_id: UUID | None = None
    service_id: UUID | None = None
    doctor_id: UUID | None = None
    child_id: UUID | None = None
    email: str = "patient@icaremc.app"
    first_name: str = "Patient"
    last_name: str = "User"
    return_url: str | None = None


class ChildPaymentStatusOut(BaseModel):
    ok: bool = True
    child_id: UUID
    payment_status: str
    amount_paid: Decimal | None = None
    currency: str = "ETB"
    payment_method: str | None = None
    paid_at: str | None = None
    tx_ref: str | None = None
