"""Console Insights: feature momentum, performance, small-group floor, access and no content."""

from datetime import UTC, date, datetime, timedelta

import pytest

from labadda import insights
from labadda.insights.trends import classify, horizon_window
from labadda.metrics.flush import upsert
from labadda.metrics.registry import Sample
from tests.analytics_support import add_people, fresh_cache, mark_active, store
from tests.test_capabilities import grant
from tests.test_metrics_api import SECRETS, seed_content
from tests.test_panel import PANEL, pair

__all__ = ["fresh_cache"]

# A Wednesday; the current week began on Monday 9 November.
NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
MONDAY = date(2026, 11, 9)
PATHS = ("/admin/insights/trends", "/admin/insights/performance")


def trends(db_factory, settings, weeks=12, now=NOW):
    with db_factory() as db:
        return insights.build_trends(db, settings, weeks, now=now)


def performance(db_factory, settings, span="7d", now=NOW):
    with db_factory() as db:
        return insights.build_performance(db, settings, span, now=now)


def noon(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=6)


def busy_weeks(db_factory, weekly: dict[str, list[float]], people: int = 6):
    """Store per-feature weekly totals for complete weeks ending last week, oldest first."""
    crowd = add_people(db_factory, None, people, "trend")
    length = len(next(iter(weekly.values())))
    for index in range(length):
        week = MONDAY - timedelta(weeks=length - index)
        mark_active(db_factory, crowd, week + timedelta(days=1))
        rows = [
            (noon(week + timedelta(days=1)), metric, "org", values[index])
            for metric, values in weekly.items()
        ]
        store(db_factory, "day", *rows)


@pytest.mark.parametrize(
    ("recent", "prior", "share", "expected"),
    [
        (None, 3.0, 0.1, "unknown"),
        (0.0, 0.0, 0.0, "unused"),
        (4.0, 0.0, 0.5, "new"),
        (0.0, 4.0, 0.0, "dormant"),
        (13.0, 10.0, 0.1, "growing"),
        (7.0, 10.0, 0.1, "declining"),
        (10.5, 10.0, 0.4, "core"),
        (10.5, 10.0, 0.1, "steady"),
    ],
)
def test_classification(recent, prior, share, expected):
    assert classify(recent, prior, share) == expected


def test_horizon_is_whole_weeks_ending_with_the_current_week(settings):
    window = horizon_window(settings, 8, now=NOW)
    assert window.first.weekday() == 0
    assert window.first == MONDAY - timedelta(weeks=7)
    assert window.last == date(2026, 11, 11)


def test_empty_installation_is_unknown(db_factory, settings, ids):
    found = trends(db_factory, settings)
    assert found["state"] == "unknown"
    assert found["features"] == []
    assert performance(db_factory, settings)["state"] == "unknown"


def test_momentum_names_rising_falling_and_unused_features(db_factory, settings, ids):
    busy_weeks(
        db_factory,
        {
            "chat.messages": [10, 10, 10, 10, 20, 20, 20, 20],
            "posts.created": [10, 10, 10, 10, 4, 4, 4, 4],
            "tasks.created": [5, 5, 5, 5, 0, 0, 0, 0],
            "uploads.count": [0, 0, 0, 0, 3, 3, 3, 3],
        },
    )
    found = trends(db_factory, settings)
    assert found["state"] == "measured"
    by_key = {row["key"]: row for row in found["features"]}
    assert by_key["chat.messages"]["trend"] == "growing"
    assert by_key["chat.messages"]["change"] == pytest.approx(1.0)
    assert by_key["chat.messages"]["weekly_recent"] == pytest.approx(20)
    assert by_key["posts.created"]["trend"] == "declining"
    assert by_key["tasks.created"]["trend"] == "dormant"
    assert by_key["uploads.count"]["trend"] == "new"
    assert by_key["board.operations"]["trend"] == "unused"
    assert by_key["chat.messages"]["share"] == pytest.approx(20 / 27)
    assert by_key["chat.messages"]["per_person"] == pytest.approx(20 / 6)
    assert found["features"][0]["trend"] == "growing"
    assert all(row["advice"] for row in found["features"])
    assert found["people"]["weekly_recent"] == pytest.approx(6)
    assert found["points"][-1]["partial"] is True


