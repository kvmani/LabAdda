"""Run every health item on a timer and keep the latest results in memory (AD-07)."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import datetime

from . import events
from .catalog import BY_KEY, ITEMS
from .types import STATUSES, Context, Result, make, worst

log = logging.getLogger("labadda.health")

FORCED_NOTE = "Set by the test-only health setting."
# Test-only: a file in the asset directory that browser tests write and delete while the server
# runs, because the stack's start-up environment cannot be changed per test.
FORCE_FILE = ".test-health-force"


def parse_forced(text: str) -> dict[str, str]:
    """``database=degraded,backups=unavailable`` -> {item: status}; unknown names are ignored."""
    forced = {}
    for part in text.split(","):
        item, _, status = part.strip().partition("=")
        if item in BY_KEY and status in STATUSES:
            forced[item] = status
    return forced


class Sampler:
    def __init__(self, context: Context) -> None:
        self.context = context
        self._lock = threading.Lock()
        self._running = threading.Lock()
        self._latest: dict[str, Result] = {}
        self._reported: dict[str, str] = {}
        # Forcing a state is for browser tests only; real instances never honour it.
        allowed = context.settings.fixtures_allowed
        self.forced = parse_forced(context.settings.test_health_force) if allowed else {}

    def _forced_now(self) -> dict[str, str]:
        if not self.context.settings.fixtures_allowed:
            return {}
        try:
            text = (self.context.settings.asset_dir / FORCE_FILE).read_text(encoding="utf-8")
        except OSError:
            return self.forced
        return {**self.forced, **parse_forced(text.replace("\n", ","))}

    def measure(self) -> dict[str, Result]:
        """Run every item once; an item that raises is reported unknown, never as an error."""
        results = {}
        for item in ITEMS:
            try:
                result = item.check(self.context)
            except Exception:
                log.exception("health.item_failed", extra={"item": item.key})
                result = make(self.context, "unknown", None, "", "This check could not be completed.")
            forced = self._forced_now().get(item.key)
            if forced:
                result = replace(result, status=forced, detail=f"{FORCED_NOTE} {result.detail}")
            results[item.key] = result
        return results

    def run_once(self) -> bool:
        """Measure, publish and record events; False when another run is already in progress."""
        if not self._running.acquire(blocking=False):
            return False
        try:
            results = self.measure()
            with self._lock:
                self._latest = results
            self._record_events(results)
        finally:
            self._running.release()
        return True

    def _record_events(self, results: dict[str, Result]) -> None:
        try:
            with self.context.factory() as db:
                for key, result in results.items():
                    events.apply(db, key, result, self._reported.get(key))
                db.commit()
        except Exception:
            log.exception("health.events_failed")
            return
        self._reported = {key: result.status for key, result in results.items()}

    def due(self, now: datetime) -> bool:
        """True when nothing has been measured yet or the newest result is a full interval old."""
        with self._lock:
            times = [result.checked_at for result in self._latest.values()]
        interval = self.context.settings.health.sample_seconds
        return not times or (now - max(times)).total_seconds() >= interval

    def snapshot(self) -> list[tuple[str, Result, float]]:
        """Each item's latest result and its age in seconds; old results are served as stale."""
        now = self.context.now()
        limit = self.context.settings.health.stale_seconds
        with self._lock:
            latest = dict(self._latest)
        rows = []
        for item in ITEMS:
            result = latest.get(item.key)
            if result is None:
                rows.append((item.key, make(self.context, "unknown", None, "", "Not checked yet."), 0.0))
                continue
            age = max((now - result.checked_at).total_seconds(), 0.0)
            if age > limit and result.status != "unsupported":
                result = replace(
                    result, status="stale", detail=f"The last check is out of date. {result.detail}"
                )
            rows.append((item.key, result, age))
        return rows

    def current_status(self, item: str) -> str | None:
        """The status the item last measured, unaffected by how old the measurement is."""
        with self._lock:
            result = self._latest.get(item)
        return result.status if result else None

    def overall(self) -> str:
        return worst([result.status for _, result, _ in self.snapshot()])
