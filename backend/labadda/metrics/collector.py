"""The scheduler job: sample gauges and flush once per interval, roll up once per site hour."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..security import utcnow
from . import gauges, rollup
from .flush import flush
from .registry import REGISTRY, Registry


class Collector:
    """Safe to call on every scheduler tick; it does work only when an interval has passed."""

    def __init__(
        self,
        factory: sessionmaker[Session],
        settings: Settings,
        sockets: Callable[[], int],
        registry: Registry = REGISTRY,
    ) -> None:
        self._factory = factory
        self._settings = settings
        self._sockets = sockets
        self._registry = registry
        self._flushed_at: datetime | None = None
        self._rolled_hour: datetime | None = None

    def tick(self, now: datetime | None = None) -> None:
        """Flush when the interval has passed; roll up when a new site-local hour began."""
        now = now or utcnow()
        interval = timedelta(seconds=self._settings.metrics_flush_seconds)
        if self._flushed_at is not None and now - self._flushed_at < interval:
            return
        with self._factory() as db:
            gauges.sample(
                db, settings=self._settings, sockets=self._sockets(), now=now, registry=self._registry
            )
        with self._factory() as db:
            flush(db, now=now, registry=self._registry)
        self._flushed_at = now
        hour = now.astimezone(ZoneInfo(self._settings.timezone)).replace(minute=0, second=0, microsecond=0)
        if hour != self._rolled_hour:
            with self._factory() as db:
                rollup.roll_up(db, self._settings, now=now)
            self._rolled_hour = hour
