"""Pilot regressions: conflicts, retained cancellation, bounded input and current scope."""

import uuid

from sqlalchemy import select

from labadda.models import CalendarEvent, Workspace


def event(client, **values):
    response = client.post(
        "/calendar/events",
        json={
            "scope_kind": "personal",
            "title": "Tensile review — Asha",
            "starts_at": "2026-11-16T09:00:00+05:30",
            "ends_at": "2026-11-16T10:00:00+05:30",
            **values,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_stale_edits_and_cancellation_retain_content(as_user, db_factory):
    client = as_user("asha")
    original = event(client)
    path = f"/calendar/events/{original['id']}"
    changed = client.patch(path, json={"revision": 1, "title": "Revised tensile review"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["revision"] == 2
    assert client.patch(path, json={"revision": 1, "title": "Stale overwrite"}).status_code == 409
    assert client.delete(path + "?revision=1").status_code == 409
    assert client.get(path).json()["title"] == "Revised tensile review"
    assert client.delete(path + "?revision=2").status_code == 200
    assert client.get(path).status_code == 404
    assert client.get("/calendar/events?start=2026-11-16T00:00:00Z&end=2026-11-17T00:00:00Z").json() == []
    with db_factory() as db:
        retained = db.get(CalendarEvent, uuid.UUID(original["id"]))
        assert retained.title == "Revised tensile review"
        assert retained.cancelled_at is not None
        assert retained.revision == 3


def test_archived_workspace_cannot_be_edited_by_its_steward(as_user, ids, db_factory):
    client = as_user("asha")
    workspace = ids["workspaces"]["section_a"]
    original = event(client, scope_kind="workspace", workspace_id=workspace)
    with db_factory() as db:
        db.get(Workspace, uuid.UUID(workspace)).archived = True
        db.commit()
    path = f"/calendar/events/{original['id']}"
    assert client.get(path).json()["can_edit"] is False
    assert client.patch(path, json={"revision": 1, "title": "Blocked edit"}).status_code == 403
    assert client.delete(path + "?revision=1").status_code == 403
    with db_factory() as db:
        assert db.scalar(select(CalendarEvent.title)) == original["title"]


def test_calendar_requires_bounded_zoned_input_and_revision(as_user):
    client = as_user("asha")
    original = event(client)
    path = f"/calendar/events/{original['id']}"
    assert client.patch(path, json={"title": "Missing revision"}).status_code == 422
    assert client.delete(path).status_code == 422
    assert client.patch(path, json={"revision": 1, "title": "   "}).status_code == 422
    assert client.patch(path, json={"revision": 1, "starts_at": "2026-11-16T09:00:00"}).status_code == 422
    assert (
        client.get("/calendar/events?start=2020-01-01T00:00:00Z&end=2030-01-01T00:00:00Z").status_code == 422
    )
    assert client.get(path + "?panel=1").status_code == 401
    assert client.get("/calendar/sources?panel=1").status_code == 401
