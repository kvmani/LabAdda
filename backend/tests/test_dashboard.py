"""C5 owner overview: source grants, bounded priorities and final visibility."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from labadda.models import Membership
from tests.test_todos import new_list


def create(api, workspace, title, due=None, done=False):
    listing = new_list(api, workspace)
    result = api.post(
        f"/todos/lists/{listing['id']}/tasks",
        json={"client_id": str(uuid.uuid4()), "title": title, "due_date": due, "done": done},
    ).json()
    return listing, result


def test_dashboard_personal_assigned_deadlines_and_unread(as_user, ids):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    create(api, None, "Personal control", "2026-11-12")
    create(api, None, "Already complete", "2026-11-01", True)
    listing, task = create(as_user("asha"), ws, "Assigned witness", "2026-11-11")
    assert (
        as_user("asha")
        .put(
            f"/todos/lists/{listing['id']}/tasks/{task['id']}/assignee",
            json={"revision": 1, "user_id": ids["users"]["ben"]},
        )
        .status_code
        == 200
    )
    create(as_user("asha"), ws, "Unassigned hidden")
    as_user("asha").post(
        f"/workspaces/{ws}/chat", json={"body": "@ben review the blank", "client_id": str(uuid.uuid4())}
    )
    result = api.get("/dashboard").json()
    assert [row["title"] for row in result["tasks"]] == ["Assigned witness", "Personal control"]
    assert result["chats"][0]["unread"] == 1 and result["updates"][0]["kind"] == "mention"
    assert as_user("chen").get("/dashboard").json()["tasks"] == []
    assert as_user("admin").get("/dashboard").json()["tasks"] == []
    assert api.get("/dashboard", headers={"X-LabAdda-Panel": "1"}).status_code == 401


def test_dashboard_final_grant_loss_drops_task_chat_and_update(as_user, ids, db_factory, monkeypatch):
    from labadda.api import dashboard

    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    listing, task = create(api, ws, "Protected assigned")
    api.put(
        f"/todos/lists/{listing['id']}/tasks/{task['id']}/assignee",
        json={"revision": 1, "user_id": ids["users"]["ben"]},
    )
    original = dashboard._task_json

    def revoke(row):
        result = original(row)
        with db_factory() as db:
            db.execute(
                delete(Membership).where(
                    Membership.user_id == ids["users"]["ben"], Membership.workspace_id == ws
                )
            )
            db.commit()
        return result

    monkeypatch.setattr(dashboard, "_task_json", revoke)
    result = api.get("/dashboard").json()
    assert result["tasks"] == [] and result["chats"] == [] and result["updates"] == []
    assert result["restart_required"] and not result["tasks_more"]


def test_dashboard_calendar_uses_configured_timezone(as_user, monkeypatch, app, settings):
    from dataclasses import replace

    monkeypatch.setattr(app.state, "settings", replace(settings, timezone="Asia/Kolkata"))
    from labadda.api import dashboard

    monkeypatch.setattr(dashboard, "utcnow", lambda: datetime(2026, 11, 10, 23, 30, tzinfo=UTC))
    result = as_user("ben").get("/dashboard").json()
    assert result["timezone"] == "Asia/Kolkata" and result["today"] == "2026-11-11"


def test_dashboard_private_notes_are_owner_only(as_user):
    as_user("ben").post(
        "/notes",
        json={
            "title": "Private daily reminder",
            "body": "Keep uncertainty private",
            "due_at": "2026-11-12T09:00:00+05:30",
        },
    )
    assert as_user("ben").get("/dashboard").json()["notes"][0]["title"] == "Private daily reminder"
    for name in ["asha", "chen", "admin"]:
        assert as_user(name).get("/dashboard").json()["notes"] == []


def test_invalid_dashboard_timezone_is_rejected_at_configuration_load(monkeypatch):
    from labadda.config import load_settings

    monkeypatch.setenv("LABADDA_TIMEZONE", "Not/A_Timezone")
    with pytest.raises(ValueError, match="installed IANA timezone"):
        load_settings()


def test_dashboard_windows_apply_after_active_filter(as_user):
    api = as_user("ben")
    listing = new_list(api)
    for index in range(28):
        assert (
            api.post(
                f"/todos/lists/{listing['id']}/tasks",
                json={
                    "client_id": str(uuid.uuid4()),
                    "title": "Active " + str(index),
                    "due_date": "2026-11-12",
                },
            ).status_code
            == 201
        )
    assert (
        api.post(
            f"/todos/lists/{listing['id']}/tasks",
            json={
                "client_id": str(uuid.uuid4()),
                "title": "Completed earlier",
                "due_date": "2026-11-01",
                "done": True,
            },
        ).status_code
        == 201
    )
    result = api.get("/dashboard").json()
    assert (
        len(result["tasks"]) == 25
        and result["tasks_more"]
        and all(not row["done"] for row in result["tasks"])
    )
