"""T37/T38 personal and hierarchical shared to-do contracts on PostgreSQL."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import text

from labadda.cli import alembic_config
from tests.test_panel import PANEL, pair


def list_body(title="Research plan", workspace_id=None):
    return {"client_id": str(uuid.uuid4()), "title": title, "workspace_id": workspace_id}


def new_list(api, workspace_id=None):
    result = api.post("/todos/lists", json=list_body(workspace_id=workspace_id))
    assert result.status_code == 201, result.text
    return result.json()


def task_body(**kwargs):
    return {
        "client_id": str(uuid.uuid4()),
        "title": "測定 sample α",
        "description": "First run",
        "due_date": "2026-12-01",
        "priority": "high",
        "checklist": [{"title": "Calibrate", "done": False}],
        **kwargs,
    }


def test_personal_lists_and_tasks_are_owner_only(as_user):
    ben = as_user("ben")
    row = new_list(ben)
    path = f"/todos/lists/{row['id']}/tasks"
    task = ben.post(path, json=task_body()).json()
    assert task["title"] == "測定 sample α" and task["due_date"] == "2026-12-01"
    for name in ["admin", "chen", "asha"]:
        api = as_user(name)
        assert api.get("/todos/lists").json()["items"] == []
        assert api.get(path).status_code == 404
        assert api.post(path, json=task_body()).status_code == 404
        assert api.put(f"/todos/lists/{row['id']}", json={"title": "No", "revision": 1}).status_code == 404


def test_workspace_upward_access_and_parent_sibling_admin_denial(as_user, ids):
    ben = as_user("ben")
    section = new_list(ben, ids["workspaces"]["section_a"])
    division = new_list(ben, ids["workspaces"]["division"])
    assert (
        as_user("chen")
        .get("/todos/lists?workspace_id=" + ids["workspaces"]["division"])
        .json()["items"][0]["id"]
        == division["id"]
    )
    for name in ["chen", "dana", "admin"]:
        assert (
            as_user(name).get("/todos/lists?workspace_id=" + ids["workspaces"]["section_a"]).status_code
            == 404
        )
        assert as_user(name).get(f"/todos/lists/{section['id']}/tasks").status_code == 404
    assert as_user("asha").get(f"/todos/lists/{section['id']}/tasks").status_code == 200


def test_group_direct_membership_and_project_access(as_user, ids):
    ben = as_user("ben")
    group = ben.post("/groups", json={"name": "Task group", "member_ids": [ids["users"]["chen"]]}).json()
    row = new_list(ben, group["id"])
    assert as_user("chen").get(f"/todos/lists/{row['id']}/tasks").status_code == 200
    assert as_user("dana").get(f"/todos/lists/{row['id']}/tasks").status_code == 404
    project = new_list(as_user("eli"), ids["workspaces"]["project"])
    assert as_user("dana").get(f"/todos/lists/{project['id']}/tasks").status_code == 200
    assert ben.get(f"/todos/lists/{project['id']}/tasks").status_code == 404


def test_read_only_and_archived_workspace(as_user, ids, db_factory):
    ben = as_user("ben")
    workspace = ids["workspaces"]["section_a"]
    row = new_list(ben, workspace)
    from labadda.models import Workspace

    with db_factory() as db:
        db.get(Workspace, workspace).posting_policy = "read_only"
        db.commit()
    path = f"/todos/lists/{row['id']}/tasks"
    assert ben.get(path).status_code == 200
    assert ben.post(path, json=task_body()).status_code == 403
    assert as_user("asha").post(path, json=task_body()).status_code == 201
    with db_factory() as db:
        db.get(Workspace, workspace).archived = True
        db.commit()
    assert as_user("asha").post(path, json=task_body()).status_code == 403


def test_create_retries_are_bound_to_intent_and_destination(as_user):
    api = as_user("ben")
    body = list_body()
    first = api.post("/todos/lists", json=body).json()
    assert api.post("/todos/lists", json=body).json()["id"] == first["id"]
    assert api.post("/todos/lists", json={**body, "title": "different"}).status_code == 409
    path = f"/todos/lists/{first['id']}/tasks"
    body = task_body()
    first_task = api.post(path, json=body).json()
    assert api.post(path, json=body).json()["id"] == first_task["id"]
    assert api.post(path, json={**body, "done": True}).status_code == 409
    another = new_list(api)
    assert api.post(f"/todos/lists/{another['id']}/tasks", json=body).status_code == 409


def test_revisions_checklist_completion_and_reopening(as_user):
    api = as_user("ben")
    row = new_list(api)
    path = f"/todos/lists/{row['id']}/tasks"
    task = api.post(path, json=task_body()).json()
    edit = {
        k: task[k] for k in ["title", "description", "due_date", "priority", "checklist", "done", "revision"]
    }
    edit["done"] = True
    edit["checklist"][0]["done"] = True
    assert api.put(path + "/" + task["id"], json=edit).json()["revision"] == 2
    assert api.put(path + "/" + task["id"], json=edit).status_code == 409
    edit.update(revision=2, done=False)
    assert api.put(path + "/" + task["id"], json=edit).json()["done"] is False
    assert (
        api.put(f"/todos/lists/{row['id']}", json={"title": "New title", "revision": 1}).json()["revision"]
        == 2
    )
    assert (
        api.put(f"/todos/lists/{row['id']}", json={"title": "Stale title", "revision": 1}).status_code == 409
    )


@pytest.mark.parametrize(
    "change",
    [
        {"title": " "},
        {"priority": "urgent"},
        {"due_date": "bad-date"},
        {"done": 1},
        {"checklist": [{"title": "x"}] * 51},
        {"description": "x" * 10001},
        {"workspace_id": str(uuid.uuid4())},
    ],
)
def test_invalid_task_payloads(as_user, change):
    api = as_user("ben")
    row = new_list(api)
    assert api.post(f"/todos/lists/{row['id']}/tasks", json=task_body(**change)).status_code == 422


def test_cursor_pages_are_scoped_and_bounded(as_user):
    api = as_user("ben")
    row = new_list(api)
    path = f"/todos/lists/{row['id']}/tasks"
    for i in range(3):
        assert api.post(path, json=task_body(title=str(i))).status_code == 201
    first = api.get(path + "?limit=2").json()
    second = api.get(path + "?limit=2&after=" + first["next_cursor"]).json()
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    assert len({t["id"] for t in first["items"] + second["items"]}) == 3
    assert api.get(path + "?limit=51").status_code == 422


def test_panel_markers_and_csrf_refused(as_user, make_client, ids):
    api = as_user("ben")
    new_list(api)
    panel = pair(as_user, make_client, ids)
    assert panel.api.get("/todos/lists", headers=PANEL).status_code == 401
    assert api.get("/todos/lists", headers=PANEL).status_code == 401
    assert api.get("/todos/lists?panel=1").status_code == 401
    assert api.client.post(api.url("/todos/lists"), json=list_body()).status_code == 403


def test_revoked_grant_no_longer_reads_or_writes(as_user, ids):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    row = new_list(api, ws)
    assert (
        as_user("admin").delete(f"/admin/workspaces/{ws}/memberships/{ids['users']['ben']}").status_code
        == 200
    )
    assert api.get(f"/todos/lists/{row['id']}/tasks").status_code == 404
    assert api.post(f"/todos/lists/{row['id']}/tasks", json=task_body()).status_code == 404


def test_two_writers_cannot_overwrite_same_revision(as_user, ids):
    ben, asha = as_user("ben"), as_user("asha")
    row = new_list(ben, ids["workspaces"]["section_a"])
    path = f"/todos/lists/{row['id']}/tasks"
    task = ben.post(path, json=task_body()).json()
    body = {
        k: task[k] for k in ["title", "description", "due_date", "priority", "checklist", "done", "revision"]
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(api.put, path + "/" + task["id"], json={**body, "title": title})
            for api, title in [(ben, "one"), (asha, "two")]
        ]
        assert sorted(f.result().status_code for f in futures) == [200, 409]


def test_downgrade_protects_user_content(as_user, settings, db_factory):
    new_list(as_user("ben"))
    with pytest.raises(RuntimeError, match="To-do lists exist"):
        command.downgrade(alembic_config(settings.database_url), "0016")
    with db_factory() as db:
        assert db.scalar(text("select count(*) from todo_lists")) == 1


def test_session_expiry_while_waiting_for_scope_lock_rolls_back(as_user, ids, monkeypatch):

    from labadda import identity_locks
    from labadda.api import todos

    original = todos._scope

    def expire_after_scope(db, user, workspace_id, write=False):
        result = original(db, user, workspace_id, write)
        if write:
            # Advance only the validation clock, representing elapsed lock wait.
            monkeypatch.setattr(identity_locks, "session_valid", lambda *_: False)
        return result

    api = as_user("ben")
    monkeypatch.setattr(todos, "_scope", expire_after_scope)
    assert (
        api.post("/todos/lists", json=list_body(workspace_id=ids["workspaces"]["section_a"])).status_code
        == 401
    )


def test_workspace_row_writer_and_list_creation_do_not_deadlock(as_user, ids, db_factory):
    import time

    from sqlalchemy import select

    from labadda.models import Workspace

    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    with db_factory() as writer, ThreadPoolExecutor(max_workers=1) as pool:
        row = writer.scalar(select(Workspace).where(Workspace.id == ws).with_for_update())
        future = pool.submit(api.post, "/todos/lists", json=list_body(workspace_id=ws))
        deadline = time.monotonic() + 1.5
        blocked = False
        while time.monotonic() < deadline:
            blocked = writer.scalar(
                text(
                    "select exists(select 1 from pg_stat_activity where datname=current_database() and "
                    "wait_event_type='Lock' and query like '%FOR KEY SHARE%')"
                )
            )
            if blocked:
                break
            time.sleep(0.01)
            writer.execute(text("select pg_stat_clear_snapshot()"))
        try:
            assert blocked, "Task writer must wait on the workspace row before taking table SHARE"
            row.name = "Renamed during task creation"
            writer.commit()
        except BaseException:
            writer.rollback()
            raise
        assert future.result(timeout=5).status_code == 201


def test_list_detail_refresh_keeps_scope_private(as_user, ids):
    api = as_user("ben")
    personal = new_list(api)
    assert api.get("/todos/lists/" + personal["id"]).json()["revision"] == 1
    for name in ["asha", "chen", "dana", "admin"]:
        assert as_user(name).get("/todos/lists/" + personal["id"]).status_code == 404
    shared = new_list(api, ids["workspaces"]["section_a"])
    assert as_user("asha").get("/todos/lists/" + shared["id"]).status_code == 200
    assert as_user("dana").get("/todos/lists/" + shared["id"]).status_code == 404
