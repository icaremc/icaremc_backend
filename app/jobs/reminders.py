"""Cron-style reminder job: python -m app.jobs.reminders"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.api.v1.routers.push import send_fcm
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models import (
    ChildFollowupReminderLog,
    ChildFollowupVisit,
    ChildVaccineRecord,
    ChildVaccineReminderLog,
    Notification,
    Profile,
    VaccineDoseSchedule,
)


async def run_followup_reminders() -> int:
    sent = 0
    today = date.today()
    async with async_session_factory() as db:
        visits = (
            await db.execute(
                select(ChildFollowupVisit).where(ChildFollowupVisit.status.in_(["scheduled", "due", "overdue"]))
            )
        ).scalars().all()
        for visit in visits:
            if visit.due_date is None:
                continue
            days_until = (visit.due_date - today).days
            if days_until < 0:
                visit.status = "overdue"
            elif days_until == 0:
                visit.status = "due"
            remind_key = f"d{days_until}"
            if days_until not in (0, 1, 7):
                continue
            exists = (
                await db.execute(
                    select(ChildFollowupReminderLog).where(
                        ChildFollowupReminderLog.visit_id == visit.id,
                        ChildFollowupReminderLog.remind_key == remind_key,
                    )
                )
            ).scalar_one_or_none()
            if exists:
                continue
            profile = (await db.execute(select(Profile).where(Profile.id == visit.user_id))).scalar_one_or_none()
            title = "Follow-up visit reminder"
            body = f"Child follow-up due on {visit.due_date.isoformat()}"
            db.add(
                Notification(
                    user_id=visit.user_id,
                    type="followup_reminder",
                    title=title,
                    body=body,
                    data={"visit_id": str(visit.id), "child_local_id": visit.child_local_id},
                )
            )
            db.add(
                ChildFollowupReminderLog(
                    visit_id=visit.id,
                    user_id=visit.user_id,
                    remind_key=remind_key,
                    due_date=visit.due_date,
                )
            )
            if profile and profile.fcm_token:
                await send_fcm(profile.fcm_token, title, body)
            sent += 1
        await db.commit()
    return sent


async def run_vaccine_reminders() -> int:
    sent = 0
    async with async_session_factory() as db:
        schedule = (
            await db.execute(select(VaccineDoseSchedule).where(VaccineDoseSchedule.is_published.is_(True)))
        ).scalars().all()
        # ponytail: lightweight scan; narrow with age windows when child birth dates are joined
        pending = (
            await db.execute(select(ChildVaccineRecord).where(ChildVaccineRecord.received.is_(False)))
        ).scalars().all()
        for record in pending:
            code = record.vaccine_key
            remind_key = "eligible"
            exists = (
                await db.execute(
                    select(ChildVaccineReminderLog).where(
                        ChildVaccineReminderLog.user_id == record.user_id,
                        ChildVaccineReminderLog.child_local_id == record.child_local_id,
                        ChildVaccineReminderLog.vaccine_code == code,
                        ChildVaccineReminderLog.remind_key == remind_key,
                    )
                )
            ).scalar_one_or_none()
            if exists:
                continue
            if not any(s.code == code for s in schedule):
                continue
            title = "Vaccine reminder"
            body = f"{record.vaccine_name} is due"
            db.add(
                Notification(
                    user_id=record.user_id,
                    type="vaccine_reminder",
                    title=title,
                    body=body,
                    data={"vaccine_key": code, "child_local_id": record.child_local_id},
                )
            )
            db.add(
                ChildVaccineReminderLog(
                    user_id=record.user_id,
                    child_local_id=record.child_local_id,
                    vaccine_code=code,
                    remind_key=remind_key,
                )
            )
            sent += 1
        await db.commit()
    return sent


async def main() -> None:
    followups = await run_followup_reminders()
    vaccines = await run_vaccine_reminders()
    print(f"{datetime.now(UTC).isoformat()} followups={followups} vaccines={vaccines}")


if __name__ == "__main__":
    asyncio.run(main())
