"""Read stored metric series for the console (AD-08, AD-12); metadata only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..deps import Actor, get_db, require_console
from ..errors import ApiError, Invalid
from ..metrics import catalog
from ..models import MetricSample
from ..serialize import iso

router = APIRouter(tags=["metrics"])
console_activity = require_console("activity")

UNAVAILABLE = ("metrics_unavailable", "Usage figures are unavailable. Try again.")

Resolution = Literal["minute", "hour", "day"]

# Each resolution may be read only over the period it is kept for, which also bounds the
# number of points in one response.
LONGEST_RANGE: dict[str, timedelta] = {
    "minute": timedelta(hours=48),
    "hour": timedelta(days=35),
    "day": timedelta(days=731),
}


@dataclass(frozen=True)
class SeriesQuery:
    """Validated query of ``GET /admin/metrics/series``."""

    metric: str
    dimension: str
    resolution: Resolution
    start: datetime
    end: datetime


def series_query(
    metric: str = Query(min_length=1, max_length=64),
    resolution: Resolution = Query(),
    start: AwareDatetime = Query(alias="from"),
    end: AwareDatetime = Query(alias="to"),
    dimension: str = Query(default="", max_length=64),
) -> SeriesQuery:
    """Parse the query string; time zones are required so periods are unambiguous."""
    return SeriesQuery(metric, dimension, resolution, start, end)


def _validated(query: SeriesQuery) -> catalog.Metric:
    try:
        entry = catalog.series_metric(query.metric)
    except catalog.UnknownMetric:
        raise Invalid("unknown_metric", "That measurement is not collected.") from None
    if catalog.is_unit_dimension(query.dimension):
        # Per-unit figures need small-group protection (AD-08); they are served only by the
        # analytics summaries that apply it, never as raw series.
        raise Invalid("unit_series_not_available", "Figures for one unit are shown on the Activity page.")
    try:
        catalog.check_dimension(entry, query.dimension)
    except catalog.UnknownDimension:
        raise Invalid("unknown_dimension", "That breakdown is not collected for this measurement.") from None
    if query.end <= query.start:
        raise Invalid("invalid_range", "The end of the period must be after its start.")
    if query.end - query.start > LONGEST_RANGE[query.resolution]:
        raise Invalid("range_too_long", "Choose a shorter period or a coarser resolution.")
    return entry


def _point(row: MetricSample) -> dict:
    return {"bucket_start": iso(row.bucket_start), "value": row.value, "samples": row.samples}


def _rows(db: Session, query: SeriesQuery) -> list[MetricSample]:
    db.execute(text("set local statement_timeout = '2s'"))
    return db.scalars(
        select(MetricSample)
        .where(
            MetricSample.metric == query.metric,
            MetricSample.resolution == query.resolution,
            MetricSample.dimension == query.dimension,
            MetricSample.bucket_start >= query.start,
            MetricSample.bucket_start < query.end,
        )
        .order_by(MetricSample.bucket_start)
    ).all()


@router.get("/admin/metrics/series")
def series(
    query: SeriesQuery = Depends(series_query),
    actor: Actor = Depends(console_activity),
    db: Session = Depends(get_db),
) -> dict:
    """Stored buckets in ``[from, to)``, oldest first; a missing bucket means not measured."""
    entry = _validated(query)
    try:
        rows = _rows(db, query)
    except DBAPIError:
        db.rollback()
        raise ApiError(*UNAVAILABLE, status=503) from None
    return {
        "metric": query.metric,
        "dimension": query.dimension,
        "resolution": query.resolution,
        "kind": entry.kind,
        "unit": entry.unit,
        "from": iso(query.start),
        "to": iso(query.end),
        "points": [_point(row) for row in rows],
    }
