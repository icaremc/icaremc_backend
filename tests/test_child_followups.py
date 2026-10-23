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


def test_delete_child(client, patient_auth):
    h = auth_header(patient_auth["token"])
    create_res = client.post(
        "/api/v1/children",
        headers=h,
        json={
            "local_id": "baby-del-test",
            "name": "To Delete",
            "gender": "male",
            "birth_date": "2026-01-01",
        },
    )
    assert create_res.status_code == 200
    child_id = create_res.json()["id"]

    # Add measurement, milestone, vaccine
    m = client.post(
        "/api/v1/child-measurements",
        headers=h,
        json={"child_local_id": "baby-del-test", "weight_kg": 4.5, "height_cm": 52},
    )
    assert m.status_code == 200

    ms = client.post(
        "/api/v1/child-milestones",
        headers=h,
        json={"child_local_id": "baby-del-test", "item_key": "smile"},
    )
    assert ms.status_code == 200

    v = client.post(
        "/api/v1/child-vaccines",
        headers=h,
        json={"child_local_id": "baby-del-test", "vaccine_key": "bcg", "vaccine_name": "BCG"},
    )
    assert v.status_code == 200

    # Delete child
    del_res = client.delete(f"/api/v1/children/{child_id}", headers=h)
    assert del_res.status_code == 200

    # Child is gone
    get_res = client.get(f"/api/v1/children/{child_id}", headers=h)
    assert get_res.status_code == 404

    # All sub-records are cleaned up
    assert client.get("/api/v1/child-measurements", headers=h, params={"child_local_id": "baby-del-test"}).json() == []
    assert client.get("/api/v1/child-milestones", headers=h, params={"child_local_id": "baby-del-test"}).json() == []
    assert client.get("/api/v1/child-vaccines", headers=h, params={"child_local_id": "baby-del-test"}).json() == []
    assert client.get("/api/v1/child-followups", headers=h, params={"child_local_id": "baby-del-test"}).json() == []


def test_delete_child_measurement_milestone_and_vaccine(client, patient_auth, unique_phone):
    h = auth_header(patient_auth["token"])
    child_local_id = f"baby-delete-records-{uuid4().hex[:8]}"

    measurement = client.post(
        "/api/v1/child-measurements",
        headers=h,
        json={"child_local_id": child_local_id, "weight_kg": 4.5},
    )
    milestone = client.post(
        "/api/v1/child-milestones",
        headers=h,
        json={"child_local_id": child_local_id, "item_key": "smile"},
    )
    vaccine = client.post(
        "/api/v1/child-vaccines",
        headers=h,
        json={"child_local_id": child_local_id, "vaccine_key": "bcg", "vaccine_name": "BCG"},
    )
    assert measurement.status_code == milestone.status_code == vaccine.status_code == 200

    # Cross-user isolation: another patient cannot delete these records
    other_phone = unique_phone("99")
    other_otp = client.post("/api/v1/auth/patient/otp", json={"phone": other_phone}).json()
    other_signup = client.post(
        "/api/v1/auth/patient/signup",
        json={
            "phone": other_phone,
            "password": "secret12",
            "otp": other_otp["dev_code"],
            "full_name": "Other Mother",
        },
    )
    other_h = auth_header(other_signup.json()["access_token"])

    for endpoint, record in (
        ("child-measurements", measurement.json()),
        ("child-milestones", milestone.json()),
        ("child-vaccines", vaccine.json()),
    ):
        forbidden_del = client.delete(f"/api/v1/{endpoint}/{record['id']}", headers=other_h)
        assert forbidden_del.status_code == 404

    for endpoint, record in (
        ("child-measurements", measurement.json()),
        ("child-milestones", milestone.json()),
        ("child-vaccines", vaccine.json()),
    ):
        deleted = client.delete(f"/api/v1/{endpoint}/{record['id']}", headers=h)
        assert deleted.status_code == 204

    assert client.get(
        "/api/v1/child-measurements", headers=h, params={"child_local_id": child_local_id}
    ).json() == []
    assert client.get(
        "/api/v1/child-milestones", headers=h, params={"child_local_id": child_local_id}
    ).json() == []
    assert client.get(
        "/api/v1/child-vaccines", headers=h, params={"child_local_id": child_local_id}
    ).json() == []

    for endpoint in ("child-measurements", "child-milestones", "child-vaccines"):
        missing = client.delete(f"/api/v1/{endpoint}/{uuid4()}", headers=h)
        assert missing.status_code == 404


def test_followup_visit_checklist_and_patch(client, patient_auth):
    h = auth_header(patient_auth["token"])

    # Seed a template with rich checklist/modules and vaccines
    async def _seed_template():
        async with async_session_factory() as db:
            tmpl = ChildFollowupVisitTemplate(
                code=f"visit_test_{uuid4().hex[:6]}",
                label="2 months checkup",
                sort_order=1,
                offset_days=60,
                modules={
                    "growth": True,
                    "vaccines": True,
                    "nutrition": True,
                    "red_flags": True,
                    "development": True,
                },
                vaccines=[{"name": "Penta 1", "route": "Intramuscular"}],
                is_published=True,
            )
            db.add(tmpl)
            await db.commit()
            return str(tmpl.id)

    tmpl_id = asyncio.run(_seed_template())

    # Patient can list published followup templates
    templates_res = client.get("/api/v1/followup-templates", headers=h)
    assert templates_res.status_code == 200
    all_tmpls = templates_res.json()
    assert any(t["id"] == tmpl_id for t in all_tmpls)

    # Create child
    create_res = client.post(
        "/api/v1/children",
        headers=h,
        json={
            "local_id": "baby-checklist-test",
            "name": "Checklist Baby",
            "gender": "male",
            "birth_date": "2026-05-01",
        },
    )
    assert create_res.status_code == 200

    # Fetch followups for the child
    followups_res = client.get(
        "/api/v1/child-followups",
        headers=h,
        params={"child_local_id": "baby-checklist-test"},
    )
    assert followups_res.status_code == 200
    visits = followups_res.json()
    visit = next(v for v in visits if v["template_id"] == tmpl_id)

    # Verify template details are included on the visit
    assert visit["template"] is not None
    assert visit["template"]["id"] == tmpl_id
    assert visit["template"]["label"] == "2 months checkup"
    assert visit["template"]["modules"]["development"] is True
    assert visit["label"] == "2 months checkup"
    assert visit["modules"]["development"] is True
    assert len(visit["vaccines"]) == 1
    assert visit["status"] == "scheduled"
    assert visit["completed_at"] is None
    visit_id = visit["id"]

    # Get single followup by ID
    single_res = client.get(f"/api/v1/child-followups/{visit_id}", headers=h)
    assert single_res.status_code == 200
    single = single_res.json()
    assert single["id"] == visit_id
    assert single["template"]["label"] == "2 months checkup"

    # Patch checklist responses and mark visit completed
    checklist_answers = {
        "notes": "Child is feeding and sleeping well.",
        "growth_done": True,
        "vaccines_done": True,
        "nutrition_done": True,
        "counseling_done": True,
        "development_done": True,
        "red_flags_reviewed": True,
        "red_flags_concern": False,
    }
    patch_res = client.patch(
        f"/api/v1/child-followups/{visit_id}",
        headers=h,
        json={
            "status": "completed",
            "checklist": checklist_answers,
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["status"] == "completed"
    assert patched["completed_at"] is not None
    assert patched["checklist"]["growth_done"] is True
    assert patched["checklist"]["notes"] == "Child is feeding and sleeping well."
    assert patched["template"]["label"] == "2 months checkup"


