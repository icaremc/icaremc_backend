import asyncio
from datetime import date, timedelta
from uuid import UUID, uuid4

from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import ChildFollowupVisitTemplate
from app.resources.children.helpers import add_months, calculate_visit_due_date
from tests.conftest import auth_header


def test_date_helpers():
    # Regular addition
    assert add_months(date(2026, 1, 15), 1) == date(2026, 2, 15)
    assert add_months(date(2026, 1, 15), 12) == date(2027, 1, 15)

    # Clamping at month ends (non-leap year Feb)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    # Leap year Feb (2028 is a leap year)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)

    # calculate_visit_due_date with days
    bdate = date(2026, 5, 1)
    assert calculate_visit_due_date(bdate, offset_days=45) == date(2026, 6, 15)

    # calculate_visit_due_date with months
    assert calculate_visit_due_date(bdate, offset_months=6) == date(2026, 11, 1)

    # calculate_visit_due_date with both
    assert calculate_visit_due_date(bdate, offset_days=5, offset_months=1) == date(2026, 6, 6)


def test_child_creation_auto_generates_followup_visits(client, patient_auth):
    h = auth_header(patient_auth["token"])

    # Seed 2 templates
    async def _seed_templates():
        async with async_session_factory() as db:
            t1 = ChildFollowupVisitTemplate(
                code=f"visit_6w_{uuid4().hex[:6]}",
                label="6 weeks checkup",
                sort_order=1,
                offset_days=42,
                is_published=True,
            )
            t2 = ChildFollowupVisitTemplate(
                code=f"visit_6mo_{uuid4().hex[:6]}",
                label="6 months checkup",
                sort_order=2,
                offset_months=6,
                is_published=True,
            )
            # Unpublished template should not be scheduled
            t3 = ChildFollowupVisitTemplate(
                code=f"visit_unpub_{uuid4().hex[:6]}",
                label="Unpublished checkup",
                sort_order=3,
                offset_days=10,
                is_published=False,
            )
            db.add_all([t1, t2, t3])
            await db.commit()
            return str(t1.id), str(t2.id)

    t1_id, t2_id = asyncio.run(_seed_templates())

    birth_date = date(2026, 3, 1)
    create_res = client.post(
        "/api/v1/children",
        headers=h,
        json={
            "local_id": "baby-followup-test",
            "name": "Followup Baby",
            "gender": "female",
            "birth_date": str(birth_date),
        },
    )
    assert create_res.status_code == 200, create_res.text
    child_id = create_res.json()["id"]

    # Verify visits were generated
    followups_res = client.get(
        "/api/v1/child-followups",
        headers=h,
        params={"child_local_id": "baby-followup-test"},
    )
    assert followups_res.status_code == 200
    visits = followups_res.json()
    assert len(visits) == 2

    visits_by_template = {v["template_id"]: v for v in visits}
    assert t1_id in visits_by_template
    assert t2_id in visits_by_template

    # Check calculated due dates
    expected_t1_date = (birth_date + timedelta(days=42)).isoformat()
    expected_t2_date = add_months(birth_date, 6).isoformat()
    assert visits_by_template[t1_id]["due_date"] == expected_t1_date
    assert visits_by_template[t2_id]["due_date"] == expected_t2_date
    assert visits_by_template[t1_id]["status"] == "scheduled"

    # Patch birth_date and verify due dates update
    new_birth_date = date(2026, 4, 1)
    patch_res = client.patch(
        f"/api/v1/children/{child_id}",
        headers=h,
        json={"birth_date": str(new_birth_date)},
    )
    assert patch_res.status_code == 200

    followups_updated_res = client.get(
        "/api/v1/child-followups",
        headers=h,
        params={"child_local_id": "baby-followup-test"},
    )
    assert followups_updated_res.status_code == 200
    updated_visits = {v["template_id"]: v for v in followups_updated_res.json()}
    assert updated_visits[t1_id]["due_date"] == (new_birth_date + timedelta(days=42)).isoformat()
    assert updated_visits[t2_id]["due_date"] == add_months(new_birth_date, 6).isoformat()

    # Backfill endpoint returns the visits
    backfill_res = client.post(
        f"/api/v1/children/{child_id}/backfill-followups",
        headers=h,
    )
    assert backfill_res.status_code == 200
    assert len(backfill_res.json()) == 2
