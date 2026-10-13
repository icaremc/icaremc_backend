import asyncio
from datetime import date
from uuid import uuid4

from app.jobs.reminders import run_followup_reminders, run_vaccine_reminders
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import (
    ChildFollowupVisit,
    ChildFollowupVisitTemplate,
    ChildVaccineRecord,
    Profile,
    User,
    VaccineDoseSchedule,
)


def test_reminders_run_without_errors():
    async def _test():
        async with async_session_factory() as db:
            # Seed test user & profile
            user = User(phone=f"09{uuid4().hex[:8]}", role="patient", password_hash="dummy_hashed_pw")
            db.add(user)
            await db.flush()

            profile = Profile(
                id=user.id,
                full_name="Test Mother",
                fcm_token="sample_token_123",
                notifications_enabled=True,
            )
            db.add(profile)

            # Seed a followup visit template and visit due today
            template = ChildFollowupVisitTemplate(
                code=f"tpl_{uuid4().hex[:6]}",
                label="Month 2 Checkup",
            )
            db.add(template)
            await db.flush()

            visit = ChildFollowupVisit(
                user_id=user.id,
                child_local_id="child_1",
                template_id=template.id,
                due_date=date.today(),
            )
            db.add(visit)

            # Seed a vaccine schedule and record
            schedule = VaccineDoseSchedule(
                code=f"BCG_{uuid4().hex[:6]}",
                display_name="BCG Vaccine",
                eligible_from_days=0,
                is_published=True,
            )
            db.add(schedule)
            await db.flush()

            record = ChildVaccineRecord(
                user_id=user.id,
                child_local_id="child_1",
                vaccine_key=schedule.code,
                vaccine_name=schedule.display_name,
                received=False,
            )
            db.add(record)
            await db.commit()

        # Run reminder jobs
        followups_sent = await run_followup_reminders()
        vaccines_sent = await run_vaccine_reminders()

        assert followups_sent >= 1
        assert vaccines_sent >= 1

    asyncio.run(_test())
