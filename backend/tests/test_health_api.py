"""T61, T63: health and events endpoints; access, acknowledgement, recovery, no content."""

import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select

from labadda.models import AuditEvent, OpsEvent
from labadda.security import utcnow
from tests.test_capabilities import grant
from tests.test_panel import pair

HEALTH = "/admin/health"
EVENTS = "/admin/events"


@pytest.fixture
def settings(settings):
    return replace(settings, test_health_force="database=unavailable")


def sample(app):
    assert app.state.health.run_once()


def by_key(response):
    return {item["key"]: item for item in response.json()["items"]}


def test_health_reports_every_item_with_the_common_shape(as_user, app):
    body = as_user("admin").get(HEALTH).json()
    assert [item["key"] for item in body["items"]] == [
        "application",
        "database",
        "file_storage",
        "connections",
        "jobs",
        "response_time",
        "sign_in",
        "backups",
        "server",
        "certificate",
    ]
    for item in body["items"]:
        assert {"status", "value", "unit", "detail", "checked_at", "age_seconds", "help", "chart"} <= set(
            item
        )
        assert item["help"].startswith("troubleshooting/health-")
    assert body["interval_seconds"] == 15
    assert body["overall"] == "unavailable"  # the forced database item
    items = {item["key"]: item for item in body["items"]}
    assert items["backups"]["status"] == "unknown"
    assert items["database"]["chart"] == {"metric": "db.size_bytes", "dimension": "", "unit": "bytes"}


def test_health_access_follows_the_console_rules(as_user, make_client, ids, app):
    assert as_user("admin").get(HEALTH).status_code == 200
    for username in ("asha", "chen", "ben"):
        assert as_user(username).get(HEALTH).status_code == 403
    assert grant(as_user("admin"), ids["users"]["ben"]).status_code == 201
    assert as_user("ben").get(HEALTH).status_code == 200
    assert make_client().get(HEALTH).status_code == 401
    assert pair(as_user, make_client, ids).get(HEALTH).status_code == 401


def test_forced_state_raises_one_event_with_guidance(as_user, app):
    sample(app)
    sample(app)
    events = as_user("admin").get(EVENTS).json()["events"]
    assert [(e["code"], e["state"], e["severity"], e["count"]) for e in events] == [
        ("database.unavailable", "open", "error", 1)
    ]
    assert events[0]["help"] == "troubleshooting/health-database"
    assert events[0]["component_label"] == "Database"


def test_acknowledging_records_who_and_why_but_the_item_stays_failing(as_user, app, db_factory):
    sample(app)
    admin = as_user("admin")
    event_id = admin.get(EVENTS).json()["events"][0]["id"]
    response = admin.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "Operator has been called."})
    assert response.status_code == 200
    body = response.json()
    assert (body["state"], body["note"], body["acknowledged_by"]["username"]) == (
        "acknowledged",
        "Operator has been called.",
        "admin",
    )
    sample(app)
    assert by_key(admin.get(HEALTH))["database"]["status"] == "unavailable"
    assert admin.get(EVENTS, params={"state": "open"}).json()["events"] == []
    assert len(admin.get(EVENTS, params={"state": "acknowledged"}).json()["events"]) == 1
    with db_factory() as db:
        row = db.scalars(select(AuditEvent).where(AuditEvent.action == "ops_event.acknowledge")).one()
        assert (row.reason, row.detail["before"], row.detail["after"]) == (
            "Operator has been called.",
            "open",
            "acknowledged",
        )


def test_acknowledging_twice_blank_note_and_unknown_event(as_user, app):
    sample(app)
    admin = as_user("admin")
    event_id = admin.get(EVENTS).json()["events"][0]["id"]
    assert admin.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "   "}).status_code == 422
    assert admin.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "Seen."}).status_code == 200
    again = admin.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "Seen."})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "event_acknowledged")
    assert admin.post(f"{EVENTS}/999999/acknowledge", json={"note": "Seen."}).status_code == 404


def test_a_failing_item_cannot_be_resolved_by_hand_but_recovery_resolves_it(as_user, app):
    sample(app)
    admin = as_user("admin")
    event_id = admin.get(EVENTS).json()["events"][0]["id"]
    refused = admin.post(f"{EVENTS}/{event_id}/resolve", json={"note": "Fixed."})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "still_failing")
    app.state.health.forced = {}
    sample(app)
    resolved = admin.get(EVENTS, params={"state": "resolved"}).json()["events"]
    assert [(e["id"], e["state"]) for e in resolved] == [(event_id, "resolved")]
    assert resolved[0]["resolved_at"]
    again = admin.post(f"{EVENTS}/{event_id}/resolve", json={})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "event_resolved")


def test_an_event_whose_item_no_longer_fails_can_be_resolved_and_is_audited(as_user, app, db_factory):
    sample(app)  # the certificate item is unsupported here, so it is not failing
    seed_events(db_factory, 1, "x")
    with db_factory() as db:
        event = db.scalars(select(OpsEvent).where(OpsEvent.code == "jobs.degradedx0")).one()
        event.component = "certificate"
        event.state = "open"
        db.commit()
        event_id = event.id
    response = as_user("admin").post(f"{EVENTS}/{event_id}/resolve", json={"note": "Checked by hand."})
    assert response.status_code == 200
    assert response.json()["state"] == "resolved"
    with db_factory() as db:
        row = db.scalars(select(AuditEvent).where(AuditEvent.action == "ops_event.resolve")).one()
        assert (row.reason, row.detail["before"], row.detail["after"]) == (
            "Checked by hand.",
            "open",
            "resolved",
        )


