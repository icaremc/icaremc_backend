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


class CategoryTranslationIn(BaseModel):
    language_code: str
    name: str


class CategoryIn(BaseModel):
    name: str
    slug: str
    is_active: bool = True
    sort_order: int = 1
    image_url: str | None = None
    care_focus: str = "both"
    translations: list[CategoryTranslationIn] | None = None


class CategoryPatchIn(BaseModel):
    name: str | None = None
    slug: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    image_url: str | None = None
    care_focus: str | None = None
    translations: list[CategoryTranslationIn] | None = None


class WeekIn(BaseModel):
    week_number: int
    trimester: int
    image_note: str | None = None
    image_url: str | None = None
    is_published: bool = False


class WeekPatchIn(BaseModel):
    week_number: int | None = None
    trimester: int | None = None
    image_note: str | None = None
    image_url: str | None = None
    is_published: bool | None = None


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


class GrowthPeriodTranslationIn(BaseModel):
    language_code: str
    title: str
    subtitle: str | None = None
    growth: dict[str, object] = Field(default_factory=dict)
    vaccines: list[object] = Field(default_factory=list)
    milestones: list[object] = Field(default_factory=list)
    red_flags: list[object] = Field(default_factory=list)
    nutrition: list[object] = Field(default_factory=list)
    visit_reminders: list[object] = Field(default_factory=list)


class GrowthPeriodIn(BaseModel):
    age_months: int
    age_label: str
    age_group: str = "infant"
    image_note: str | None = None
    growth_metrics: dict[str, object] = Field(default_factory=dict)
    is_published: bool = False
    translations: list[GrowthPeriodTranslationIn] | None = None


class GrowthPeriodPatchIn(BaseModel):
    age_months: int | None = None
    age_label: str | None = None
    age_group: str | None = None
    image_note: str | None = None
    growth_metrics: dict[str, object] | None = None
    is_published: bool | None = None
    translations: list[GrowthPeriodTranslationIn] | None = None


class FollowupTemplateIn(BaseModel):
    code: str
    sort_order: int = 0
    label: str
    offset_days: int | None = None
    offset_months: int | None = None
    growth_period_id: UUID | None = None
    modules: dict[str, object] = Field(default_factory=dict)
    vaccines: list[object] = Field(default_factory=list)
    remind_days_before: list[int] = Field(default_factory=lambda: [7, 1, 0])
    label_translations: dict[str, object] = Field(default_factory=dict)
    is_published: bool = False


class FollowupTemplatePatchIn(BaseModel):
    sort_order: int | None = None
    label: str | None = None
    offset_days: int | None = None
    offset_months: int | None = None
    growth_period_id: UUID | None = None
    modules: dict[str, object] | None = None
    vaccines: list[object] | None = None
    remind_days_before: list[int] | None = None
    label_translations: dict[str, object] | None = None
    is_published: bool | None = None


class LegalIn(BaseModel):
    slug: str
    locale: str = "en"
    title: str
    sections: list[object] = Field(default_factory=list)


class AppointmentStatusIn(BaseModel):
    status: str


class AdminPatchIn(BaseModel):
    is_active: bool | None = None
    admin_role: str | None = None
    full_name: str | None = None


class DocumentIn(BaseModel):
    title: str
    category: str = "other"
    storage_path: str
    file_name: str
    mime_type: str = "application/pdf"


class DailyTipTranslationIn(BaseModel):
    language_code: str
    title: str
    content: str


class DailyTipIn(BaseModel):
    week_number: int
    day_number: int | None = None
    category: str | None = None
    is_active: bool = True
    translations: list[DailyTipTranslationIn] | None = None


class DailyTipPatchIn(BaseModel):
    week_number: int | None = None
    day_number: int | None = None
    category: str | None = None
    is_active: bool | None = None
    translations: list[DailyTipTranslationIn] | None = None
