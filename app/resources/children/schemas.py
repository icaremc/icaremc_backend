from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ChildIn(BaseModel):
    local_id: str | None = None
    name: str = ""
    gender: str
    birth_date: date
    pregnancy_id: UUID | None = None
    birth_weight: Decimal | None = None
    birth_height: Decimal | None = None
    delivery_type: str | None = None
    gestational_age_weeks: Decimal | None = None
    gestational_age_days: int | None = None
    birth_hospital: str | None = None
    blood_group: str | None = None
    woreda: str | None = None
    photo_url: str | None = None
    is_active: bool = True


class MeasurementIn(BaseModel):
    child_local_id: str
    measured_on: date | None = None
    age_months: Decimal | None = None
    weight_kg: Decimal | None = None
    height_cm: Decimal | None = None
    head_circumference_cm: Decimal | None = None
    notes: str | None = None


class MilestoneIn(BaseModel):
    child_local_id: str
    item_key: str


class VaccineIn(BaseModel):
    child_local_id: str
    vaccine_key: str
    vaccine_name: str
    age_months: int | None = None
    received: bool = False
    date_received: date | None = None