def test_usage_readers_read_events_but_cannot_acknowledge_or_resolve(as_user, ids, app):
    sample(app)
    admin = as_user("admin")
    event_id = admin.get(EVENTS).json()["events"][0]["id"]
    assert grant(admin, ids["users"]["ben"]).status_code == 201
    reader = as_user("ben")
    assert len(reader.get(EVENTS).json()["events"]) == 1
    ack = reader.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "Looking."})
    assert (ack.status_code, ack.json()["error"]["code"]) == (403, "admin_required")
    assert reader.post(f"{EVENTS}/{event_id}/resolve", json={}).status_code == 403
    assert admin.get(EVENTS).json()["events"][0]["state"] == "open"


def test_events_access_for_members_signed_out_and_panel(as_user, make_client, ids, app):
    sample(app)
    event_id = as_user("admin").get(EVENTS).json()["events"][0]["id"]
    assert as_user("asha").get(EVENTS).status_code == 403
    assert as_user("asha").post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "x"}).status_code == 403
    anonymous = make_client()
    assert anonymous.get(EVENTS).status_code == 401
    assert anonymous.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "x"}).status_code == 401
    kiosk = pair(as_user, make_client, ids)
    assert kiosk.get(EVENTS).status_code == 401
    assert kiosk.post(f"{EVENTS}/{event_id}/resolve", json={}).status_code == 401


def test_deactivated_administrator_is_refused(as_user, make_client):
    client = make_client()
    assert client.login("fay").status_code == 401
    assert client.get(EVENTS).status_code == 401


def seed_events(db_factory, total, batch="a"):
    base = utcnow()
    with db_factory() as db:
        for index in range(total):
            db.add(
                OpsEvent(
                    code=f"jobs.degraded{batch}{index}",
                    component="jobs" if index % 2 else "server",
                    severity="warning" if index % 3 else "error",
                    summary="Seeded.",
                    detail={},
                    first_at=base - timedelta(minutes=index),
                    last_at=base - timedelta(minutes=index // 2),
                    count=1,
                    state="open" if index % 4 else "resolved",
                )
            )
        db.commit()


def test_events_filter_and_page_with_a_stable_cursor(as_user, db_factory, ids):
    seed_events(db_factory, 12)
    admin = as_user("admin")
    first = admin.get(EVENTS, params={"limit": 5}).json()
    assert len(first["events"]) == 5 and first["next_cursor"]
    seen = [event["id"] for event in first["events"]]
    seed_events(db_factory, 3, "b")  # newer events arriving between pages must not shift the next page
    second = admin.get(EVENTS, params={"limit": 5, "cursor": first["next_cursor"]}).json()
    seen += [event["id"] for event in second["events"]]
    assert len(set(seen)) == 10
    rest = admin.get(EVENTS, params={"limit": 100, "cursor": second["next_cursor"]}).json()
    assert rest["next_cursor"] is None
    assert len(rest["events"]) == 2
    only = admin.get(EVENTS, params={"state": "resolved", "component": "server", "limit": 100}).json()
    assert only["events"]
    assert {(e["state"], e["component"]) for e in only["events"]} == {("resolved", "server")}
    assert {
        e["severity"] for e in admin.get(EVENTS, params={"severity": "error", "limit": 100}).json()["events"]
    } == {"error"}


def test_invalid_filters_and_cursors_are_refused(as_user):
    admin = as_user("admin")
    assert admin.get(EVENTS, params={"state": "gone"}).status_code == 422
    assert admin.get(EVENTS, params={"limit": 0}).status_code == 422
    bad = admin.get(EVENTS, params={"cursor": "not-a-cursor"})
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "invalid_cursor")


def test_console_responses_contain_no_user_content(as_user, ids, app):
    member = as_user("ben")
    secrets = (
        "Synthetic health post body",
        "Synthetic health chat text",
        "synthetic-health-note",
        "health-file.pdf",
    )
    workspace = ids["workspaces"]["section_a"]
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": secrets[0]}).status_code == 201
    assert (
        member.post(
            f"/workspaces/{workspace}/chat", json={"body": secrets[1], "client_id": str(uuid.uuid4())}
        ).status_code
        == 201
    )
    assert member.post("/notes", json={"title": secrets[2], "body": secrets[2]}).status_code == 201
    assert (
        member.post(
            "/uploads", files={"file": (secrets[3], b"%PDF-1.4\nS\n%%EOF", "application/pdf")}
        ).status_code
        == 201
    )
    sample(app)
    admin = as_user("admin")
    event_id = admin.get(EVENTS).json()["events"][0]["id"]
    admin.post(f"{EVENTS}/{event_id}/acknowledge", json={"note": "Checked."})
    window = {"metric": "sockets.connected", "resolution": "minute", "dimension": ""}
    start = (utcnow() - timedelta(hours=24)).isoformat()
    window.update({"from": start, "to": utcnow().isoformat()})
    bodies = [
        admin.get(path, params=params).text
        for path, params in ((HEALTH, None), (EVENTS, None), ("/admin/metrics/series", window))
    ]
    for secret in secrets:
        assert not any(secret in body for body in bodies)
