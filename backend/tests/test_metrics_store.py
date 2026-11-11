"""Metric flush, roll-up and retention against PostgreSQL (T62)."""

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import select

from labadda.cli import alembic_config
from labadda.metrics import rollup
from labadda.metrics.flush import flush, upsert
from labadda.metrics.registry import Registry, Sample
from labadda.models import ActivityDay, MetricSample

NOON = datetime(2026, 11, 11, 12, 0, 20, tzinfo=UTC)


def stored(db, resolution):
    rows = db.scalars(select(MetricSample).where(MetricSample.resolution == resolution)).all()
    return {(row.bucket_start, row.metric, row.dimension): (row.value, row.samples) for row in rows}


def test_flush_writes_closed_minutes_only(db_factory, ids):
    registry = Registry()
    registry.count("posts.created", "org", now=NOON)
    registry.count("posts.created", "org", now=NOON + timedelta(minutes=1))
    with db_factory() as db:
        assert flush(db, now=NOON + timedelta(minutes=1), registry=registry) == 1
        assert stored(db, "minute") == {(NOON.replace(second=0), "posts.created", "org"): (1.0, 1)}


def test_flush_retried_after_failing_between_commit_and_reset_counts_once(db_factory, ids, monkeypatch):
    registry = Registry()
    for _ in range(3):
        registry.count("chat.messages", "group", now=NOON)
    registry.observe("http.latency", 40.0, "chat", now=NOON)
    later = NOON + timedelta(minutes=2)

    def crash(_samples):
        raise RuntimeError("process stopped before reset")

    monkeypatch.setattr(registry, "discard", crash)
    with db_factory() as db, pytest.raises(RuntimeError):
        flush(db, now=later, registry=registry)
    monkeypatch.undo()
    with db_factory() as db:
        flush(db, now=later, registry=registry)
        assert flush(db, now=later, registry=registry) == 0
        rows = stored(db, "minute")
    minute = NOON.replace(second=0)
    assert rows[(minute, "chat.messages", "group")] == (3.0, 3)
    assert rows[(minute, "http.latency_p95", "chat")][1] == 1
    assert len(rows) == 3


def kolkata_rows():
    # 18:30 UTC is midnight in Asia/Kolkata: the first two minutes belong to 11 November,
    # the last two to 12 November (site-local).
    def at(hour, minute):
        return datetime(2026, 11, 11, hour, minute, tzinfo=UTC)

    return [
        Sample(at(18, 10), "posts.created", "org", 2, 2),
        Sample(at(18, 29), "posts.created", "org", 3, 3),
        Sample(at(18, 30), "posts.created", "org", 5, 5),
        Sample(at(19, 5), "posts.created", "org", 7, 7),
        Sample(at(18, 10), "sockets.connected", "", 4, 1),
        Sample(at(18, 29), "sockets.connected", "", 9, 1),
        Sample(at(18, 10), "http.latency_p95", "all", 100, 1),
        Sample(at(18, 29), "http.latency_p95", "all", 400, 3),
    ]


def test_roll_up_across_a_site_local_day_boundary(db_factory, ids, settings):
    site = replace(settings, timezone="Asia/Kolkata")
    now = datetime(2026, 11, 13, 0, 0, tzinfo=UTC)
    with db_factory() as db:
        upsert(db, "minute", kolkata_rows())
        db.commit()
        rollup.roll_up(db, site, now=now)
        hours = stored(db, "hour")
        days = stored(db, "day")
        rollup.roll_up(db, site, now=now)
        assert stored(db, "hour") == hours
        assert stored(db, "day") == days
    first_hour = datetime(2026, 11, 11, 17, 30, tzinfo=UTC)
    second_hour = datetime(2026, 11, 11, 18, 30, tzinfo=UTC)
    assert hours[(first_hour, "posts.created", "org")] == (5.0, 5)
    assert hours[(second_hour, "posts.created", "org")] == (12.0, 12)
    assert hours[(first_hour, "sockets.connected", "")] == (9.0, 2)
    assert hours[(first_hour, "http.latency_p95", "all")] == (325.0, 4)
    eleventh = datetime(2026, 11, 10, 18, 30, tzinfo=UTC)
    twelfth = datetime(2026, 11, 11, 18, 30, tzinfo=UTC)
    assert days[(eleventh, "posts.created", "org")] == (5.0, 5)
    assert days[(twelfth, "posts.created", "org")] == (12.0, 12)


