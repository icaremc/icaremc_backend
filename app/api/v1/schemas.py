from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow", from_attributes=True)


# ponytail: RowOut covers ORM dumps without 50 hand-written field lists; tighten per-route when clients need contracts
class RowOut(ApiModel):
    pass


class OkOut(ApiModel):
    ok: bool = True
    detail: str | None = None


class CmsItemOut(ApiModel):
    translation: dict[str, Any] | None = None
    lang_resolved: str | None = None


class ProfileOut(ApiModel):
    id: UUID
    full_name: str | None = None
    phone: str | None = None
    locale: str | None = None
    location: str | None = None
    hospital: str | None = None
    account_type: str | None = None
    avatar_url: str | None = None
    dark_mode: bool | None = None
    notifications_enabled: bool | None = None
    onboarding_complete: bool | None = None


class AppointmentOut(ApiModel):
    id: UUID
    doctor_id: UUID
    patient_id: UUID
    appointment_date: date
    time_slot: str
    status: str
    total_amount: Decimal | None = None
    amount_paid: Decimal | None = None
    payment_status: str | None = None
    service_id: UUID | None = None
    service_name: str | None = None
    note: str | None = None


class WalletBundleOut(ApiModel):
    wallet: RowOut | None = None
    transactions: list[RowOut] = Field(default_factory=list)


class DoctorDetailOut(ApiModel):
    doctor: RowOut
    services: list[RowOut] = Field(default_factory=list)
    slots: list[RowOut] = Field(default_factory=list)


class PaymentInitiateOut(ApiModel):
    ok: bool = True
    tx_ref: str
    checkout_url: str | None = None
    dev: bool | None = None
    meta: dict[str, Any] | None = None
    chapa: dict[str, Any] | None = None


class PaymentWebhookOut(ApiModel):
    ok: bool = True
    type: str | None = None
    ignored: bool | None = None
    unmatched: bool | None = None
    idempotent: bool | None = None


class PushOut(ApiModel):
    ok: bool = True
    fcm: dict[str, Any] | None = None


class HealthOut(ApiModel):
    status: str


class ErrorOut(ApiModel):
    detail: str
