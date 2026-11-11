"""T63: sampler results, deduplicated events, recovery, and acknowledgement never turning an item green."""

from dataclasses import replace
from datetime import timedelta

from sqlalchemy import func, select

from labadda.health import Sampler, events
from labadda.health.types import Result
from labadda.models import OpsEvent
from tests.health_support import NOW, context


def reading(status, at=NOW, detail="Reading."):
    return Result(status, 1, "ms", detail, at)


def apply(db_factory, item, status, previous, at=NOW):
    with db_factory() as db:
        events.apply(db, item, reading(status, at), previous)
        db.commit()


def rows(db_factory):
    with db_factory() as db:
        return db.scalars(select(OpsEvent).order_by(OpsEvent.id)).all()


def test_a_problem_raises_one_event_and_repeats_only_count(ids, db_factory):
    apply(db_factory, "database", "unavailable", None)
    apply(db_factory, "database", "unavailable", "unavailable", NOW + timedelta(seconds=15))
    (event,) = rows(db_factory)
    assert (event.code, event.component, event.severity, event.state, event.count) == (
        "database.unavailable",
        "database",
        "error",
        "open",
        1,
    )
    # Seen again after a lapse (a restart forgets what was reported): a repeat, not a new row.
    apply(db_factory, "database", "unavailable", None, NOW + timedelta(minutes=5))
    (event,) = rows(db_factory)
    assert event.count == 2
    assert event.last_at == NOW + timedelta(minutes=5)
    assert event.first_at == NOW


def test_recovery_resolves_and_a_new_failure_opens_a_new_event(ids, db_factory):
    apply(db_factory, "backups", "degraded", None)
    apply(db_factory, "backups", "healthy", "degraded", NOW + timedelta(minutes=1))
    (event,) = rows(db_factory)
    assert (event.state, event.resolved_at) == ("resolved", NOW + timedelta(minutes=1))
    apply(db_factory, "backups", "degraded", "healthy", NOW + timedelta(minutes=2))
    assert [(e.state, e.count) for e in rows(db_factory)] == [("resolved", 1), ("open", 1)]


def test_changing_problem_word_supersedes_the_older_event(ids, db_factory):
    apply(db_factory, "server", "degraded", None)
    apply(db_factory, "server", "unavailable", "degraded", NOW + timedelta(seconds=15))
    assert [(e.code, e.state) for e in rows(db_factory)] == [
        ("server.degraded", "resolved"),
        ("server.unavailable", "open"),
    ]


def test_unknown_and_unsupported_neither_raise_nor_resolve(ids, db_factory):
    apply(db_factory, "certificate", "unknown", None)
    apply(db_factory, "certificate", "unsupported", None)
    assert rows(db_factory) == []
    apply(db_factory, "database", "unavailable", None)
    apply(db_factory, "database", "unknown", "unavailable")
    assert [e.state for e in rows(db_factory)] == ["open"]


def test_an_acknowledged_event_is_not_duplicated_and_resolves_on_recovery(ids, db_factory):
    apply(db_factory, "jobs", "degraded", None)
    with db_factory() as db:
        event = db.scalar(select(OpsEvent))
        event.state = "acknowledged"
        db.commit()
    apply(db_factory, "jobs", "degraded", None, NOW + timedelta(minutes=3))
    (event,) = rows(db_factory)
    assert (event.state, event.count) == ("acknowledged", 2)
    apply(db_factory, "jobs", "healthy", "degraded", NOW + timedelta(minutes=4))
    assert rows(db_factory)[0].state == "resolved"


def test_event_contents_are_metadata_only(ids, db_factory):
    apply(db_factory, "file_storage", "degraded", None)
    (event,) = rows(db_factory)
    assert set(event.detail) == {"status", "value", "unit", "message"}
    assert event.summary.startswith("File storage is degraded.")


# --- sampler --------------------------------------------------------------------------------


def sampler(settings, db_factory, **overrides):
    return Sampler(context(replace(settings, environment="test"), db_factory, **overrides))


def test_sampler_serves_not_checked_yet_as_unknown(ids, settings, db_factory):
    rows_ = sampler(settings, db_factory).snapshot()
    assert {result.status for _, result, _ in rows_} == {"unknown"}
    assert len(rows_) == 10


