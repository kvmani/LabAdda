"""Record that a person was active on a site-local day, at most one write per person per day.

An in-memory "seen today" set means only the first signed-in request of the day touches the
database; the insert ignores duplicates, so concurrent first requests are harmless.
"""

from __future__ import annotations

import threading
import uuid
from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import ActivityDay
from ..people import site_date


class ActivityRecorder:
    """The process-wide record of who has already been written for the current site day."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day: date | None = None
        self._seen: set[uuid.UUID] = set()

    def record(
        self, db: Session, user_id: uuid.UUID, settings: Settings, *, now: datetime | None = None
    ) -> None:
        """Insert today's row for this person unless this process already wrote it; commits."""
        today = site_date(settings, now=now)
        with self._lock:
            if self._day != today:
                self._day = today
                self._seen.clear()
            if user_id in self._seen:
                return
        db.execute(insert(ActivityDay).values(user_id=user_id, day=today).on_conflict_do_nothing())
        db.commit()
        with self._lock:
            if self._day == today:
                self._seen.add(user_id)

    def reset(self) -> None:
        """Forget who was seen (a fresh process, and tests)."""
        with self._lock:
            self._day = None
            self._seen.clear()


ACTIVITY = ActivityRecorder()
