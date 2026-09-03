from typing import Protocol
from uuid import UUID

from app.api.v1.schemas import CmsItemOut, RowOut
from app.core.i18n import cms_item, translation_or_en
from app.persistence.sqlalchemy.models import (
    ChildGrowthPeriodTranslation,
    DailyTipTranslation,
    GrowthClinicalAdviceTranslation,
    PregnancyWeekTranslation,
)
from app.resources.cms.repository import CmsRepository
from app.resources.errors import not_found
from app.resources.serialize import require_row, to_rows


class HasId(Protocol):
    id: UUID


class CmsService:
    def __init__(self, repo: CmsRepository) -> None:
        self._repo = repo

    async def _items(self, entities: list[HasId], model: type[object], id_column: object, lang: str) -> list[CmsItemOut]:
        out: list[CmsItemOut] = []
        for entity in entities:
            tr = await translation_or_en(
                self._repo.session,
                model=model,
                id_column=id_column,
                entity_id=entity.id,
                lang=lang,
            )
            out.append(CmsItemOut.model_validate(cms_item(entity, tr)))
        return out

    async def pregnancy_weeks(self, lang: str) -> list[CmsItemOut]:
        weeks = await self._repo.published_weeks()
        return await self._items(weeks, PregnancyWeekTranslation, PregnancyWeekTranslation.pregnancy_week_id, lang)

    async def growth_periods(self, lang: str) -> list[CmsItemOut]:
        periods = await self._repo.published_growth_periods()
        return await self._items(periods, ChildGrowthPeriodTranslation, ChildGrowthPeriodTranslation.period_id, lang)

    async def clinical_advice(self, lang: str) -> list[CmsItemOut]:
        rows = await self._repo.active_clinical_advice()
        return await self._items(rows, GrowthClinicalAdviceTranslation, GrowthClinicalAdviceTranslation.advice_id, lang)

    async def daily_tips(self, lang: str, week_number: int | None) -> list[CmsItemOut]:
        tips = await self._repo.active_daily_tips(week_number)
        return await self._items(tips, DailyTipTranslation, DailyTipTranslation.tip_id, lang)

    async def vaccine_schedule(self) -> list[RowOut]:
        return to_rows(await self._repo.published_vaccine_schedule())

    async def symptoms(self) -> list[RowOut]:
        return to_rows(await self._repo.symptoms())

    async def legal(self, slug: str, lang: str) -> RowOut:
        row = await self._repo.legal(slug, lang)
        if row is None and lang != "en":
            row = await self._repo.legal(slug, "en")
        if row is None:
            raise not_found()
        return require_row(row)
