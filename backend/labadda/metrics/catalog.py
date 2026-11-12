"""The fixed v1 metric catalogue (AD-08): every name, unit, kind and allowed dimension value.

Anything outside this catalogue is rejected, which bounds both the number of series and the
number of rows a minute can produce.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from ..models import WORKSPACE_KINDS

MetricKind = Literal["counter", "gauge", "histogram"]

MAX_METRICS = 60
MAX_DIMENSION_VALUES = 40
NO_DIMENSION = ""
UNIT_PREFIX = "unit:"
# Organisation units beyond the per-metric budget are folded here instead of growing the series.
UNIT_OVERFLOW = "unit:other"
ALL_ROUTES = "all"
OTHER_ROUTES = "other"

# Route groups come from the first static segment of the route template (and, under
# /workspaces/{id}/, the second), so raw paths and their IDs never become dimensions.
ROUTE_GROUPS: dict[str, str] = {
    "admin": "admin",
    "auth": "auth",
    "capabilities": "admin",
    "dashboard": "dashboard",
    "directory": "people",
    "files": "files",
    "groups": "groups",
    "me": "dashboard",
    "notes": "personal",
    "notification-preferences": "notifications",
    "notifications": "notifications",
    "panel": "panel",
    "posts": "noticeboard",
    "todos": "tasks",
    "uploads": "files",
    "usage": "admin",
    "workspaces": "workspaces",
    "workspaces/board": "board",
    "workspaces/chat": "chat",
    "workspaces/posts": "noticeboard",
    "workspaces/search": "noticeboard",
    "workspaces/upcoming": "noticeboard",
}
ROUTE_GROUP_VALUES = tuple(sorted({*ROUTE_GROUPS.values(), OTHER_ROUTES}))

# Upload size bands for "uploads by size band" (AD-08): dimension value and exclusive upper
# bound in bytes; the last band is open-ended.
SIZE_BANDS: tuple[tuple[str, int | None], ...] = (
    ("under_100kb", 100 * 1024),
    ("under_1mb", 1024 * 1024),
    ("under_10mb", 10 * 1024 * 1024),
    ("10mb_or_more", None),
)

# Percentile series stored for each histogram, as stored-name suffix and quantile.
PERCENTILES: dict[str, float] = {"p50": 0.50, "p95": 0.95}


class UnknownMetric(ValueError):
    """A metric name that is not in the catalogue."""


class UnknownDimension(ValueError):
    """A dimension value the metric does not allow (the cardinality guard)."""


@dataclass(frozen=True)
class Metric:
    """One catalogued metric and the only dimension values it may be recorded with."""

    name: str
    kind: MetricKind
    unit: str
    dimensions: tuple[str, ...]
    per_unit: bool = False

    @property
    def series(self) -> tuple[str, ...]:
        """Names under which this metric is stored in ``metric_samples``."""
        if self.kind == "histogram":
            return tuple(f"{self.name}_{suffix}" for suffix in PERCENTILES)
        return (self.name,)


def _feature(name: str, unit: str = "count") -> Metric:
    return Metric(name, "counter", unit, WORKSPACE_KINDS, per_unit=True)


_METRICS = (
    Metric("http.requests", "counter", "count", ROUTE_GROUP_VALUES),
    Metric("http.errors", "counter", "count", ROUTE_GROUP_VALUES),
    Metric("http.latency", "histogram", "ms", (*ROUTE_GROUP_VALUES, ALL_ROUTES)),
    Metric("auth.signin_ok", "counter", "count", (NO_DIMENSION,)),
    Metric("auth.signin_failed", "counter", "count", (NO_DIMENSION,)),
    Metric("sessions.active", "gauge", "count", (NO_DIMENSION,)),
    Metric("sockets.connected", "gauge", "count", (NO_DIMENSION,)),
    _feature("posts.created"),
    _feature("replies.created"),
    _feature("chat.messages"),
    _feature("board.operations"),
    _feature("tasks.created"),
    _feature("tasks.completed"),
    _feature("uploads.count"),
    _feature("uploads.bytes", "bytes"),
    _feature("notifications.created"),
    Metric("uploads.size_band", "counter", "count", tuple(band for band, _ in SIZE_BANDS)),
    Metric("db.size_bytes", "gauge", "bytes", (NO_DIMENSION,)),
    Metric("assets.bytes", "gauge", "bytes", (NO_DIMENSION,)),
    Metric("disk.free_bytes", "gauge", "bytes", (NO_DIMENSION,)),
)

CATALOG: dict[str, Metric] = {metric.name: metric for metric in _METRICS}
SERIES: dict[str, Metric] = {series: metric for metric in _METRICS for series in metric.series}


def metric(name: str) -> Metric:
    """Return the catalogued metric or raise ``UnknownMetric``."""
    found = CATALOG.get(name)
    if found is None:
        raise UnknownMetric(name)
    return found


def series_metric(name: str) -> Metric:
    """Return the metric behind a stored series name or raise ``UnknownMetric``."""
    found = SERIES.get(name)
    if found is None:
        raise UnknownMetric(name)
    return found


def is_unit_dimension(dimension: str) -> bool:
    """True for ``unit:<canonical organisation unit UUID>`` and the overflow value."""
    if dimension == UNIT_OVERFLOW:
        return True
    if not dimension.startswith(UNIT_PREFIX):
        return False
    raw = dimension[len(UNIT_PREFIX) :]
    try:
        return str(uuid.UUID(raw)) == raw
    except ValueError:
        return False


def check_dimension(entry: Metric, dimension: str) -> None:
    """Raise ``UnknownDimension`` unless the metric allows this dimension value."""
    if dimension in entry.dimensions:
        return
    if entry.per_unit and is_unit_dimension(dimension):
        return
    raise UnknownDimension(f"{entry.name}:{dimension[:40]}")


def size_band(size: int) -> str:
    """The size band dimension value for a file of ``size`` bytes."""
    for band, limit in SIZE_BANDS:
        if limit is None or size < limit:
            return band
    raise AssertionError("SIZE_BANDS ends with an open band")


def unit_dimension(unit_id: uuid.UUID) -> str:
    """The dimension value for one organisation unit."""
    return f"{UNIT_PREFIX}{unit_id}"
