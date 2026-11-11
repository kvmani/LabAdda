"""Metric catalogue and in-memory registry: validation, concurrency, percentiles (T62)."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from labadda.metrics import catalog
from labadda.metrics.registry import LATENCY_BOUNDS_MS, Registry, minute_of, percentile

NOON = datetime(2026, 11, 11, 12, 0, 30, tzinfo=UTC)
LATER = NOON + timedelta(minutes=1)


def by_series(rows):
    return {(row.metric, row.dimension): row for row in rows}


def test_catalog_stays_within_contract_bounds():
    assert len(catalog.CATALOG) <= catalog.MAX_METRICS
    for entry in catalog.CATALOG.values():
        assert len(entry.dimensions) <= catalog.MAX_DIMENSION_VALUES
    assert "http.latency_p95" in catalog.SERIES
    assert "http.latency" not in catalog.SERIES


def test_unknown_metric_is_rejected():
    registry = Registry()
    with pytest.raises(catalog.UnknownMetric):
        registry.count("posts.deleted", "org", now=NOON)


def test_metric_used_as_the_wrong_kind_is_rejected():
    registry = Registry()
    with pytest.raises(catalog.UnknownMetric):
        registry.observe("posts.created", 3.0, "org", now=NOON)


@pytest.mark.parametrize(
    ("name", "dimension"),
    [
        ("posts.created", "division"),
        ("posts.created", "unit:not-a-uuid"),
        ("posts.created", "unit:" + str(uuid.uuid4()).upper()),
        ("http.requests", "/api/v1/posts/123"),
        ("auth.signin_ok", "asha"),
        ("sessions.active", "org"),
    ],
)
def test_unknown_dimension_is_rejected(name, dimension):
    registry = Registry()
    with pytest.raises(catalog.UnknownDimension):
        if catalog.metric(name).kind == "gauge":
            registry.set_gauge(name, 1, dimension, now=NOON)
        else:
            registry.count(name, dimension, now=NOON)
    assert registry.closed(LATER) == []


def test_units_beyond_the_budget_fold_into_other():
    registry = Registry()
    units = [catalog.unit_dimension(uuid.uuid4()) for _ in range(catalog.MAX_DIMENSION_VALUES)]
    for unit in units:
        registry.count("posts.created", unit, now=NOON)
    rows = registry.closed(LATER)
    dimensions = {row.dimension for row in rows}
    budget = catalog.MAX_DIMENSION_VALUES - len(catalog.WORKSPACE_KINDS) - 1
    assert len(dimensions) == budget + 1
    assert by_series(rows)[("posts.created", catalog.UNIT_OVERFLOW)].value == len(units) - budget


def test_concurrent_counts_are_all_kept():
    registry = Registry()
    threads_count = 8
    per_thread = 2000
    start = threading.Barrier(threads_count)

    def worker():
        start.wait()
        for _ in range(per_thread):
            registry.count("chat.messages", "group", now=NOON)
            registry.observe("http.latency", 12.0, "chat", now=NOON)

    threads = [threading.Thread(target=worker) for _ in range(threads_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rows = by_series(registry.closed(LATER))
    assert rows[("chat.messages", "group")].value == threads_count * per_thread
    assert rows[("chat.messages", "group")].samples == threads_count * per_thread
    assert rows[("http.latency_p95", "chat")].samples == threads_count * per_thread


def test_open_minute_is_not_closed_and_discard_keeps_newer_minutes():
    registry = Registry()
    registry.count("posts.created", "org", now=NOON)
    registry.count("posts.created", "org", now=LATER)
    assert registry.closed(NOON) == []
    closed = registry.closed(LATER)
    assert [(row.bucket_start, row.value) for row in closed] == [(minute_of(NOON), 1)]
    registry.discard(closed)
    remaining = registry.closed(LATER + timedelta(minutes=1))
    assert [(row.bucket_start, row.value) for row in remaining] == [(minute_of(LATER), 1)]


def test_gauge_keeps_the_latest_reading():
    registry = Registry()
    registry.set_gauge("sockets.connected", 4, now=NOON)
    registry.set_gauge("sockets.connected", 7, now=NOON)
    row = by_series(registry.closed(LATER))[("sockets.connected", "")]
    assert row.value == 7
    assert row.samples == 2


def test_percentiles_of_a_uniform_spread_are_close():
    registry = Registry()
    for millisecond in range(1, 1001):
        registry.observe("http.latency", float(millisecond), "all", now=NOON)
    rows = by_series(registry.closed(LATER))
    # Interpolation can only be as precise as the bucket holding the rank (500-1000 ms here).
    assert rows[("http.latency_p50", "all")].value == pytest.approx(500, abs=5)
    assert rows[("http.latency_p95", "all")].value == pytest.approx(950, abs=50)
    assert rows[("http.latency_p95", "all")].samples == 1000


def test_percentile_of_values_beyond_the_last_bound_reports_the_bound():
    buckets = [0] * len(LATENCY_BOUNDS_MS) + [3]
    assert percentile(buckets, 0.95) == LATENCY_BOUNDS_MS[-1]


def test_percentile_within_one_bucket_interpolates():
    buckets = [0] * (len(LATENCY_BOUNDS_MS) + 1)
    buckets[4] = 10  # 50-100 ms
    assert percentile(buckets, 0.5) == pytest.approx(75)


def test_naive_time_is_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        minute_of(datetime(2026, 11, 11, 12, 0))
