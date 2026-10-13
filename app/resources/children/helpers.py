import calendar
from datetime import date, timedelta


def add_months(sourcedate: date, months: int) -> date:
    """Adds months to a date, clamping to the last valid day of the target month."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calculate_visit_due_date(
    birth_date: date,
    offset_days: int | None = None,
    offset_months: int | None = None,
) -> date:
    """
    Computes visit due date based on child's birth date and template offsets.
    Handles offset_months first, followed by offset_days.
    """
    due_date = birth_date
    if offset_months is not None:
        due_date = add_months(due_date, offset_months)
    if offset_days is not None:
        due_date = due_date + timedelta(days=offset_days)
    return due_date
