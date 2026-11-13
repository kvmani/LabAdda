"""A6: GET /admin/overview. Attention order, tiles, small-group floor, unknown states, no content."""

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select

from labadda import backup_status as bs
from labadda.health import ITEMS
from labadda.models import Membership, OpsEvent, User, Workspace
from labadda.security import utcnow
from tests.analytics_support import add_people, fresh_cache, mark_active, store  # noqa: F401
from tests.test_admin_site import receipt
from tests.test_capabilities import grant
from tests.test_panel import pair

OVERVIEW = "/admin/overview"


@pytest.fixture
def status_dir(app, tmp_path):
    folder = tmp_path / "status-secret-folder"
    folder.mkdir()
    app.state.settings = replace(app.state.settings, status_dir=folder)
    app.state.health.context.settings = app.state.settings
    return folder


def force(app, **words):
    """Every health item healthy, except the ones named."""
    app.state.health.forced = {item.key: words.get(item.key, "healthy") for item in ITEMS}


def staff_every_unit(db_factory):
    """Give each organisation unit without a steward one, so the fixture has nothing to report."""
    with db_factory() as db:
        asha = db.scalar(select(User).where(User.username == "asha"))
        for unit in db.scalars(select(Workspace).where(Workspace.kind == "org")):
            if db.scalar(
                select(Membership).where(Membership.workspace_id == unit.id, Membership.user_id == asha.id)
            ):
                continue
            db.add(Membership(user_id=asha.id, workspace_id=unit.id, role="steward"))
        db.commit()


def seed_gauges(db_factory, *, sessions=6, sockets=3):
    now = utcnow().replace(second=0, microsecond=0)
    store(
        db_factory,
        "minute",
        (now, "sessions.active", "", sessions),
        (now, "sockets.connected", "", sockets),
        (now, "assets.bytes", "", 2048),
        (now, "db.size_bytes", "", 8192),
        (now, "http.latency_p95", "all", 120),
    )


def tiles(body):
    return {tile["key"]: tile for tile in body["tiles"]}


def test_clean_installation_needs_nothing(as_user, app, db_factory, status_dir):
    staff_every_unit(db_factory)
    force(app)
    bs.write_status(status_dir, receipt(2))
    seed_gauges(db_factory)
    body = as_user("admin").get(OVERVIEW).json()
    assert body["overall"] == "healthy"
    assert body["attention"] == []
    assert [tile["key"] for tile in body["tiles"]] == [
        "active_today",
        "signed_in_now",
        "connected_now",
        "storage_used",
        "last_backup",
        "open_events",
    ]
    found = tiles(body)
    assert (found["signed_in_now"]["state"], found["signed_in_now"]["value"]) == ("measured", 6)
    assert found["connected_now"]["value"] == 3
    assert (found["storage_used"]["state"], found["storage_used"]["value"]) == ("measured", 10240)
    assert found["last_backup"]["state"] == "healthy"
    assert found["open_events"]["value"] == 0
    assert all(len(tile["trend"]) == 7 for tile in body["tiles"] if tile["trend"] is not None)
    assert body["charts"]["response_time"]["points"][-1]["value"] == 120


def test_stale_backup_unit_without_steward_and_open_event_in_severity_order(
    as_user, app, db_factory, status_dir
):
    staff_every_unit(db_factory)
    app.state.health.forced = {item.key: "healthy" for item in ITEMS if item.key != "backups"}
    bs.write_status(status_dir, receipt(60))
    with db_factory() as db:
        steward = db.scalar(
            select(Membership).where(
                Membership.workspace_id
                == db.scalar(select(Workspace.id).where(Workspace.name == "Corrosion Section")),
                Membership.role == "steward",
            )
        )
        db.delete(steward)
        now = utcnow()
        db.add(
            OpsEvent(
                code="jobs.late",
                component="scheduler",
                severity="critical",
                summary="A background job has not run.",
                detail={},
                first_at=now,
                last_at=now,
            )
        )
        db.commit()
    body = as_user("admin").get(OVERVIEW).json()
    assert [(e["kind"], e["severity"]) for e in body["attention"]] == [
        ("event", "critical"),
        ("health", "error"),
        ("people", "warning"),
    ]
    routes = [e["route"] for e in body["attention"]]
    assert routes[1:] == ["/admin/backups", "/admin/org"]
    assert routes[0].startswith("/admin/events?state=open&event=")
    assert "Corrosion Section" in body["attention"][2]["detail"]
    assert body["overall"] == "unavailable"
    assert tiles(body)["open_events"]["by_severity"]["critical"] == 1