def test_weeks_with_fewer_than_five_people_are_suppressed(db_factory, settings, ids):
    busy_weeks(db_factory, {"chat.messages": [9, 9, 9, 9, 9, 9, 9, 9]}, people=4)
    found = trends(db_factory, settings)
    assert found["state"] == "suppressed"
    assert found["features"] == []
    assert found["people"] is None
    assert all(point["values"] is None for point in found["points"])


def test_performance_merges_resolutions_and_ranks_slow_areas(db_factory, settings, ids):
    hour = datetime(2026, 11, 11, 6, 30, tzinfo=UTC)
    store(
        db_factory,
        "hour",
        (hour, "http.requests", "chat", 100),
        (hour, "http.errors", "chat", 5),
        (hour, "http.requests", "board", 50),
    )
    with db_factory() as db:
        upsert(
            db,
            "hour",
            [
                Sample(hour, "http.latency_p95", "chat", 1500, 100),
                Sample(hour, "http.latency_p95", "board", 200, 50),
                Sample(hour, "http.latency_p95", "all", 1000, 150),
                Sample(hour, "http.latency_p50", "all", 80, 150),
            ],
        )
        minute = hour + timedelta(hours=1, minutes=5)
        upsert(
            db,
            "minute",
            [
                Sample(minute, "http.requests", "chat", 10, 10),
                Sample(minute, "http.latency_p95", "all", 100, 10),
                Sample(minute, "auth.signin_failed", "", 2, 2),
                Sample(minute, "auth.signin_ok", "", 30, 30),
                # Already covered by the hour row: must not be counted twice.
                Sample(hour + timedelta(minutes=1), "http.requests", "chat", 999, 1),
            ],
        )
        db.commit()
    found = performance(db_factory, settings, "24h")
    assert found["state"] == "measured"
    current = found["current"]
    assert current["requests"] == 160
    assert current["errors"] == 5
    assert current["error_rate"] == pytest.approx(5 / 160)
    assert current["p95_ms"] == pytest.approx(round((1000 * 150 + 100 * 10) / 160, 1))
    assert current["signin_failure_rate"] == pytest.approx(2 / 32)
    assert [group["key"] for group in found["groups"]] == ["chat", "board"]
    assert found["groups"][0]["status"] == "degraded"
    assert found["groups"][1]["status"] == "healthy"
    assert [point["requests"] for point in found["points"]] == [150, 10]


def test_day_spans_use_day_rows_then_finer_rows(db_factory, settings, ids):
    store(
        db_factory,
        "day",
        (datetime(2026, 11, 1, 18, 30, tzinfo=UTC), "http.requests", "tasks", 40),
    )
    store(db_factory, "hour", (datetime(2026, 11, 11, 4, 30, tzinfo=UTC), "http.requests", "tasks", 7))
    found = performance(db_factory, settings, "30d")
    assert found["bucket"] == "day"
    assert found["current"]["requests"] == 47
    assert found["previous"] is None


@pytest.mark.parametrize("path", PATHS)
def test_access_matches_other_operational_pages(as_user, make_client, ids, path):
    assert as_user("admin").get(path).status_code == 200
    for username in ("asha", "chitra", "deepa"):
        response = as_user(username).get(path)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "usage_read_required"
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    assert as_user("bharat").get(path).status_code == 200
    assert make_client().get(path).status_code == 401
    assert as_user("admin").get(path, headers=PANEL).status_code == 401
    assert pair(as_user, make_client, ids).get(path).status_code == 401


def test_invalid_choices_are_rejected(as_user):
    response = as_user("admin").get("/admin/insights/trends", params={"weeks": 5})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_weeks"
    assert as_user("admin").get("/admin/insights/performance", params={"span": "1y"}).status_code == 422


def test_no_content_reaches_insights(as_user, ids):
    seed_content(as_user("bharat"), ids["workspaces"]["section_a"])
    admin = as_user("admin")
    for path in PATHS:
        body = admin.get(path).text
        assert not any(secret in body for secret in SECRETS)
