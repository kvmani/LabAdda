"""Request metrics, activity days and the scheduler collector (T62)."""

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from labadda.metrics import REGISTRY, Collector, MetricsMiddleware
from labadda.metrics.activity import ACTIVITY
from labadda.metrics.middleware import route_group
from labadda.metrics.registry import Registry
from labadda.models import ActivityDay, MetricSample

from .test_panel import pair, ws


def closed_counts(metric):
    rows = REGISTRY.closed(datetime.now(UTC) + timedelta(minutes=2))
    return {row.dimension: row.value for row in rows if row.metric == metric}


@pytest.mark.parametrize(
    ("template", "group"),
    [
        ("/api/v1/workspaces/{workspace_id}/chat/{message_id}/replies", "chat"),
        ("/api/v1/workspaces/{workspace_id}/board/ops", "board"),
        ("/api/v1/workspaces/{workspace_id}/members", "workspaces"),
        ("/api/v1/posts/{post_id}/replies", "noticeboard"),
        ("/api/v1/admin/people/{user_id}", "admin"),
        ("/api/v1/unlisted", "other"),
        ("/{path:path}", "other"),
        (None, "other"),
    ],
)
def test_route_group_comes_from_the_template(template, group):
    assert route_group(template, "/api/v1") == group


def test_api_requests_are_counted_by_group_without_ids(as_user, ids):
    asha = as_user("asha")
    assert asha.get(f"/workspaces/{ws(ids)}/chat").status_code == 200
    assert asha.get(f"/workspaces/{uuid.uuid4()}/chat").status_code == 404
    requests = closed_counts("http.requests")
    assert requests["chat"] == 2
    assert requests["auth"] == 1
    assert all(ids["workspaces"]["section_a"] not in dimension for dimension in requests)
    latency = closed_counts("http.latency_p95")
    assert set(latency) == {"chat", "auth", "all"}


def test_probes_assets_and_web_shell_are_not_counted(app, settings):
    client = TestClient(app)
    base = settings.base_path
    for path in ("/healthz", "/readyz", "/assets/app.js", "/notes", "/"):
        client.get(base + path)
    assert closed_counts("http.requests") == {}
    assert closed_counts("http.latency_p50") == {}


def test_server_errors_are_counted_as_errors():
    registry = Registry()
    app = FastAPI()

    @app.get("/api/v1/posts/{post_id}")
    def failing(post_id: str):
        raise RuntimeError("fixture failure")

    app.add_middleware(MetricsMiddleware, api_prefix="/api/v1", registry=registry)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/v1/posts/abc").status_code == 500
    rows = registry.closed(datetime.now(UTC) + timedelta(minutes=2))
    errors = {row.dimension: row.value for row in rows if row.metric == "http.errors"}
    assert errors == {"noticeboard": 1}


def activity(db_factory):
    with db_factory() as db:
        return set(db.execute(select(ActivityDay.user_id, ActivityDay.day)).all())


def test_activity_is_written_once_per_person_per_day(as_user, ids, db_factory, settings):
    asha = as_user("asha")
    assert asha.get("/auth/session").status_code == 200
    asha_id = uuid.UUID(ids["users"]["asha"])
    assert {row.user_id for row in activity(db_factory)} == {asha_id}
    with db_factory() as db:
        db.execute(delete(ActivityDay))
        db.commit()
    # The second request is answered from the "seen today" set: no database write.
    assert asha.get("/auth/session").status_code == 200
    assert activity(db_factory) == set()


def test_activity_records_the_site_local_day(db_factory, ids, settings):
    site = replace(settings, timezone="Asia/Kolkata")
    person = uuid.UUID(ids["users"]["bharat"])
    with db_factory() as db:
        ACTIVITY.record(db, person, site, now=datetime(2026, 11, 11, 18, 0, tzinfo=UTC))
        ACTIVITY.record(db, person, site, now=datetime(2026, 11, 11, 18, 20, tzinfo=UTC))
        ACTIVITY.record(db, person, site, now=datetime(2026, 11, 11, 18, 40, tzinfo=UTC))
    assert activity(db_factory) == {(person, date(2026, 11, 11)), (person, date(2026, 11, 12))}


def test_panel_sessions_and_failed_sign_ins_record_no_activity(as_user, make_client, ids, db_factory):
    panel = pair(as_user, make_client, ids)
    with db_factory() as db:
        db.execute(delete(ActivityDay))
        db.commit()
    ACTIVITY.reset()
    assert panel.get(f"/workspaces/{ws(ids)}/board").status_code == 200
    assert make_client().login("asha", "wrong-password-1").status_code == 401
    assert make_client().login("farhan").status_code == 401
    assert make_client().get("/auth/session").status_code == 401
    assert activity(db_factory) == set()


def test_collector_samples_gauges_flushes_and_waits_for_the_interval(db_factory, ids, settings):
    registry = Registry()
    collector = Collector(db_factory, settings, lambda: 3, registry=registry)
    first = datetime(2026, 11, 11, 12, 0, 10, tzinfo=UTC)
    collector.tick(first)
    collector.tick(first + timedelta(seconds=30))
    with db_factory() as db:
        assert db.scalars(select(MetricSample)).all() == []
    collector.tick(first + timedelta(seconds=70))
    with db_factory() as db:
        rows = {row.metric: row for row in db.scalars(select(MetricSample))}
    assert rows["sockets.connected"].value == 3
    assert rows["sockets.connected"].bucket_start == first.replace(second=0)
    assert rows["db.size_bytes"].value > 0
    assert rows["sessions.active"].value == 0
    assert rows["assets.bytes"].value == 0


def test_unreadable_gauge_is_left_unknown_not_zero(db_factory, ids, settings, tmp_path):
    registry = Registry()
    missing = replace(settings, asset_dir=tmp_path / "not-mounted")
    Collector(db_factory, missing, lambda: 0, registry=registry).tick(
        datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    )
    later = datetime(2026, 11, 11, 12, 2, tzinfo=UTC)
    names = {row.metric for row in registry.closed(later)}
    assert "disk.free_bytes" not in names
    assert "db.size_bytes" in names