def test_roll_up_leaves_the_current_hour_and_day_open(db_factory, ids, settings):
    now = datetime(2026, 11, 11, 18, 45, tzinfo=UTC)
    with db_factory() as db:
        upsert(
            db, "minute", [Sample(datetime(2026, 11, 11, 18, 40, tzinfo=UTC), "posts.created", "org", 1, 1)]
        )
        db.commit()
        rollup.roll_up(db, replace(settings, timezone="UTC"), now=now)
        assert stored(db, "hour") == {}
        assert stored(db, "day") == {}


def test_late_minutes_update_the_newest_hour_on_the_next_roll_up(db_factory, ids, settings):
    site = replace(settings, timezone="UTC")
    hour = datetime(2026, 11, 11, 10, 0, tzinfo=UTC)
    with db_factory() as db:
        upsert(db, "minute", [Sample(hour + timedelta(minutes=5), "tasks.created", "project", 1, 1)])
        db.commit()
        rollup.roll_up(db, site, now=hour + timedelta(hours=1, minutes=1))
        upsert(db, "minute", [Sample(hour + timedelta(minutes=59), "tasks.created", "project", 2, 2)])
        db.commit()
        rollup.roll_up(db, site, now=hour + timedelta(hours=1, minutes=2))
        assert stored(db, "hour") == {(hour, "tasks.created", "project"): (3.0, 3)}


def test_retention_deletes_only_expired_rows(db_factory, ids, settings):
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    keep_minute = now - timedelta(hours=47)
    old_minute = now - timedelta(hours=49)
    keep_hour = now - timedelta(days=34)
    old_hour = now - timedelta(days=36)
    keep_day = now - timedelta(days=729)
    old_day = now - timedelta(days=731)
    person = uuid.UUID(ids["users"]["asha"])
    with db_factory() as db:
        upsert(db, "minute", [Sample(t, "auth.signin_ok", "", 1, 1) for t in (keep_minute, old_minute)])
        upsert(db, "hour", [Sample(t, "auth.signin_ok", "", 1, 1) for t in (keep_hour, old_hour)])
        upsert(db, "day", [Sample(t, "auth.signin_ok", "", 1, 1) for t in (keep_day, old_day)])
        db.add_all(
            [
                ActivityDay(user_id=person, day=date(2024, 11, 12)),
                ActivityDay(user_id=person, day=date(2024, 11, 10)),
            ]
        )
        db.commit()
        rollup.expire(db, replace(settings, timezone="UTC"), now=now)
        db.commit()
        kept = {(row.resolution, row.bucket_start) for row in db.scalars(select(MetricSample))}
        days = set(db.scalars(select(ActivityDay.day)))
    assert kept == {("minute", keep_minute), ("hour", keep_hour), ("day", keep_day)}
    assert days == {date(2024, 11, 12)}


@pytest.fixture
def restore_head(migrated):
    yield migrated
    command.upgrade(alembic_config(migrated), "head")


def test_downgrade_refuses_while_metrics_exist(db_factory, ids, restore_head):
    with db_factory() as db:
        upsert(db, "minute", [Sample(NOON.replace(second=0), "auth.signin_ok", "", 1, 1)])
        db.commit()
    with pytest.raises(RuntimeError, match="Metrics or activity days exist"):
        command.downgrade(alembic_config(restore_head), "0026")
    with db_factory() as db:
        assert len(stored(db, "minute")) == 1
        db.execute(MetricSample.__table__.delete())
        db.add(ActivityDay(user_id=uuid.UUID(ids["users"]["ben"]), day=date(2026, 11, 11)))
        db.commit()
    with pytest.raises(RuntimeError, match="Metrics or activity days exist"):
        command.downgrade(alembic_config(restore_head), "0026")
    with db_factory() as db:
        db.execute(ActivityDay.__table__.delete())
        db.commit()
    command.downgrade(alembic_config(restore_head), "0026")
