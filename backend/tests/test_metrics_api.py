"""GET /admin/metrics/series: access, validation and no content anywhere (T61, T62)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from labadda.metrics import REGISTRY, catalog
from labadda.metrics.flush import flush, upsert
from labadda.metrics.registry import Sample
from labadda.models import ActivityDay, MetricSample
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair

START = datetime(2026, 11, 11, 10, 0, tzinfo=UTC)
PATH = "/admin/metrics/series"


def window(**overrides):
    params = {
        "metric": "posts.created",
        "dimension": "org",
        "resolution": "hour",
        "from": START.isoformat(),
        "to": (START + timedelta(hours=3)).isoformat(),
    }
    params.update(overrides)
    return {key: value for key, value in params.items() if value is not None}


def seed_hours(db_factory):
    rows = [
        Sample(START + timedelta(hours=offset), "posts.created", "org", offset + 1, 1) for offset in (2, 0, 5)
    ]
    rows.append(Sample(START, "posts.created", "project", 9, 9))
    rows.append(Sample(START, "posts.created", "org", 99, 1))
    with db_factory() as db:
        upsert(db, "hour", rows[:4])
        upsert(db, "minute", rows[4:])
        db.commit()


def test_administrator_reads_one_series_in_order_within_the_period(as_user, db_factory):
    seed_hours(db_factory)
    response = as_user("admin").get(PATH, params=window())
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "counter"
    assert body["unit"] == "count"
    assert body["resolution"] == "hour"
    assert [(point["bucket_start"], point["value"]) for point in body["points"]] == [
        (START.isoformat(), 1.0),
        ((START + timedelta(hours=2)).isoformat(), 3.0),
    ]


def test_usage_reader_may_read_series(as_user, ids, db_factory):
    seed_hours(db_factory)
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    response = as_user("bharat").get(PATH, params=window(metric="http.latency_p95", dimension="all"))
    assert response.status_code == 200
    assert response.json()["unit"] == "ms"
    assert response.json()["points"] == []


@pytest.mark.parametrize("username", ["asha", "chitra", "deepa", "esha", "bharat"])
def test_members_without_a_grant_are_forbidden(as_user, username):
    response = as_user(username).get(PATH, params=window())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "usage_read_required"


def test_signed_out_deactivated_and_panel_sessions_are_refused(as_user, make_client, ids):
    client = make_client()
    assert client.get(PATH, params=window()).status_code == 401
    assert client.login("farhan").status_code == 401
    assert client.get(PATH, params=window()).status_code == 401
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.get(PATH, params=window()).status_code == 401
    assert as_user("admin").get(PATH, params=window(), headers=PANEL).status_code == 401


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"metric": "posts.deleted"}, "unknown_metric"),
        ({"metric": "http.latency"}, "unknown_metric"),
        ({"dimension": "division"}, "unknown_dimension"),
        ({"dimension": f"unit:{uuid.uuid4()}"}, "unit_series_not_available"),
        ({"dimension": catalog.UNIT_OVERFLOW}, "unit_series_not_available"),
        ({"to": START.isoformat()}, "invalid_range"),
        ({"resolution": "minute", "to": (START + timedelta(hours=49)).isoformat()}, "range_too_long"),
        ({"resolution": "week"}, "invalid"),
        ({"from": "2026-11-11T10:00:00"}, "invalid"),
        ({"metric": None}, "invalid"),
    ],
)
def test_invalid_queries_are_rejected(as_user, overrides, code):
    response = as_user("admin").get(PATH, params=window(**overrides))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_slow_series_query_reports_unavailable(as_user, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from labadda.api import metrics as metrics_api

    def cancelled(db, query):
        raise OperationalError("select", {}, Exception("canceling statement due to statement timeout"))

    monkeypatch.setattr(metrics_api, "_rows", cancelled)
    response = as_user("admin").get(PATH, params=window())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "metrics_unavailable"


SECRETS = (
    "Synthetic metric note title",
    "Synthetic metric post body",
    "Synthetic metric chat text",
    "synthetic-metric-file.pdf",
    "synthetic-metric-search",
)


def seed_content(member, workspace):
    assert member.post("/notes", json={"title": SECRETS[0], "body": SECRETS[0]}).status_code == 201
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": SECRETS[1]}).status_code == 201
    message = {"body": SECRETS[2], "client_id": str(uuid.uuid4())}
    assert member.post(f"/workspaces/{workspace}/chat", json=message).status_code == 201
    upload = member.post(
        "/uploads", files={"file": (SECRETS[3], b"%PDF-1.4\nSynthetic\n%%EOF", "application/pdf")}
    )
    assert upload.status_code == 201
    assert member.get(f"/workspaces/{workspace}/search", params={"q": SECRETS[4]}).status_code == 200


def test_no_content_in_metric_rows_activity_days_or_responses(as_user, ids, db_factory):
    member = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    seed_content(member, workspace)
    with db_factory() as db:
        assert flush(db, now=datetime.now(UTC) + timedelta(minutes=2), registry=REGISTRY) > 0
        stored = [
            (row.metric, row.dimension, row.resolution, str(row.value))
            for row in db.scalars(select(MetricSample))
        ]
        days = [str(row.user_id) for row in db.scalars(select(ActivityDay))]
    assert {"posts.created", "chat.messages", "http.requests"} <= {row[0] for row in stored}
    assert days
    admin = as_user("admin")
    now = datetime.now(UTC)
    bodies = []
    for name, entry in catalog.SERIES.items():
        for dimension in entry.dimensions:
            params = window(
                metric=name,
                dimension=dimension,
                resolution="minute",
                **{
                    "from": (now - timedelta(hours=1)).isoformat(),
                    "to": (now + timedelta(hours=1)).isoformat(),
                },
            )
            response = admin.get(PATH, params=params)
            assert response.status_code == 200, (name, dimension)
            bodies.append(response.text)
    responses = "\n".join(bodies)
    # Unit IDs are permitted in stored dimensions (AD-08) but never served as raw series.
    assert workspace not in responses
    combined = (responses + repr(stored) + repr(days)).lower()
    for secret in SECRETS:
        assert secret.lower() not in combined
