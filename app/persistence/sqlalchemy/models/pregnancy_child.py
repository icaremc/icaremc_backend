import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.sqlalchemy.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Pregnancy(Base):
    __tablename__ = "pregnancies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    lmp_date: Mapped[date | None] = mapped_column(Date)
    edd: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="active", server_default=text("'active'"))
    pregnancy_number: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    is_first_pregnancy: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    location: Mapped[str | None] = mapped_column(Text)
    hospital: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[list] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"))
    pre_pregnancy_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    embryo_transfer_date: Mapped[date | None] = mapped_column(Date)
    embryo_age_days: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PregnancyLog(Base):
    __tablename__ = "pregnancy_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    pregnancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pregnancies.id", ondelete="CASCADE"), nullable=False
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    height: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    blood_pressure_systolic: Mapped[int | None] = mapped_column(Integer)
    blood_pressure_diastolic: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    symptoms: Mapped[list] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PregnancyWeek(Base):
    __tablename__ = "pregnancy_weeks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    week_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    trimester: Mapped[int] = mapped_column(Integer, nullable=False)
    image_note: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PregnancyWeekTranslation(Base):
    __tablename__ = "pregnancy_week_translations"
    __table_args__ = (UniqueConstraint("pregnancy_week_id", "language_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    pregnancy_week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pregnancy_weeks.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text)
    baby: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str | None] = mapped_column(Text)
    mother_changes: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    warning_signs: Mapped[str | None] = mapped_column(Text)
    sections: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Child(Base):
    __tablename__ = "children"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    pregnancy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pregnancies.id"))
    local_id: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    birth_height: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    delivery_type: Mapped[str | None] = mapped_column(Text)
    gestational_age_weeks: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    gestational_age_days: Mapped[int | None] = mapped_column(Integer)
    birth_hospital: Mapped[str | None] = mapped_column(Text)
    blood_group: Mapped[str | None] = mapped_column(String(8))
    woreda: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildGrowthPeriod(Base):
    __tablename__ = "child_growth_periods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    age_months: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    age_label: Mapped[str] = mapped_column(Text, nullable=False)
    age_group: Mapped[str] = mapped_column(String(32), default="infant", server_default=text("'infant'"))
    image_note: Mapped[str | None] = mapped_column(Text)
    growth_metrics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildGrowthPeriodTranslation(Base):
    __tablename__ = "child_growth_period_translations"
    __table_args__ = (UniqueConstraint("period_id", "language_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_growth_periods.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text)
    growth: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    vaccines: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    milestones: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    red_flags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    nutrition: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    visit_reminders: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildGrowthMeasurement(Base):
    __tablename__ = "child_growth_measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    child_local_id: Mapped[str] = mapped_column(String(64), nullable=False)
    measured_on: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    age_months: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    head_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildMilestoneCheck(Base):
    __tablename__ = "child_milestone_checks"
    __table_args__ = (UniqueConstraint("user_id", "child_local_id", "item_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    child_local_id: Mapped[str] = mapped_column(String(64), nullable=False)
    item_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChildVaccineRecord(Base):
    __tablename__ = "child_vaccine_records"
    __table_args__ = (UniqueConstraint("user_id", "child_local_id", "vaccine_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    child_local_id: Mapped[str] = mapped_column(String(64), nullable=False)
    vaccine_key: Mapped[str] = mapped_column(Text, nullable=False)
    vaccine_name: Mapped[str] = mapped_column(Text, nullable=False)
    age_months: Mapped[int | None] = mapped_column(Integer)
    received: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    date_received: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VaccineDoseSchedule(Base):
    __tablename__ = "vaccine_dose_schedule"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    dose_number: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    series_code: Mapped[str] = mapped_column(String(64), default="", server_default=text("''"))
    eligible_from_days: Mapped[int] = mapped_column(Integer, nullable=False)
    eligible_until_days: Mapped[int | None] = mapped_column(Integer)
    preferred_visit_codes: Mapped[list] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"))
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildFollowupVisitTemplate(Base):
    __tablename__ = "child_followup_visit_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    label: Mapped[str] = mapped_column(Text, nullable=False)
    offset_days: Mapped[int | None] = mapped_column(Integer)
    offset_months: Mapped[int | None] = mapped_column(Integer)
    growth_period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_growth_periods.id", ondelete="SET NULL")
    )
    modules: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    vaccines: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    remind_days_before: Mapped[list] = mapped_column(ARRAY(Integer), default=list, server_default=text("'{7,1,0}'"))
    label_translations: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildFollowupVisit(Base):
    __tablename__ = "child_followup_visits"
    __table_args__ = (UniqueConstraint("user_id", "child_local_id", "template_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    child_local_id: Mapped[str] = mapped_column(String(64), nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_followup_visit_templates.id"), nullable=False
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="scheduled", server_default=text("'scheduled'"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checklist: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChildFollowupReminderLog(Base):
    __tablename__ = "child_followup_reminder_log"
    __table_args__ = (UniqueConstraint("visit_id", "remind_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_followup_visits.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    remind_key: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChildVaccineReminderLog(Base):
    __tablename__ = "child_vaccine_reminder_log"
    __table_args__ = (UniqueConstraint("user_id", "child_local_id", "vaccine_code", "remind_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    child_local_id: Mapped[str] = mapped_column(String(64), nullable=False)
    vaccine_code: Mapped[str] = mapped_column(Text, nullable=False)
    remind_key: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GrowthClinicalAdvice(Base):
    __tablename__ = "growth_clinical_advice"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    min_age_months: Mapped[float | None] = mapped_column(Numeric)
    max_age_months: Mapped[float | None] = mapped_column(Numeric)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GrowthClinicalAdviceTranslation(Base):
    __tablename__ = "growth_clinical_advice_translations"
    __table_args__ = (UniqueConstraint("advice_id", "language_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    advice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_clinical_advice.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(8), nullable=False)
    explain_text: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    causes: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    recommendations: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
