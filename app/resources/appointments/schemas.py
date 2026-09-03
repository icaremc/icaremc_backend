from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class BookIn(BaseModel):
    doctor_id: UUID
    appointment_date: date
    time_slot: str
    service_id: UUID | None = None
    note: str | None = None
    care_subscription_id: UUID | None = None
    payment_method: str | None = None


class ReviewIn(BaseModel):
    appointment_id: UUID
    rating: Decimal
    comment: str | None = None
