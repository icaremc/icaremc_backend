from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SettingIn(BaseModel):
    data: dict[str, object]


class DoctorVerifyIn(BaseModel):
    is_verified: bool


class PayoutActionIn(BaseModel):
    status: str
    admin_note: str | None = None


class AdminCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = "Admin"
    admin_role: str = "viewer"


class SubscriptionGrantIn(BaseModel):
    patient_id: UUID
    days: int = 365
    amount_paid: Decimal = Decimal("0")
    admin_receipt_url: str | None = None


class HospitalIn(BaseModel):
    name: str
    slug: str
    description: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    image_url: str | None = None
    is_active: bool = True
    sort_order: int = 0


class CategoryIn(BaseModel):
    name: str
    slug: str
    is_active: bool = True
    sort_order: int = 1
    image_url: str | None = None
    care_focus: str = "both"


class WeekIn(BaseModel):
    week_number: int
    trimester: int
    image_note: str | None = None
    image_url: str | None = None
    is_published: bool = False


class WeekTranslationIn(BaseModel):
    language_code: str
    title: str
    subtitle: str | None = None
    baby: str | None = None
    stage: str | None = None
    mother_changes: str | None = None
    recommendations: str | None = None
    warning_signs: str | None = None
    sections: list[object] = Field(default_factory=list)


class LegalIn(BaseModel):
    slug: str
    locale: str = "en"
    title: str
    sections: list[object] = Field(default_factory=list)
