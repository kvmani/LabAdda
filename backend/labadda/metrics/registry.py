"""Thread-safe in-memory counters, gauges and fixed-bucket histograms, keyed by UTC minute.

Values for a minute stay in memory until a flush has written them. A flush writes absolute
per-minute totals, so writing the same closed minute twice (for example after a failure
between the database commit and ``discard``) stores the same numbers, never double counts.
"""

from __future__ import annotations

import bisect
import threading
from dataclasses import dataclass
from datetime import datetime

from ..security import utcnow
from . import catalog

# Upper bounds in milliseconds; the last bucket holds everything slower.
LATENCY_BOUNDS_MS: tuple[float, ...] = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)

Key = tuple[datetime, str, str]


@dataclass(frozen=True)
class Sample:
    """One stored row: a minute, a series name, a dimension value, its value and sample count."""

    bucket_start: datetime
    metric: str
    dimension: str
    value: float
    samples: int


def minute_of(instant: datetime) -> datetime:
    """The start of the UTC minute that contains ``instant``."""
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("A timezone-aware instant is required")
    return instant.replace(second=0, microsecond=0)


def percentile(buckets: list[int], quantile: float, bounds: tuple[float, ...] = LATENCY_BOUNDS_MS) -> float:
    """Estimate a quantile by linear interpolation inside the bucket that holds its rank."""
    total = sum(buckets)
    if total == 0:
        raise ValueError("No observations")
    rank = quantile * total
    below = 0
    for index, count in enumerate(buckets):
        if count and below + count >= rank:
            if index >= len(bounds):
                # Observations beyond the last bound cannot be placed more precisely.
                return bounds[-1]
            lower = bounds[index - 1] if index else 0.0
            upper = bounds[index]
            return lower + (upper - lower) * (rank - below) / count
        below += count
    return bounds[-1]


class Registry:
    """The process-wide metric store; every write is validated against the catalogue."""

    def __init__(self, bounds: tuple[float, ...] = LATENCY_BOUNDS_MS) -> None:
        self._bounds = bounds
        self._lock = threading.Lock()
        self._counters: dict[Key, list[float]] = {}
        self._gauges: dict[Key, list[float]] = {}
        self._histograms: dict[Key, list[int]] = {}
        # Organisation units accepted per metric for the life of the process.
        self._units: dict[str, set[str]] = {}

    def count(
        self,
        name: str,
        dimension: str = catalog.NO_DIMENSION,
        amount: float = 1,
        *,
        now: datetime | None = None,
    ) -> None:
        """Add ``amount`` to a counter for the current minute."""
        entry = self._entry(name, "counter")
        with self._lock:
            key = self._key(entry, dimension, now)
            total = self._counters.setdefault(key, [0.0, 0])
            total[0] += amount
            total[1] += 1

    def set_gauge(
        self, name: str, value: float, dimension: str = catalog.NO_DIMENSION, *, now: datetime | None = None
    ) -> None:
        """Record the latest reading of a gauge for the current minute."""
        entry = self._entry(name, "gauge")
        with self._lock:
            key = self._key(entry, dimension, now)
            reading = self._gauges.setdefault(key, [0.0, 0])
            reading[0] = value
            reading[1] += 1

    def observe(
        self, name: str, value: float, dimension: str = catalog.NO_DIMENSION, *, now: datetime | None = None
    ) -> None:
        """Place one observation in the histogram bucket for the current minute."""
        entry = self._entry(name, "histogram")
        with self._lock:
            key = self._key(entry, dimension, now)
            buckets = self._histograms.setdefault(key, [0] * (len(self._bounds) + 1))
            buckets[bisect.bisect_left(self._bounds, value)] += 1

    def closed(self, now: datetime | None = None) -> list[Sample]:
        """Rows for every minute that ended before ``now``; nothing is removed."""
        with self._lock:
            current = minute_of(now or utcnow())
            rows = [
                Sample(key[0], key[1], key[2], total[0], int(total[1]))
                for store in (self._counters, self._gauges)
                for key, total in store.items()
                if key[0] < current
            ]
            for key, buckets in self._histograms.items():
                if key[0] < current:
                    rows.extend(self._percentile_rows(key, buckets))
        return rows

    def discard(self, samples: list[Sample]) -> None:
        """Forget minutes that a flush has committed."""
        written = {sample.bucket_start for sample in samples}
        with self._lock:
            for store in (self._counters, self._gauges, self._histograms):
                for key in [key for key in store if key[0] in written]:
                    del store[key]

    def reset(self) -> None:
        """Drop every value and accepted unit (start-up of a fresh process, and tests)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._units.clear()

    def _entry(self, name: str, kind: catalog.MetricKind) -> catalog.Metric:
        entry = catalog.metric(name)
        if entry.kind != kind:
            raise catalog.UnknownMetric(f"{name} is a {entry.kind}, not a {kind}")
        return entry

    def _key(self, entry: catalog.Metric, dimension: str, now: datetime | None) -> Key:
        # Callers hold the lock, and the minute is read under it: a value can never land
        # in a minute that a concurrent flush has already treated as closed.
        catalog.check_dimension(entry, dimension)
        if entry.per_unit and dimension.startswith(catalog.UNIT_PREFIX):
            dimension = self._bounded_unit(entry, dimension)
        return (minute_of(now or utcnow()), entry.name, dimension)

    def _bounded_unit(self, entry: catalog.Metric, dimension: str) -> str:
        accepted = self._units.setdefault(entry.name, set())
        if dimension in accepted or dimension == catalog.UNIT_OVERFLOW:
            return dimension
        budget = catalog.MAX_DIMENSION_VALUES - len(entry.dimensions) - 1
        if len(accepted) >= budget:
            return catalog.UNIT_OVERFLOW
        accepted.add(dimension)
        return dimension

    def _percentile_rows(self, key: Key, buckets: list[int]) -> list[Sample]:
        total = sum(buckets)
        return [
            Sample(key[0], f"{key[1]}_{suffix}", key[2], percentile(buckets, quantile, self._bounds), total)
            for suffix, quantile in catalog.PERCENTILES.items()
        ]


REGISTRY = Registry()
