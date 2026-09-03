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
    email: str = "patient@icaremc.app"
    first_name: str = "Patient"
    last_name: str = "User"
