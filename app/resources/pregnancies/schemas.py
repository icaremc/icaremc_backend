from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PregnancyIn(BaseModel):
    lmp_date: date | None = None
    edd: date | None = None
    status: str = "active"
    pregnancy_number: int = 1
    is_first_pregnancy: bool = True
    location: str | None = None
    hospital: str | None = None
    conditions: list[str] = Field(default_factory=list)
    pre_pregnancy_weight: Decimal | None = None
    height_cm: Decimal | None = None
    embryo_transfer_date: date | None = None
    embryo_age_days: int | None = None


class PregnancyLogIn(BaseModel):
    pregnancy_id: UUID
    week_number: int
    weight: Decimal | None = None
    height: Decimal | None = None
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    temperature: Decimal | None = None
    symptoms: list[str] = Field(default_factory=list)
    notes: str | None = None
