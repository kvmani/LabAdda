"""Shared builders for health tests: a context with injectable readings."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from labadda.health import Context
from labadda.health.proc import Proc, ProcUnavailable

NOW = datetime(2026, 11, 11, 12, 0, 0, tzinfo=UTC)


class DownFactory:
    """A session factory for a database that does not answer."""

    def __call__(self):
        raise ConnectionError("database down")


class FakeProc(Proc):
    def __init__(self, *, rss=200 * 1024**2, load=0.5, cpus=4, memory=(8 * 1024**3, 6 * 1024**3), fail=False):
        self.values = (rss, load, cpus, memory)
        self.fail = fail

    def process_rss_bytes(self):
        if self.fail:
            raise ProcUnavailable("rss")
        return self.values[0]

    def load_average(self):
        return self.values[1]

    def cpu_count(self):
        return self.values[2]

    def memory(self):
        return self.values[3]


def context(settings, db_factory, **overrides) -> Context:
    thresholds = overrides.pop("thresholds", {})
    settings = replace(settings, health=replace(settings.health, **thresholds))
    values = {
        "settings": settings,
        "factory": db_factory,
        "started": NOW.replace(hour=0),
        "expected_schema": lambda: "0029",
        "now": lambda: NOW,
    }
    values.update(overrides)
    return Context(**values)
