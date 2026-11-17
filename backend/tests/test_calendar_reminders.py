"""Calendar reminder deduplication, preferences and current-access delivery."""

from datetime import timedelta

from labadda.scheduler import process_due_reminders
from labadda.security import utcnow


def test_personal_reminder_dedupes_and_acknowledges(as_user, db_factory):
    client = as_user("bharat")
    now = utcnow()
    event = client.post(
        "/calendar/events",
        json={
            "scope_kind": "personal",
            "title": "Project Tejas review",
            "starts_at": (now + timedelta(minutes=10)).isoformat(),
            "ends_at": (now + timedelta(minutes=40)).isoformat(),
            "all_day": False,
        },
    )
    assert event.status_code == 200, event.text
    with db_factory() as db:
        assert process_due_reminders(db, now=now) == 1
        assert process_due_reminders(db, now=now) == 0
    alerts = client.get("/notifications").json()
    item = next(n for n in alerts["items"] if n["link"]["view"] == "calendar")
    assert item["title"] == "Project Tejas review"
    for name in ("asha", "chitra", "admin", "deepa", "esha"):
        other = as_user(name)
        assert "Project Tejas review" not in other.get("/notifications").text
        assert other.post(f"/notifications/{item['id']}/open").status_code == 404
    assert client.post(f"/notifications/{item['id']}/open").status_code == 200
    assert client.get("/notifications").json()["unread"] == 0
    changed = client.patch(
        f"/calendar/events/{event.json()['id']}",
        json={
            "revision": 1,
            "starts_at": (now + timedelta(minutes=12)).isoformat(),
        },
    )
    assert changed.status_code == 200, changed.text
    assert item["id"] not in client.get("/notifications").text
    with db_factory() as db:
        assert process_due_reminders(db, now=now) == 1
    # Cancellation suppresses existing reminders, even after delivery.
    assert client.delete(f"/calendar/events/{event.json()['id']}?revision=2").status_code == 200
    assert item["id"] not in client.get("/notifications").text


def test_calendar_reminder_preferences_and_future_window(as_user, db_factory):
    client = as_user("bharat")
    now = utcnow()
    prefs = client.get("/notification-preferences").json()
    assert client.put("/notification-preferences", json={**prefs, "reminders": False}).status_code == 200
    for minutes, all_day in [(10, False), (30, False), (10, True)]:
        result = client.post(
            "/calendar/events",
            json={
                "scope_kind": "personal",
                "title": "Thin Films review",
                "starts_at": (now + timedelta(minutes=minutes)).isoformat(),
                "ends_at": (now + timedelta(minutes=minutes + 30)).isoformat(),
                "all_day": all_day,
            },
        )
        assert result.status_code == 200, result.text
    with db_factory() as db:
        assert process_due_reminders(db, now=now) == 0
    assert client.get("/notifications").json()["unread"] == 0
    prefs = client.get("/notification-preferences").json()
    assert client.put("/notification-preferences", json={**prefs, "reminders": True}).status_code == 200
    with db_factory() as db:
        assert process_due_reminders(db, now=now) == 0


def test_workspace_reminder_respects_current_grants(as_user, ids, db_factory):
    now = utcnow()
    workspace = ids["workspaces"]["section_a"]
    result = as_user("asha").post(
        "/calendar/events",
        json={
            "scope_kind": "workspace",
            "workspace_id": str(workspace),
            "title": "Thin Films meeting",
            "starts_at": (now + timedelta(minutes=10)).isoformat(),
            "ends_at": (now + timedelta(minutes=40)).isoformat(),
            "all_day": False,
        },
    )
    assert result.status_code == 200, result.text
    with db_factory() as db:
        assert process_due_reminders(db, now=now) == 2
    bharat = as_user("bharat")
    item = next(n for n in bharat.get("/notifications").json()["items"] if n["link"]["view"] == "calendar")
    for name in ("chitra", "deepa", "admin", "esha"):
        assert "Thin Films meeting" not in as_user(name).get("/notifications").text
    assert (
        as_user("admin")
        .delete(f"/admin/workspaces/{workspace}/memberships/{ids['users']['bharat']}")
        .status_code
        == 200
    )
    assert item["id"] not in bharat.get("/notifications").text
    assert bharat.post(f"/notifications/{item['id']}/open").status_code == 404


def test_calendar_reminder_downgrade_preserves_delivery_history(as_user, db_factory, migrated):
    import pytest
    from alembic import command

    from labadda.cli import alembic_config

    now = utcnow()
    result = as_user("asha").post(
        "/calendar/events",
        json={
            "scope_kind": "personal",
            "title": "Thin Films discussion",
            "starts_at": (now + timedelta(minutes=10)).isoformat(),
            "ends_at": (now + timedelta(minutes=40)).isoformat(),
            "all_day": False,
        },
    )
    assert result.status_code == 200
    with db_factory() as db:
        process_due_reminders(db, now=now)
    with pytest.raises(RuntimeError, match="Cannot discard processed"):
        command.downgrade(alembic_config(migrated), "0048")
