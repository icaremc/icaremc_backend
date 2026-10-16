from datetime import date, datetime, timezone
from uuid import UUID

from app.api.v1.schemas import RowOut
from app.persistence.sqlalchemy.models import (
    Child,
    ChildFollowupVisit,
    ChildFollowupVisitTemplate,
    ChildGrowthMeasurement,
    ChildMilestoneCheck,
    ChildVaccineRecord,
)
from app.persistence.sqlalchemy.serialize import row_dict
from app.resources.children.helpers import calculate_visit_due_date
from app.resources.children.repository import ChildrenRepository
from app.resources.children.schemas import (
    ChildIn,
    ChildPatchIn,
    FollowupVisitPatchIn,
    MeasurementIn,
    MilestoneIn,
    VaccineIn,
)
from app.resources.errors import not_found
from app.resources.serialize import require_row, to_rows


def _serialize_visit_with_template(
    visit: ChildFollowupVisit, template: ChildFollowupVisitTemplate | None
) -> RowOut:
    data = row_dict(visit)
    if template is not None:
        t_dict = row_dict(template)
        data["template"] = t_dict
        data["child_followup_visit_templates"] = t_dict
        data["template_label"] = template.label
        data["label"] = template.label
        data["modules"] = template.modules
        data["vaccines"] = template.vaccines
        data["offset_days"] = template.offset_days
        data["offset_months"] = template.offset_months
    else:
        data["template"] = None
        data["child_followup_visit_templates"] = None
    return RowOut.model_validate(data)


class ChildrenService:
    def __init__(self, repo: ChildrenRepository) -> None:
        self._repo = repo

    async def _generate_followup_visits(self, user_id: UUID, child_local_id: str, birth_date: date) -> None:
        templates = await self._repo.list_published_followup_templates()
        if not templates:
            return
        existing_visits = await self._repo.list_followups(user_id, child_local_id)
        existing_map = {visit.template_id: visit for visit in existing_visits}

        for template in templates:
            due_date = calculate_visit_due_date(birth_date, template.offset_days, template.offset_months)
            if template.id in existing_map:
                visit = existing_map[template.id]
                if visit.status != "completed":
                    visit.due_date = due_date
            else:
                self._repo.add(
                    ChildFollowupVisit(
                        user_id=user_id,
                        child_local_id=child_local_id,
                        template_id=template.id,
                        due_date=due_date,
                        status="scheduled",
                    )
                )
        await self._repo.flush()

    async def list_children(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_children(user_id))

    async def get_child(self, child_id: UUID, user_id: UUID) -> RowOut:
        row = await self._repo.get_child(child_id, user_id)
        if row is None:
            raise not_found()
        return require_row(row)

    async def create_child(self, user_id: UUID, body: ChildIn) -> RowOut:
        row = Child(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        child_local_id = row.local_id or str(row.id)
        if not row.local_id:
            row.local_id = child_local_id
            await self._repo.flush()
        if row.birth_date:
            await self._generate_followup_visits(user_id, child_local_id, row.birth_date)
        return require_row(row)

    async def patch_child(self, child_id: UUID, user_id: UUID, body: ChildPatchIn) -> RowOut:
        row = await self._repo.get_child(child_id, user_id)
        if row is None:
            raise not_found()
        prev_birth_date = row.birth_date
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        await self._repo.flush()
        child_local_id = row.local_id or str(row.id)
        if row.birth_date and row.birth_date != prev_birth_date:
            await self._generate_followup_visits(user_id, child_local_id, row.birth_date)
        return require_row(row)

    async def backfill_followups(self, child_id: UUID, user_id: UUID) -> list[RowOut]:
        row = await self._repo.get_child(child_id, user_id)
        if row is None:
            raise not_found()
        child_local_id = row.local_id or str(row.id)
        if row.birth_date:
            await self._generate_followup_visits(user_id, child_local_id, row.birth_date)
        return await self.list_followups(user_id, child_local_id)

    async def delete_child(self, child_id: UUID, user_id: UUID) -> None:
        row = await self._repo.get_child(child_id, user_id)
        if row is None:
            raise not_found()
        child_local_id = row.local_id or str(row.id)
        await self._repo.delete_child_associated_data(user_id, child_local_id)
        await self._repo.delete(row)
        await self._repo.flush()

    async def add_measurement(self, user_id: UUID, body: MeasurementIn) -> RowOut:
        data = body.model_dump()
        if data.get("measured_on") is None:
            data.pop("measured_on", None)
        row = ChildGrowthMeasurement(
            user_id=user_id, **{k: v for k, v in data.items() if v is not None or k == "child_local_id"}
        )
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_measurements(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_measurements(user_id, child_local_id))

    async def add_milestone(self, user_id: UUID, body: MilestoneIn) -> RowOut:
        row = ChildMilestoneCheck(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_milestones(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_milestones(user_id, child_local_id))

    async def upsert_vaccine(self, user_id: UUID, body: VaccineIn) -> RowOut:
        existing = await self._repo.get_vaccine(user_id, body.child_local_id, body.vaccine_key)
        if existing:
            for key, value in body.model_dump().items():
                setattr(existing, key, value)
            await self._repo.flush()
            return require_row(existing)
        row = ChildVaccineRecord(user_id=user_id, **body.model_dump())
        self._repo.add(row)
        await self._repo.flush()
        return require_row(row)

    async def list_vaccines(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        return to_rows(await self._repo.list_vaccines(user_id, child_local_id))

    async def list_followups(self, user_id: UUID, child_local_id: str) -> list[RowOut]:
        pairs = await self._repo.list_followups_with_template(user_id, child_local_id)
        return [_serialize_visit_with_template(v, t) for v, t in pairs]

    async def get_followup(self, visit_id: UUID, user_id: UUID) -> RowOut:
        row = await self._repo.get_followup_with_template(visit_id, user_id)
        if row is None:
            raise not_found()
        return _serialize_visit_with_template(row[0], row[1])

    async def patch_followup(
        self, visit_id: UUID, user_id: UUID, body: FollowupVisitPatchIn
    ) -> RowOut:
        visit = await self._repo.get_followup(visit_id, user_id)
        if visit is None:
            raise not_found()
        for key, value in body.model_dump(exclude_unset=True).items():
            if key == "checklist" and isinstance(value, dict):
                current = dict(visit.checklist or {})
                current.update(value)
                visit.checklist = current
            else:
                setattr(visit, key, value)
        if body.status == "completed" and visit.completed_at is None and body.completed_at is None:
            visit.completed_at = datetime.now(timezone.utc)
        elif body.status == "scheduled" and body.completed_at is None:
            visit.completed_at = None
        await self._repo.flush()
        row = await self._repo.get_followup_with_template(visit_id, user_id)
        if row is None:
            return require_row(visit)
        return _serialize_visit_with_template(row[0], row[1])

    async def list_published_followup_templates(self) -> list[RowOut]:
        return to_rows(await self._repo.list_published_followup_templates())