def test_an_event_for_a_listed_item_is_not_listed_twice(as_user, app, db_factory, status_dir):
    staff_every_unit(db_factory)
    app.state.health.forced = {item.key: "healthy" for item in ITEMS if item.key != "backups"}
    bs.write_status(status_dir, receipt(60))
    body = as_user("admin").get(OVERVIEW).json()
    assert [e["id"] for e in body["attention"]] == ["health:backups"]
    assert tiles(body)["open_events"]["value"] == 1


def test_unknown_is_never_zero_or_healthy(as_user, app, db_factory, status_dir):
    staff_every_unit(db_factory)
    body = as_user("admin").get(OVERVIEW).json()
    found = tiles(body)
    # The administrator's own request makes one person active, which is below the floor.
    assert (found["active_today"]["state"], found["active_today"]["value"]) == ("suppressed", None)
    for key in ("signed_in_now", "connected_now", "storage_used"):
        assert (found[key]["state"], found[key]["value"]) == ("unknown", None), key
    assert (found["last_backup"]["state"], found["last_backup"]["value"]) == ("unknown", None)
    assert body["charts"]["response_time"]["state"] == "unknown"
    assert body["charts"]["activity"]["state"] == "suppressed"
    assert body["overall"] != "healthy"
    assert {"health:backups", "health:response_time"} <= {e["id"] for e in body["attention"]}


def test_old_gauges_are_stale(as_user, app, db_factory):
    old = (utcnow() - timedelta(minutes=30)).replace(second=0, microsecond=0)
    store(db_factory, "minute", (old, "sockets.connected", "", 4))
    tile = tiles(as_user("admin").get(OVERVIEW).json())["connected_now"]
    assert tile["state"] == "stale"


def test_small_groups_are_never_sent(as_user, app, db_factory):
    seed_gauges(db_factory, sessions=3, sockets=3)
    people = add_people(db_factory, None, 3, "few")
    mark_active(db_factory, people, utcnow().date())
    body = as_user("admin").get(OVERVIEW).json()
    found = tiles(body)
    assert (found["signed_in_now"]["state"], found["signed_in_now"]["value"]) == ("suppressed", None)
    assert found["signed_in_now"]["trend"] == [None] * 7
    assert (found["active_today"]["state"], found["active_today"]["value"]) == ("suppressed", None)
    assert all(point["value"] is None for point in body["charts"]["activity"]["points"])
    assert "suppressed" in {point["state"] for point in body["charts"]["activity"]["points"]}


def test_enough_people_are_sent_like_the_activity_page(as_user, app, db_factory):
    people = add_people(db_factory, None, 6, "many")
    today = utcnow().date()
    mark_active(db_factory, people, today)
    admin = as_user("admin")
    summary = admin.get("/admin/analytics/summary", params={"period": "7d"}).json()
    activity = next(t for t in summary["tiles"] if t["key"] == "active_day")
    shown = tiles(admin.get(OVERVIEW).json())["active_today"]
    assert (shown["state"], shown["value"]) == (activity["state"], activity["value"])


def test_access_follows_the_console_rules(as_user, make_client, ids):
    assert as_user("admin").get(OVERVIEW).status_code == 200
    for username in ("asha", "chitra", "bharat"):
        assert as_user(username).get(OVERVIEW).status_code == 403
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    assert as_user("bharat").get(OVERVIEW).status_code == 200
    assert make_client().get(OVERVIEW).status_code == 401
    assert pair(as_user, make_client, ids).get(OVERVIEW).status_code == 401


def test_overview_contains_no_user_content(as_user, ids, app, db_factory, status_dir):
    member = as_user("bharat")
    secrets = (
        "Synthetic overview post body",
        "Synthetic overview chat text",
        "synthetic-overview-note",
        "overview-file.pdf",
    )
    workspace = ids["workspaces"]["section_a"]
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": secrets[0]}).status_code == 201
    chat = {"body": secrets[1], "client_id": str(uuid.uuid4())}
    assert member.post(f"/workspaces/{workspace}/chat", json=chat).status_code == 201
    assert member.post("/notes", json={"title": secrets[2], "body": secrets[2]}).status_code == 201
    upload = {"file": (secrets[3], b"%PDF-1.4\nS\n%%EOF", "application/pdf")}
    assert member.post("/uploads", files=upload).status_code == 201
    bs.write_status(status_dir, receipt(60))
    seed_gauges(db_factory)
    admin = as_user("admin")
    assert grant(admin, ids["users"]["chitra"]).status_code == 201
    bodies = [admin.get(OVERVIEW).text, as_user("chitra").get(OVERVIEW).text]
    for secret in secrets:
        assert not any(secret in body for body in bodies)
    assert not any(str(status_dir) in body for body in bodies)