def test_sampler_measures_every_item_and_records_events(ids, settings, db_factory):
    target = sampler(settings, db_factory, expected_schema=lambda: "9999")
    assert target.run_once()
    by_key = {key: result for key, result, _ in target.snapshot()}
    assert len(by_key) == 10
    assert by_key["application"].status == "degraded"
    assert by_key["database"].status == "healthy"
    assert [e.code for e in rows(db_factory)] == ["application.degraded"]
    assert target.overall() == "degraded"


def test_a_recovered_item_resolves_its_event_on_the_next_sample(ids, settings, db_factory):
    expected = ["9999"]
    target = sampler(settings, db_factory, expected_schema=lambda: expected[0])
    target.run_once()
    assert [e.state for e in rows(db_factory)] == ["open"]
    from labadda.app import expected_schema_head

    expected[0] = expected_schema_head()
    target.run_once()
    assert [e.state for e in rows(db_factory)] == ["resolved"]


def test_old_results_are_served_as_stale_but_events_keep_the_real_status(ids, settings, db_factory):
    clock = [NOW]
    target = sampler(settings, db_factory, now=lambda: clock[0])
    target.run_once()
    clock[0] = NOW + timedelta(seconds=90)
    by_key = {key: (result, age) for key, result, age in target.snapshot()}
    assert by_key["database"][0].status == "stale"
    assert by_key["database"][1] == 90
    assert by_key["certificate"][0].status == "unsupported"  # an unmeasurable item never turns stale
    assert target.current_status("database") == "healthy"
    assert target.due(clock[0]) is True
    assert target.due(NOW + timedelta(seconds=5)) is False


def test_an_item_that_raises_is_unknown_and_the_others_still_run(ids, settings, db_factory):
    def explode(ctx):
        raise RuntimeError("boom with a secret path /srv/x")

    from labadda.health import catalog
    from labadda.health import sampler as sampler_module

    original = catalog.ITEMS
    broken = (replace(original[0], check=explode), *original[1:])
    sampler_module.ITEMS = broken
    try:
        target = sampler(settings, db_factory)
        target.run_once()
    finally:
        sampler_module.ITEMS = original
    by_key = {key: result for key, result, _ in target.snapshot()}
    assert by_key["application"].status == "unknown"
    assert "secret" not in by_key["application"].detail
    assert by_key["database"].status == "healthy"


def test_forced_states_apply_only_in_test_environments(ids, settings, db_factory):
    forced = replace(settings, test_health_force="database=degraded, nonsense=degraded,server=bogus")
    target = Sampler(context(forced, db_factory))
    target.run_once()
    by_key = {key: result for key, result, _ in target.snapshot()}
    assert by_key["database"].status == "degraded"
    assert "test-only" in by_key["database"].detail
    assert by_key["server"].status != "bogus"
    pilot = replace(forced, environment="pilot")
    real = Sampler(context(pilot, db_factory))
    real.run_once()
    assert {key: r.status for key, r, _ in real.snapshot()}["database"] == "healthy"


def test_events_are_retried_when_the_database_write_fails(ids, settings, db_factory):
    target = sampler(settings, db_factory, expected_schema=lambda: "9999")
    real_factory = target.context.factory
    target.context.factory = lambda: (_ for _ in ()).throw(ConnectionError("down"))
    target.run_once()  # measuring itself reports unknown / unavailable; nothing may crash
    target.context.factory = real_factory
    target.run_once()
    assert [e.code for e in rows(db_factory)] == ["application.degraded"]
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(OpsEvent)) == 1


# --- migration ------------------------------------------------------------------------------


def test_downgrade_refuses_while_events_exist(migrated, db_factory, ids):
    import pytest
    from alembic import command

    from labadda.cli import alembic_config

    apply(db_factory, "database", "unavailable", None)
    try:
        with pytest.raises(RuntimeError, match="Operational events exist"):
            command.downgrade(alembic_config(migrated), "0029")
        with db_factory() as db:
            assert db.scalar(select(func.count()).select_from(OpsEvent)) == 1
            db.execute(OpsEvent.__table__.delete())
            db.commit()
        command.downgrade(alembic_config(migrated), "0029")
    finally:
        command.upgrade(alembic_config(migrated), "head")
