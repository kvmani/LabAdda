"""Response times, server errors and sign-in failures over a period, by feature area.

Reads the request counters and latency percentiles the metrics middleware already stores (route
groups only, never paths or IDs). Coarse rows are used where the roll-up has made them and finer
rows after them, so no minute is counted twice. Percentiles of merged buckets are the
request-weighted means of their parts, the same approximation as the roll-up and the health page.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..analytics.periods import midnight
from ..config import Settings
from ..metrics import catalog
from ..models import MetricSample
from ..people import site_date
from ..serialize import iso

Span = Literal["24h", "7d", "30d", "90d"]
SPANS: dict[str, tuple[timedelta, str]] = {
    "24h": (timedelta(hours=24), "hour"),
    "7d": (timedelta(days=7), "hour"),
    "30d": (timedelta(days=30), "day"),
    "90d": (timedelta(days=90), "day"),
}
METRICS = (
    "http.requests",
    "http.errors",
    "http.latency_p50",
    "http.latency_p95",
    "auth.signin_ok",
    "auth.signin_failed",
    "sockets.connected",
)
GROUP_LABELS: dict[str, str] = {
    "admin": "Administration",
    "auth": "Sign-in",
    "board": "Whiteboard",
    "chat": "Chat",
    "dashboard": "My day and home",
    "files": "Files",
    "groups": "Groups",
    "noticeboard": "Noticeboard",
    "notifications": "Notifications",
    "panel": "Touch panels",
    "people": "People directory",
    "personal": "Personal notes",
    "tasks": "Tasks",
    "workspaces": "Workspaces",
    "other": "Everything else",
}
# Fewer requests than this make an error rate meaningless, as on the health page.
MIN_REQUESTS_FOR_RATE = 20

Row = tuple[datetime, str, str, float, int]


@dataclass(frozen=True)
class Range:
    start: datetime
    end: datetime
    bucket: str
    timezone: str


def span_ranges(settings: Settings, span: str, *, now: datetime) -> tuple[Range, Range]:
    """The current range ending now and the equal range before it.

    Hour-bucketed spans start on a site-local hour, as the stored hour rows do (in a +05:30 zone
    they start at :30 UTC); day spans start at site midnight.
    """
    length, bucket = SPANS[span]
    if bucket == "day":
        days = length.days
        first = site_date(settings, now=now) - timedelta(days=days - 1)
        start = midnight(first, settings.timezone)
        end = midnight(site_date(settings, now=now) + timedelta(days=1), settings.timezone)
        previous = midnight(first - timedelta(days=days), settings.timezone)
        return Range(start, end, bucket, settings.timezone), Range(previous, start, bucket, settings.timezone)
    local = now.astimezone(ZoneInfo(settings.timezone)).replace(minute=0, second=0, microsecond=0)
    end = local.astimezone(now.tzinfo) + timedelta(hours=1)
    start = end - length
    return Range(start, end, bucket, settings.timezone), Range(
        start - length, start, bucket, settings.timezone
    )


def _latest(db: Session, resolution: str, start: datetime, end: datetime) -> datetime | None:
    return db.scalar(
        select(func.max(MetricSample.bucket_start)).where(
            MetricSample.resolution == resolution,
            MetricSample.metric.in_(METRICS),
            MetricSample.bucket_start >= start,
            MetricSample.bucket_start < end,
        )
    )


def _select(db: Session, resolution: str, start: datetime, end: datetime) -> list[Row]:
    if start >= end:
        return []
    query = select(
        MetricSample.bucket_start,
        MetricSample.metric,
        MetricSample.dimension,
        MetricSample.value,
        MetricSample.samples,
    ).where(
        MetricSample.resolution == resolution,
        MetricSample.metric.in_(METRICS),
        MetricSample.bucket_start >= start,
        MetricSample.bucket_start < end,
    )
    return [(row[0], row[1], row[2], float(row[3]), int(row[4])) for row in db.execute(query)]


def read_rows(db: Session, period: Range) -> list[Row]:
    """Day rows (day spans only), then hour rows after them, then minute rows after those."""
    rows: list[Row] = []
    hour_from = period.start
    if period.bucket == "day":
        latest_day = _latest(db, "day", period.start, period.end)
        if latest_day is not None:
            local = latest_day.astimezone(ZoneInfo(period.timezone)).date()
            hour_from = midnight(local + timedelta(days=1), period.timezone)
            rows += _select(db, "day", period.start, hour_from)
    latest_hour = _latest(db, "hour", hour_from, period.end)
    minute_from = hour_from if latest_hour is None else latest_hour + timedelta(hours=1)
    rows += _select(db, "hour", hour_from, minute_from)
    rows += _select(db, "minute", minute_from, period.end)
    return rows


class Totals:
    """Accumulates counters and weighted percentiles for one bucket or one whole range."""

    def __init__(self) -> None:
        self.counts: dict[tuple[str, str], float] = defaultdict(float)
        self.weighted: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
        self.peak: float | None = None

    def add(self, metric: str, dimension: str, value: float, samples: int) -> None:
        kind = catalog.series_metric(metric).kind
        if kind == "counter":
            self.counts[(metric, dimension)] += value
        elif kind == "gauge":
            self.peak = value if self.peak is None else max(self.peak, value)
        else:
            part = self.weighted[(metric, dimension)]
            part[0] += value * samples
            part[1] += samples

    def count(self, metric: str, dimension: str | None = None) -> float:
        return sum(v for (m, d), v in self.counts.items() if m == metric and dimension in (None, d))

    def percentile(self, metric: str, dimension: str) -> float | None:
        total, weight = self.weighted.get((metric, dimension), (0.0, 0.0))
        return round(total / weight, 1) if weight else None

    def figures(self, dimension: str | None) -> dict:
        latency = catalog.ALL_ROUTES if dimension is None else dimension
        requests = self.count("http.requests", dimension)
        errors = self.count("http.errors", dimension)
        return {
            "requests": requests,
            "errors": errors,
            "error_rate": errors / requests if requests >= MIN_REQUESTS_FOR_RATE else None,
            "p50_ms": self.percentile("http.latency_p50", latency),
            "p95_ms": self.percentile("http.latency_p95", latency),
        }


def _bucket_key(instant: datetime, period: Range) -> datetime:
    local = instant.astimezone(ZoneInfo(period.timezone))
    if period.bucket == "day":
        return midnight(local.date(), period.timezone)
    return local.replace(minute=0, second=0, microsecond=0).astimezone(instant.tzinfo)


def _buckets(rows: list[Row], period: Range) -> list[dict]:
    grouped: dict[datetime, Totals] = defaultdict(Totals)
    for start, metric, dimension, value, samples in rows:
        grouped[_bucket_key(start, period)].add(metric, dimension, value, samples)
    points = []
    for start in sorted(grouped):
        totals = grouped[start]
        signins = totals.count("auth.signin_ok") + totals.count("auth.signin_failed")
        points.append(
            {
                "start": iso(start),
                **totals.figures(None),
                "signin_failed": totals.count("auth.signin_failed") if signins else None,
                "peak_connections": totals.peak,
            }
        )
    return points


def _whole(rows: list[Row]) -> Totals:
    totals = Totals()
    for _, metric, dimension, value, samples in rows:
        totals.add(metric, dimension, value, samples)
    return totals


def _status(figures: dict, settings: Settings) -> str:
    limits = settings.health
    if not figures["requests"]:
        return "unknown"
    slow = figures["p95_ms"] is not None and figures["p95_ms"] > limits.response_p95_ms
    failing = figures["error_rate"] is not None and figures["error_rate"] * 100 > limits.error_rate_percent
    return "degraded" if slow or failing else "healthy"


def _groups(current: Totals, previous: Totals, settings: Settings) -> list[dict]:
    rows = []
    for group in catalog.ROUTE_GROUP_VALUES:
        figures = current.figures(group)
        if not figures["requests"]:
            continue
        before = previous.figures(group)
        rows.append(
            {
                "key": group,
                "label": GROUP_LABELS.get(group, group.title()),
                **figures,
                "previous_p95_ms": before["p95_ms"],
                "previous_requests": before["requests"],
                "status": _status(figures, settings),
            }
        )
    rows.sort(key=lambda row: (-(row["p95_ms"] or 0.0), row["label"]))
    return rows


def _summary(totals: Totals, settings: Settings) -> dict:
    figures = totals.figures(None)
    ok, failed = totals.count("auth.signin_ok"), totals.count("auth.signin_failed")
    return {
        **figures,
        "status": _status(figures, settings),
        "signin_ok": ok,
        "signin_failed": failed,
        "signin_failure_rate": failed / (ok + failed) if ok + failed >= MIN_REQUESTS_FOR_RATE else None,
        "peak_connections": totals.peak,
    }


def build_performance(db: Session, settings: Settings, span: str, *, now: datetime) -> dict:
    current, previous = span_ranges(settings, span, now=now)
    rows = read_rows(db, current)
    before = read_rows(db, previous)
    payload = {
        "span": span,
        "bucket": current.bucket,
        "timezone": settings.timezone,
        "generated_at": iso(now),
        "from": iso(current.start),
        "to": iso(current.end),
        "limits": {
            "p95_ms": settings.health.response_p95_ms,
            "error_rate": settings.health.error_rate_percent / 100,
        },
    }
    if not rows:
        return {**payload, "state": "unknown", "current": None, "previous": None, "points": [], "groups": []}
    totals, prior = _whole(rows), _whole(before)
    return {
        **payload,
        "state": "measured",
        "current": _summary(totals, settings),
        "previous": _summary(prior, settings) if before else None,
        "points": _buckets(rows, current),
        "groups": _groups(totals, prior, settings),
    }
