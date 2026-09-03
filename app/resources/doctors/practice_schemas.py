from datetime import time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    specialty: str | None = None
    hospital: str | None = None
    license_number: str | None = None
    experience_years: int | None = None
    availability: str | None = None
    bio: str | None = None
    category_id: UUID | None = None
    license_image_url: str | None = None
    degree_image_url: str | None = None
    profile_photo_url: str | None = None
    fcm_token: str | None = None
    notifications_enabled: bool | None = None
    dark_mode: bool | None = None
    available_today: bool | None = None
    primary_hospital_id: UUID | None = None
    prepayment_mode: str | None = None
    prepayment_percent: int | None = None


class ServiceIn(BaseModel):
    name: str
    description: str | None = None
    price: Decimal
    currency: str = "ETB"
    is_active: bool = True
    sort_order: int = 0
    image_url: str | None = None
    billing_type: str = "one_time"
    duration_minutes: int = 30
    visits_per_period: int | None = None


class SlotIn(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    hospital_id: UUID | None = None
    slot_duration_minutes: int = 30
    is_active: bool = True


class PayoutMethodIn(BaseModel):
    holder_name: str
    account_number: str
    bank_name: str
    bank_code: str | None = None
    swift_code: str | None = None
    is_default: bool = False
    currency: str = "ETB"


class PayoutIn(BaseModel):
    amount: Decimal
    payout_method_id: UUID
    note: str | None = None
