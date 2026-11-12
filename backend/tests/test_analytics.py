"""Activity summary: periods, unknown states, totals, access, export and no content (T61, T64)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from labadda import analytics
from labadda.analytics.cache import ResultCache
from labadda.analytics.features import FEATURE_METRICS
from labadda.analytics.periods import windows
from labadda.metrics import REGISTRY
from labadda.metrics.flush import flush
from labadda.models import AuditEvent
from labadda.people import site_date
from tests.analytics_support import fresh_cache, mark_active, store, tile
from tests.test_capabilities import grant
from tests.test_metrics_api import SECRETS, seed_content
from tests.test_panel import PANEL, pair

__all__ = ["fresh_cache"]

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 11)
PATHS = ("/admin/analytics/summary", "/admin/analytics/units", "/admin/analytics/export.csv")


def summary(db_factory, settings, period="7d", now=NOW):
    with db_factory() as db:
        return analytics.build_summary(db, settings, period, now=now)


def units(db_factory, settings, period="7d", now=NOW):
    with db_factory() as db:
        return analytics.build_units(db, settings, period, now=now)


def test_empty_installation_is_unknown_not_zero(db_factory, settings, ids):
    found = summary(db_factory, settings)
    assert found["state"] == "unknown"
    assert found["tiles"] == []
    assert found["charts"] is None
    assert units(db_factory, settings)["state"] == "unknown"
    assert units(db_factory, settings)["units"] == []


def test_unmeasured_figures_stay_unknown_beside_measured_people(db_factory, settings, ids):
    mark_active(db_factory, [ids["users"]["ben"]], TODAY)
    found = summary(db_factory, settings)
    assert found["state"] == "measured"
    assert tile(found, "active_day")["value"] == 1
    assert tile(found, "active_day")["previous"] is None
    for key in ("items_created", "peak_connections"):
        assert tile(found, key)["state"] == "unknown"
        assert tile(found, key)["value"] is None
    assert found["charts"]["weekday_hour"]["state"] == "unknown"
    assert [point["value"] for point in found["charts"]["active_per_day"]] == [None] * 6 + [1]
    assert all(point["values"] is None for point in found["charts"]["features"]["points"])


def test_periods_and_their_previous_period_cover_whole_site_days(settings):
    kolkata = replace(settings, timezone="Asia/Kolkata")
    late = datetime(2026, 11, 10, 19, 0, tzinfo=UTC)
    current, previous = windows("7d", kolkata, now=late)
    assert (current.first, current.last) == (date(2026, 11, 5), date(2026, 11, 11))
    assert current.start == datetime(2026, 11, 4, 18, 30, tzinfo=UTC)
    assert (previous.first, previous.last) == (date(2026, 10, 29), date(2026, 11, 4))
    year, before = windows("12m", kolkata, now=late)
    assert year.days == 365
    assert before.last == year.first - timedelta(days=1)


def test_counts_follow_the_site_time_zone(db_factory, settings, ids):
    kolkata = replace(settings, timezone="Asia/Kolkata")
    late = datetime(2026, 11, 10, 19, 0, tzinfo=UTC)
    store(
        db_factory,
        "minute",
        (datetime(2026, 11, 10, 18, 15, tzinfo=UTC), "posts.created", "org", 2),
        (datetime(2026, 11, 10, 18, 45, tzinfo=UTC), "posts.created", "org", 3),
        (datetime(2026, 11, 10, 18, 15, tzinfo=UTC), "http.requests", "board", 20),
        (datetime(2026, 11, 10, 18, 45, tzinfo=UTC), "http.requests", "chat", 30),
    )
    found = summary(db_factory, kolkata, now=late)
    points = {point["start"]: point["values"] for point in found["charts"]["features"]["points"]}
    assert points["2026-11-10"]["posts.created"] == 2
    assert points["2026-11-11"]["posts.created"] == 3
    in_utc = summary(db_factory, settings, now=late)
    assert {p["start"]: p["values"] for p in in_utc["charts"]["features"]["points"]}["2026-11-10"] == {
        **dict.fromkeys(FEATURE_METRICS, 0.0),
        "posts.created": 5.0,
    }
    heat = {(c["weekday"], c["hour"]): c["value"] for c in found["charts"]["weekday_hour"]["cells"]}
    assert (heat[(2, 23)], heat[(3, 0)], sum(heat.values())) == (20, 30, 50)


def test_rolled_up_buckets_are_not_counted_twice(db_factory, settings, ids):
    yesterday = datetime(2026, 11, 10, tzinfo=UTC)
    store(db_factory, "day", (yesterday, "chat.messages", "group", 10))
    store(
        db_factory,
        "hour",
        (yesterday + timedelta(hours=5), "chat.messages", "group", 10),
        (NOW - timedelta(hours=2), "chat.messages", "group", 4),
    )
    store(
        db_factory,
        "minute",
        (NOW - timedelta(hours=2), "chat.messages", "group", 4),
        (NOW - timedelta(minutes=3), "chat.messages", "group", 1),
    )
    found = summary(db_factory, settings)
    assert tile(found, "items_created")["value"] == 15
    assert found["charts"]["items_by_kind"] == [
        {"key": "org", "label": "Organisation units", "value": 0},
        {"key": "project", "label": "Projects", "value": 0},
        {"key": "group", "label": "Groups", "value": 15.0},
    ]


def test_tiles_compare_with_the_previous_period(db_factory, settings, ids):
    people = [ids["users"][name] for name in ("asha", "ben", "chen")]
    mark_active(db_factory, people, TODAY)
    mark_active(db_factory, people[:1], TODAY - timedelta(days=8))
    store(
        db_factory,
        "hour",
        (NOW - timedelta(hours=3), "sockets.connected", "", 7),
        (NOW - timedelta(days=9), "sockets.connected", "", 2),
        (NOW - timedelta(days=9), "uploads.size_band", "under_1mb", 2),
        (NOW - timedelta(hours=3), "uploads.size_band", "under_1mb", 3),
        (NOW - timedelta(hours=3), "assets.bytes", "", 4096),
    )
    found = summary(db_factory, settings)
    assert (tile(found, "active_day")["value"], tile(found, "active_day")["previous"]) == (3, 0)
    assert (tile(found, "active_week")["value"], tile(found, "active_week")["previous"]) == (3, 1)
    share = tile(found, "active_share")
    assert share["accounts"] == 6
    assert share["value"] == pytest.approx(0.5)
    assert (tile(found, "peak_connections")["value"], tile(found, "peak_connections")["previous"]) == (7, 2)
    sizes = {band["key"]: band["value"] for band in found["charts"]["upload_sizes"]}
    assert sizes == {"under_100kb": 0, "under_1mb": 3, "under_10mb": 0, "10mb_or_more": 0}
    assert found["charts"]["storage"] == [
        {"day": "2026-11-11", "files_bytes": 4096.0, "database_bytes": None}
    ]


def test_long_periods_use_coarser_feature_buckets(db_factory, settings, ids):
    store(db_factory, "day", (datetime(2026, 3, 4, tzinfo=UTC), "posts.created", "org", 1))
    year = summary(db_factory, settings, "12m")
    assert year["charts"]["features"]["bucket"] == "month"
    assert len(year["charts"]["features"]["points"]) == 13
    assert summary(db_factory, settings, "90d")["state"] == "unknown"
    store(db_factory, "day", (datetime(2026, 10, 1, tzinfo=UTC), "posts.created", "org", 1))
    quarter = summary(db_factory, settings, "90d")
    assert quarter["charts"]["features"]["bucket"] == "week"
    assert all(
        date.fromisoformat(p["start"]).weekday() == 0 for p in quarter["charts"]["features"]["points"][1:]
    )


def test_result_cache_serves_for_sixty_seconds():
    cache = ResultCache()
    builds = []

    def build():
        builds.append(1)
        return {"n": len(builds)}

    assert cache.get("k", build, clock=lambda: 100.0) == {"n": 1}
    assert cache.get("k", build, clock=lambda: 159.0) == {"n": 1}
    assert cache.get("k", build, clock=lambda: 160.0) == {"n": 2}


@pytest.mark.parametrize("path", PATHS)
def test_administrator_and_usage_reader_may_read(as_user, ids, path):
    assert as_user("admin").get(path, params={"period": "90d"}).status_code == 200
    assert grant(as_user("admin"), ids["users"]["ben"]).status_code == 201
    assert as_user("ben").get(path).status_code == 200


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("username", ["asha", "chen", "dana", "eli", "ben"])
def test_members_without_a_grant_are_forbidden(as_user, username, path):
    response = as_user(username).get(path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "usage_read_required"


@pytest.mark.parametrize("path", PATHS)
def test_signed_out_deactivated_and_panel_sessions_are_refused(as_user, make_client, ids, path):
    client = make_client()
    assert client.get(path).status_code == 401
    assert client.login("fay").status_code == 401
    assert client.get(path).status_code == 401
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.get(path).status_code == 401
    assert as_user("admin").get(path, headers=PANEL).status_code == 401


def test_usage_reader_cannot_write_through_analytics(as_user, ids):
    assert grant(as_user("admin"), ids["users"]["ben"]).status_code == 201
    response = as_user("ben").post("/admin/analytics/summary", json={})
    assert response.status_code == 405


def test_unknown_period_is_rejected(as_user):
    response = as_user("admin").get("/admin/analytics/summary", params={"period": "14d"})
    assert response.status_code == 422


def test_slow_query_reports_unavailable(as_user, monkeypatch):
    def cancelled(*args, **kwargs):
        raise OperationalError("select", {}, Exception("canceling statement due to statement timeout"))

    monkeypatch.setitem(analytics_api().BUILDERS, "summary", cancelled)
    response = as_user("admin").get("/admin/analytics/summary")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "analytics_unavailable"


def analytics_api():
    from labadda.api import analytics as module

    return module


def test_export_is_audited_and_shows_only_protected_figures(as_user, ids, db_factory, settings):
    today = site_date(settings)
    mark_active(db_factory, [ids["users"]["asha"], ids["users"]["ben"]], today)
    assert grant(as_user("admin"), ids["users"]["dana"]).status_code == 201
    response = as_user("dana").get("/admin/analytics/export.csv", params={"period": "7d"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert body.startswith("﻿section,item,this period,previous period")
    assert "Active people by home unit,Thin Films Section,fewer than 5," in body
    with db_factory() as db:
        event = db.scalars(select(AuditEvent).where(AuditEvent.action == "analytics.export")).one()
    assert str(event.actor_id) == ids["users"]["dana"]
    assert event.detail == {"period": "last 7 days", "rows": str(body.count("\n") - 1)}


def test_no_content_in_any_analytics_response(as_user, ids, db_factory):
    seed_content(as_user("ben"), ids["workspaces"]["section_a"])
    with db_factory() as db:
        assert flush(db, now=datetime.now(UTC) + timedelta(minutes=2), registry=REGISTRY) > 0
    admin = as_user("admin")
    hidden = (*SECRETS, "Project Aurora", "Microscopy Reading Club", "Invite-only pilot project")
    for period in analytics.PERIOD_DAYS:
        analytics.CACHE.clear()
        for path in PATHS:
            response = admin.get(path, params={"period": period})
            assert response.status_code == 200
            for secret in hidden:
                assert secret not in response.text
