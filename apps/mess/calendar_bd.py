"""Bangladesh calendar helpers (week starts Saturday)."""

from __future__ import annotations

from datetime import date, timedelta


def bangladesh_week_bounds(day: date | None = None) -> tuple[date, date]:
    """
    Return (Saturday, Friday) for the Bangladesh week containing ``day``.

    Python weekday(): Mon=0 … Sun=6; Saturday=5.
    """
    day = day or date.today()
    days_since_saturday = (day.weekday() + 2) % 7
    week_start = day - timedelta(days=days_since_saturday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end
