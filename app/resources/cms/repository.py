from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import (
    ChildGrowthPeriod,
    DailyTip,
    GrowthClinicalAdvice,
    LegalDocument,
    PregnancyWeek,
    SymptomCatalog,
    VaccineDoseSchedule,
)


class CmsRepository(Protocol):
    async def published_weeks(self) -> list[PregnancyWeek]: ...
    async def published_growth_periods(self) -> list[ChildGrowthPeriod]: ...
    async def published_vaccine_schedule(self) -> list[VaccineDoseSchedule]: ...
    async def active_clinical_advice(self) -> list[GrowthClinicalAdvice]: ...
    async def active_daily_tips(self, week_number: int | None) -> list[DailyTip]: ...
    async def symptoms(self) -> list[SymptomCatalog]: ...
    async def legal(self, slug: str, locale: str) -> LegalDocument | None: ...
    @property
    def session(self) -> AsyncSession: ...


class SqlAlchemyCmsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.session = db

    async def published_weeks(self) -> list[PregnancyWeek]:
        return list(
            (await self.session.execute(select(PregnancyWeek).where(PregnancyWeek.is_published.is_(True)))).scalars().all()
        )

    async def published_growth_periods(self) -> list[ChildGrowthPeriod]:
        return list(
            (
                await self.session.execute(select(ChildGrowthPeriod).where(ChildGrowthPeriod.is_published.is_(True)))
            )
            .scalars()
            .all()
        )

    async def published_vaccine_schedule(self) -> list[VaccineDoseSchedule]:
        return list(
            (
                await self.session.execute(select(VaccineDoseSchedule).where(VaccineDoseSchedule.is_published.is_(True)))
            )
            .scalars()
            .all()
        )

    async def active_clinical_advice(self) -> list[GrowthClinicalAdvice]:
        return list(
            (
                await self.session.execute(select(GrowthClinicalAdvice).where(GrowthClinicalAdvice.is_active.is_(True)))
            )
            .scalars()
            .all()
        )

    async def active_daily_tips(self, week_number: int | None) -> list[DailyTip]:
        q = select(DailyTip).where(DailyTip.is_active.is_(True))
        if week_number is not None:
            q = q.where(DailyTip.week_number == week_number)
        return list((await self.session.execute(q)).scalars().all())

    async def symptoms(self) -> list[SymptomCatalog]:
        return list((await self.session.execute(select(SymptomCatalog))).scalars().all())

    async def legal(self, slug: str, locale: str) -> LegalDocument | None:
        return (
            await self.session.execute(select(LegalDocument).where(LegalDocument.slug == slug, LegalDocument.locale == locale))
        ).scalar_one_or_none()
