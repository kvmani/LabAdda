"""T63: every health item returns each status it can have from injected readings."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from labadda import backup_status
from labadda.health import (
    application,
    backups,
    certificate,
    connections,
    database,
    file_storage,
    jobs,
    response_time,
    server,
    sign_in,
)
from labadda.health.heartbeat import Heartbeat
from labadda.health.types import DiskReading, worst
from labadda.health_thresholds import GIB
from labadda.metrics.registry import Registry
from tests.health_support import NOW, DownFactory, FakeProc, context


@pytest.fixture
def ctx(settings, db_factory):
    return context(settings, db_factory)


# --- application ----------------------------------------------------------------------------


def test_application_matches_schema(ctx):
    from labadda.app import expected_schema_head

    live = application.check(context(ctx.settings, ctx.factory, expected_schema=expected_schema_head))
    assert (live.status, live.unit) == ("healthy", "seconds")
    assert application.evaluate(ctx, uptime=3600, current="0029", expected="0029").status == "healthy"


@pytest.mark.parametrize(("current", "word"), [("0001", "behind"), ("9999", "ahead of")])
def test_application_schema_mismatch_is_degraded(ctx, current, word):
    result = application.evaluate(ctx, uptime=60, current=current, expected="0029")
    assert result.status == "degraded"
    assert word in result.detail


def test_application_is_unknown_when_the_database_is_down(settings):
    result = application.check(context(settings, DownFactory()))
    assert result.status == "unknown"
    assert result.value is None


# --- database -------------------------------------------------------------------------------


def test_database_healthy_and_measured(ctx):
    result = database.check(ctx)
    assert result.status == "healthy"
    assert result.unit == "ms"
    assert "connections in use" in result.detail


def test_database_slow_and_crowded_are_degraded(ctx):
    slow = database.evaluate(ctx, round_trip_ms=400, used=5, maximum=100, size=1024)
    crowded = database.evaluate(ctx, round_trip_ms=5, used=81, maximum=100, size=1024)
    edge = database.evaluate(ctx, round_trip_ms=250, used=80, maximum=100, size=1024)
    assert (slow.status, crowded.status, edge.status) == ("degraded", "degraded", "healthy")


def test_database_down_is_unavailable(settings):
    result = database.check(context(settings, DownFactory()))
    assert result.status == "unavailable"
    assert result.value is None


# --- file storage ---------------------------------------------------------------------------


def disk(free_gib, inode_percent=50):
    return DiskReading(int(free_gib * GIB), 100 * GIB, inode_percent * 10, 1000)


def test_file_storage_statuses_from_reserve(ctx):
    # Default reserve is 5 GiB; degraded below 6 GiB.
    assert file_storage.evaluate(ctx, disk(50)).status == "healthy"
    assert file_storage.evaluate(ctx, disk(5.5)).status == "degraded"
    under = file_storage.evaluate(ctx, disk(4))
    assert under.status == "unavailable"
    assert under.value == 4 * GIB


def test_file_storage_inodes_below_reserve(ctx):
    assert file_storage.evaluate(ctx, disk(50, inode_percent=4)).status == "unavailable"
    assert file_storage.evaluate(ctx, disk(50, inode_percent=5.5)).status == "degraded"


def test_file_storage_check_reads_the_injected_volume(settings, db_factory):
    low = context(settings, db_factory, disk=lambda path: disk(1))
    assert file_storage.check(low).status == "unavailable"


def test_file_storage_unreadable_volume_is_unknown(settings, db_factory):
    def broken(path):
        raise FileNotFoundError(path)

    assert file_storage.check(context(settings, db_factory, disk=broken)).status == "unknown"


# --- live connections -----------------------------------------------------------------------


def test_connections_backlog_statuses(ctx):
    assert connections.evaluate(ctx, sockets=3, sessions=2, backlog=0).status == "healthy"
    assert connections.evaluate(ctx, sockets=3, sessions=2, backlog=1001).status == "degraded"
    assert connections.evaluate(ctx, sockets=3, sessions=2, backlog=5001).status == "unavailable"


def test_connections_check_counts_sockets_and_handles_database_loss(settings, db_factory):
    live = connections.check(context(settings, db_factory, sockets=lambda: 4, backlog=lambda: 7))
    assert (live.status, live.value) == ("healthy", 4)
    down = connections.check(context(settings, DownFactory(), sockets=lambda: 4))
    assert (down.status, down.value) == ("unknown", 4)


# --- background jobs ------------------------------------------------------------------------


def scheduled(settings, db_factory, beat, **extra):
    extra.setdefault("started", NOW - timedelta(hours=1))
    return context(replace(settings, run_scheduler=True), db_factory, heartbeat=beat, **extra)


def beat_at(seconds_ago):
    beat = Heartbeat()
    beat.tick(NOW - timedelta(seconds=seconds_ago))
    return beat


def test_jobs_statuses_from_a_scheduler_heartbeat(settings, db_factory):
    assert jobs.check(scheduled(settings, db_factory, beat_at(20))).status == "healthy"
    assert jobs.check(scheduled(settings, db_factory, beat_at(150))).status == "degraded"
    stalled = jobs.check(scheduled(settings, db_factory, beat_at(700)))
    assert (stalled.status, stalled.value) == ("unavailable", 700)


def test_jobs_failed_runs_degrade_and_age_out(settings, db_factory):
    recent = beat_at(5)
    old = beat_at(5)
    for _ in range(3):
        recent.failure(NOW - timedelta(minutes=10))
        old.failure(NOW - timedelta(hours=2))
    assert jobs.check(scheduled(settings, db_factory, recent)).status == "degraded"
    assert jobs.check(scheduled(settings, db_factory, old)).status == "healthy"


def test_jobs_before_the_first_pass_are_unknown_then_late(settings, db_factory):
    fresh = scheduled(settings, db_factory, Heartbeat(), started=NOW - timedelta(seconds=30))
    assert jobs.check(fresh).status == "unknown"
    never = scheduled(settings, db_factory, Heartbeat(), started=NOW - timedelta(minutes=30))
    assert jobs.check(never).status == "unavailable"


def test_jobs_unsupported_when_the_scheduler_is_off(settings, db_factory):
    off = context(replace(settings, run_scheduler=False), db_factory)
    assert jobs.check(off).status == "unsupported"


# --- response time and sign-in ---------------------------------------------------------------


def traffic(registry, minutes_ago, requests, errors, latency, *, signin_ok=0, signin_failed=0):
    when = NOW - timedelta(minutes=minutes_ago)
    for _ in range(requests):
        registry.count("http.requests", "workspaces", now=when)
        registry.observe("http.latency", latency, "all", now=when)
    for _ in range(errors):
        registry.count("http.errors", "workspaces", now=when)
    registry.count("auth.signin_ok", amount=signin_ok, now=when)
    registry.count("auth.signin_failed", amount=signin_failed, now=when)


def test_response_time_unknown_without_requests(settings, db_factory):
    ctx = context(settings, db_factory, registry=Registry())
    assert response_time.check(ctx).status == "unknown"


def test_response_time_statuses(settings, db_factory):
    healthy = Registry()
    traffic(healthy, 2, 30, 0, 40)
    assert response_time.check(context(settings, db_factory, registry=healthy)).status == "healthy"
    slow = Registry()
    traffic(slow, 2, 30, 0, 2000)
    assert response_time.check(context(settings, db_factory, registry=slow)).status == "degraded"
    failing = Registry()
    traffic(failing, 3, 40, 4, 40)
    result = response_time.check(context(settings, db_factory, registry=failing))
    assert result.status == "degraded"
    assert "failed" in result.detail


def test_response_time_ignores_error_rate_for_a_handful_of_requests(settings, db_factory):
    few = Registry()
    traffic(few, 2, 5, 2, 40)
    assert response_time.check(context(settings, db_factory, registry=few)).status == "healthy"


def test_response_time_ignores_the_open_minute_and_old_minutes(settings, db_factory):
    registry = Registry()
    traffic(registry, 0, 30, 0, 5000)  # still open
    traffic(registry, 9, 30, 0, 5000)  # outside 5 minutes
    assert response_time.check(context(settings, db_factory, registry=registry)).status == "unknown"


def test_response_time_unknown_when_stored_minutes_cannot_be_read(settings):
    assert response_time.check(context(settings, DownFactory(), registry=Registry())).status == "unknown"


def test_sign_in_statuses(settings, db_factory):
    quiet = context(settings, db_factory, registry=Registry())
    assert sign_in.check(quiet).status == "healthy"
    assert sign_in.check(quiet).value == 0
    normal = Registry()
    traffic(normal, 3, 0, 0, 0, signin_ok=20, signin_failed=2)
    assert sign_in.check(context(settings, db_factory, registry=normal)).status == "healthy"
    spike = Registry()
    traffic(spike, 3, 0, 0, 0, signin_ok=4, signin_failed=20)
    result = sign_in.check(context(settings, db_factory, registry=spike))
    assert (result.status, result.value) == ("degraded", 20)


def test_sign_in_needs_enough_attempts_to_call_a_spike(settings, db_factory):
    few = Registry()
    traffic(few, 3, 0, 0, 0, signin_failed=4)
    assert sign_in.check(context(settings, db_factory, registry=few)).status == "healthy"
    assert sign_in.check(context(settings, DownFactory(), registry=Registry())).status == "unknown"


# --- backups --------------------------------------------------------------------------------


def write_backup(directory, age, **overrides):
    values = {
        "finished_at": NOW - age,
        "result": "success",
        "size_bytes": 1000,
        "verification": "passed",
        "destination": "office-disk",
        "schema": "0029",
        "release": "1.0.0",
    }
    values.update(overrides)
    backup_status.write_status(directory, backup_status.BackupStatus(**values))


def with_status_dir(settings, db_factory, directory):
    return context(replace(settings, status_dir=directory), db_factory)


def test_backups_missing_file_is_unknown_not_healthy(settings, db_factory, tmp_path):
    for directory in (None, tmp_path):
        result = backups.check(with_status_dir(settings, db_factory, directory))
        assert (result.status, result.value) == ("unknown", None)


def test_backups_malformed_file_is_unknown(settings, db_factory, tmp_path):
    (tmp_path / backup_status.STATUS_FILENAME).write_text("{not json")
    assert backups.check(with_status_dir(settings, db_factory, tmp_path)).status == "unknown"


@pytest.mark.parametrize(
    ("age", "overrides", "status"),
    [
        (timedelta(hours=3), {}, "healthy"),
        (timedelta(hours=30), {}, "degraded"),
        (timedelta(hours=60), {}, "unavailable"),
        (
            timedelta(hours=1),
            {"result": "failure", "verification": "not_run", "size_bytes": None},
            "unavailable",
        ),
        (timedelta(hours=1), {"result": "failure", "verification": "failed"}, "unavailable"),
        (timedelta(hours=-2), {}, "unknown"),
    ],
)
def test_backups_age_and_verification(settings, db_factory, tmp_path, age, overrides, status):
    write_backup(tmp_path, age, **overrides)
    assert backups.check(with_status_dir(settings, db_factory, tmp_path)).status == status


def test_backups_never_show_destination_paths(settings, db_factory, tmp_path):
    write_backup(tmp_path, timedelta(hours=1))
    result = backups.check(with_status_dir(settings, db_factory, tmp_path))
    assert "office-disk" not in json.dumps(result.as_dict())
    assert str(tmp_path) not in json.dumps(result.as_dict())


# --- server ---------------------------------------------------------------------------------


def test_server_statuses(settings, db_factory):
    def check(**kw):
        return server.check(context(settings, db_factory, proc=FakeProc(**kw)))

    assert check().status == "healthy"
    assert check(rss=2 * GIB).status == "degraded"
    assert check(load=9.0).status == "degraded"
    assert check(memory=(8 * GIB, GIB // 2)).status == "degraded"


def test_server_unreadable_proc_is_unsupported_not_an_error(settings, db_factory):
    assert server.check(context(settings, db_factory, proc=FakeProc(fail=True))).status == "unsupported"


def test_server_real_proc_never_raises(settings, db_factory):
    assert server.check(context(settings, db_factory)).status in {"healthy", "degraded", "unsupported"}


# --- certificate ----------------------------------------------------------------------------


def write_certificate(directory, *, days, checked_hours=1, raw=None):
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    record = {
        "format": 1,
        "checked_at": (NOW - timedelta(hours=checked_hours)).strftime(stamp),
        "expires_at": (NOW + timedelta(days=days, hours=1)).strftime(stamp),
    }
    (directory / certificate.STATUS_FILENAME).write_text(raw or json.dumps(record))


def test_certificate_statuses(settings, db_factory, tmp_path):
    def check(**kw):
        write_certificate(tmp_path, **kw)
        return certificate.check(with_status_dir(settings, db_factory, tmp_path))

    assert check(days=90).status == "healthy"
    assert check(days=20).status == "degraded"
    assert (check(days=3).status, check(days=3).value) == ("unavailable", 3)
    expired = check(days=-4)
    assert expired.status == "unavailable"
    assert "expired" in expired.detail
    assert check(days=90, checked_hours=100).status == "stale"


def test_certificate_without_a_report_is_unsupported(settings, db_factory, tmp_path):
    assert certificate.check(with_status_dir(settings, db_factory, None)).status == "unsupported"
    assert certificate.check(with_status_dir(settings, db_factory, tmp_path)).status == "unsupported"


@pytest.mark.parametrize(
    "raw", ["{broken", '{"format": 1}', '{"format": 2, "checked_at": "x", "expires_at": "y"}', "[]"]
)
def test_certificate_malformed_report_is_unknown(settings, db_factory, tmp_path, raw):
    write_certificate(tmp_path, days=90, raw=raw)
    assert certificate.check(with_status_dir(settings, db_factory, tmp_path)).status == "unknown"


# --- overall --------------------------------------------------------------------------------


def test_overall_is_the_worst_status_ignoring_unsupported():
    assert worst(["healthy", "unsupported"]) == "healthy"
    assert worst(["healthy", "unknown"]) == "unknown"
    assert worst(["healthy", "degraded", "unknown"]) == "degraded"
    assert worst(["degraded", "unavailable", "stale"]) == "unavailable"
    assert worst(["unsupported"]) == "unknown"
