"""Activity periods as whole site-local days, with the equal-length period just before (AD-08)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from ..config import Settings
from ..people import site_date

Period = Literal["7d", "30d", "90d", "12m"]
PERIOD_DAYS: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90, "12m": 365}
PERIOD_WORDS: dict[str, str] = {
    "7d": "last 7 days",
    "30d": "last 30 days",
    "90d": "last 90 days",
    "12m": "last 12 months",
}
BucketSize = Literal["day", "week", "month"]
# Chart bucket per period, so the longest period still draws a readable number of bars.
BUCKETS: dict[str, BucketSize] = {"7d": "day", "30d": "day", "90d": "week", "12m": "month"}


def midnight(day: date, timezone: str) -> datetime:
    """The UTC instant at which a site-local day begins (correct across clock changes)."""
    return datetime.combine(day, time(), ZoneInfo(timezone)).astimezone(UTC)


@dataclass(frozen=True)
class Window:
    """Site-local days ``first``..``last`` inclusive, read as UTC instants ``[start, end)``."""

    first: date
    last: date
    timezone: str

    @property
    def start(self) -> datetime:
        return midnight(self.first, self.timezone)

    @property
    def end(self) -> datetime:
        return midnight(self.last + timedelta(days=1), self.timezone)

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    def tail(self, days: int) -> Window:
        """The last ``days`` days of this window, or the whole window when it is shorter."""
        return Window(max(self.first, self.last - timedelta(days=days - 1)), self.last, self.timezone)

    def json(self) -> dict[str, str]:
        return {"first_day": self.first.isoformat(), "last_day": self.last.isoformat()}


def windows(period: str, settings: Settings, *, now: datetime) -> tuple[Window, Window]:
    """The current period ending today (site-local) and the previous period of equal length."""
    days = PERIOD_DAYS[period]
    today = site_date(settings, now=now)
    first = today - timedelta(days=days - 1)
    previous_last = first - timedelta(days=1)
    return (
        Window(first, today, settings.timezone),
        Window(previous_last - timedelta(days=days - 1), previous_last, settings.timezone),
    )
