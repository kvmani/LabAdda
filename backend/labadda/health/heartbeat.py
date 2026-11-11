"""What the scheduler last did, recorded by its loop and read by the Background jobs item."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timedelta

from ..security import utcnow

FAILURE_WINDOW = timedelta(hours=1)
MAX_FAILURES = 200


class Heartbeat:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ticked_at: datetime | None = None
        self._failures: deque[datetime] = deque(maxlen=MAX_FAILURES)

    def tick(self, now: datetime | None = None) -> None:
        """A full pass over reminders and every job finished."""
        with self._lock:
            self._ticked_at = now or utcnow()

    def failure(self, now: datetime | None = None) -> None:
        with self._lock:
            self._failures.append(now or utcnow())

    def last_tick(self) -> datetime | None:
        with self._lock:
            return self._ticked_at

    def failures_in_last_hour(self, now: datetime) -> int:
        with self._lock:
            return sum(1 for at in self._failures if now - at <= FAILURE_WINDOW)

    def reset(self) -> None:
        with self._lock:
            self._ticked_at = None
            self._failures.clear()


HEARTBEAT = Heartbeat()
