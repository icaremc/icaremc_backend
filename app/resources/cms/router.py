from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.schemas import CmsItemOut, RowOut
from app.core.i18n import LangDep
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.cms.repository import SqlAlchemyCmsRepository
from app.resources.cms.service import CmsService

router = APIRouter(tags=["mother"])


def get_cms_service(db: DbDep) -> CmsService:
    return CmsService(SqlAlchemyCmsRepository(db))


CmsServiceDep = Annotated[CmsService, Depends(get_cms_service)]


@router.get("/cms/pregnancy-weeks")
async def cms_pregnancy_weeks(svc: CmsServiceDep, lang: LangDep) -> list[CmsItemOut]:
    return await svc.pregnancy_weeks(lang)


@router.get("/cms/child-growth-periods")
async def cms_growth_periods(svc: CmsServiceDep, lang: LangDep) -> list[CmsItemOut]:
    return await svc.growth_periods(lang)


@router.get("/cms/vaccine-schedule")
async def vaccine_schedule(svc: CmsServiceDep) -> list[RowOut]:
    return await svc.vaccine_schedule()


@router.get("/cms/clinical-advice")
async def clinical_advice(svc: CmsServiceDep, lang: LangDep) -> list[CmsItemOut]:
    return await svc.clinical_advice(lang)


@router.get("/cms/daily-tips")
async def daily_tips(svc: CmsServiceDep, lang: LangDep, week_number: int | None = None) -> list[CmsItemOut]:
    return await svc.daily_tips(lang, week_number)


@router.get("/cms/symptoms")
async def symptoms(svc: CmsServiceDep) -> list[RowOut]:
    return await svc.symptoms()


@router.get("/cms/legal/{slug}")
async def legal(slug: str, svc: CmsServiceDep, lang: LangDep) -> RowOut:
    return await svc.legal(slug, lang)
