"""T48: reviewed board context, independent source grants and durable retry."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from labadda.cli import alembic_config
from labadda.models import Board, Membership, TodoChange, TodoSource, TodoTask, Workspace
from tests.test_chat_board import stroke
from tests.test_panel import pair
from tests.test_todos import new_list


def prepare(api, workspace, target_workspace=None):
    op = api.post(f"/workspaces/{workspace}/board/ops", json=stroke(str(uuid.uuid4()), str(uuid.uuid4())))
    assert op.status_code == 200, op.text
    board = api.get(f"/workspaces/{workspace}/board").json()
    target = new_list(api, target_workspace)
    body = {
        "client_id": str(uuid.uuid4()),
        "title": "Review research plan",
        "description": "My reviewed followup",
        "source_workspace_id": workspace,
        "source_epoch": board["epoch"],
        "source_revision": board["revision"],
    }
    return target, f"/todos/lists/{target['id']}/from-board", body


@pytest.mark.parametrize("destination", [None, "section_a", "division"])
def test_scope_confirmation_replay_and_protected_context(as_user, ids, db_factory, destination):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    dest = ids["workspaces"][destination] if destination else None
    target, url, body = prepare(api, ws, dest)
    if destination == "division":
        assert api.post(url, json=body).status_code == 422
        body["confirm_audience"] = True
    result = api.post(url, json=body)
    assert result.status_code == 201, result.text
    task = result.json()
    path = f"/todos/lists/{target['id']}/tasks/{task['id']}"
    assert task["has_source"] is True and ws not in str(task) and "source_revision" not in task
    context = api.get(path + "/source").json()
    assert context["kind"] == "board" and context["revision"] == body["source_revision"]
    assert context["current_revision"] == context["revision"] and "body" not in context
    assert api.post(url, json=body).json()["id"] == task["id"]
    assert api.post(url, json={**body, "source_epoch": 2}).status_code == 409
    api.post(f"/workspaces/{ws}/board/ops", json=stroke(str(uuid.uuid4()), str(uuid.uuid4())))
    assert api.post(url, json=body).json()["id"] == task["id"]  # lost reply after later ink
    assert api.post(url, json={**body, "client_id": str(uuid.uuid4())}).status_code == 409
    if destination == "division":
        assert as_user("chen").get(path).status_code == 200
        response = as_user("chen").get(path + "/source")
        assert response.status_code == 404 and ws not in response.text
        assert ws not in str(as_user("chen").get(path + "/history").json())
    with db_factory() as db:
        assert len(db.scalars(select(TodoSource)).all()) == 1
        db.execute(
            delete(Membership).where(Membership.user_id == ids["users"]["ben"], Membership.workspace_id == ws)
        )
        db.commit()
    assert api.post(url, json=body).status_code == 404
    assert api.get(path + "/source").status_code == 404
    if destination is None:
        assert api.get(path).status_code == 200


def test_restore_and_purge_preserve_recorded_context_and_copy(as_user, ids, db_factory):
    api = as_user("asha")
    ws = ids["workspaces"]["section_a"]
    target, url, body = prepare(api, ws)
    row = api.post(url, json=body).json()
    path = f"/todos/lists/{target['id']}/tasks/{row['id']}"
    assert api.post(f"/workspaces/{ws}/board/restore", json={"revision": 1}).status_code == 200
    context = api.get(path + "/source").json()
    assert context["epoch"] == 1 and context["current_epoch"] == 2
    assert api.post(url, json=body).json()["id"] == row["id"]
    with db_factory() as db:
        # Synthetic isolated board removal exercises FK SET NULL without task loss.
        db.execute(delete(Board).where(Board.workspace_id == ws))
        db.commit()
        ref = db.get(TodoSource, row["id"])
        assert ref.board_workspace_id is None and ref.board_epoch == 1
    assert api.get(path + "/source").status_code == 404 and api.get(path).status_code == 200


def test_source_reader_and_destination_writer_and_panel(as_user, ids, make_client, db_factory):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    _target, url, body = prepare(api, ws)
    assert api.client.post(api.url(url), json=body).status_code == 403
    for name in ["chen", "dana", "admin"]:
        own = new_list(as_user(name))
        assert as_user(name).post(f"/todos/lists/{own['id']}/from-board", json=body).status_code == 404
    assert pair(as_user, make_client, ids).post(url, json=body).status_code == 401
    shared = new_list(api, ws)
    with db_factory() as db:
        db.get(Workspace, ws).posting_policy = "read_only"
        db.commit()
    assert api.post(f"/todos/lists/{shared['id']}/from-board", json=body).status_code == 403
    assert api.post(url, json=body).status_code == 201


@pytest.mark.parametrize("shared", [False, True])
def test_waiting_reference_rechecks_locked_board_context(as_user, ids, db_factory, shared):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    _, url, body = prepare(api, ws, ws if shared else None)
    with db_factory() as writer, ThreadPoolExecutor(max_workers=1) as pool:
        board = writer.scalar(select(Board).where(Board.workspace_id == ws).with_for_update())
        pending = pool.submit(api.post, url, json=body)
        deadline = time.monotonic() + 1.5
        blocked = False
        while time.monotonic() < deadline:
            writer.execute(text("select pg_stat_clear_snapshot()"))
            blocked = writer.scalar(
                text(
                    "select exists(select 1 from pg_stat_activity where datname=current_database() and "
                    "wait_event_type='Lock' and query like '%boards.workspace_id%FOR SHARE%')"
                )
            )
            if blocked:
                break
            time.sleep(0.01)
        try:
            assert blocked, "Conversion must wait for actual board row authority"
            board.revision += 1
            writer.commit()
        except BaseException:
            writer.rollback()
            raise
        result = pending.result(timeout=5)
        assert result.status_code == 409 and result.json()["error"]["code"] == "board_context_changed"
    with db_factory() as db:
        assert db.scalar(select(TodoTask)) is None


def test_rollback_and_populated_downgrade_guard(as_user, ids, settings, db_factory, monkeypatch):
    api = as_user("ben")
    _, url, body = prepare(api, ids["workspaces"]["section_a"])
    with monkeypatch.context() as patch:

        def fail(_):
            raise RuntimeError("synthetic board reference failure")

        patch.setattr(Session, "commit", fail)
        with pytest.raises(RuntimeError, match="synthetic board reference failure"):
            api.post(url, json=body)
    with db_factory() as db:
        assert (
            db.scalar(select(TodoTask)) is None
            and db.scalar(select(TodoChange)) is None
            and db.scalar(select(TodoSource)) is None
        )
    assert api.post(url, json=body).status_code == 201
    with pytest.raises(Exception, match="Task board references exist"):
        command.downgrade(alembic_config(settings.database_url), "0021")


def test_source_view_final_grant_recheck_and_expiry_before_commit(as_user, ids, db_factory, monkeypatch):
    from labadda import identity_locks
    from labadda.api import task_board_conversion

    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    target, url, body = prepare(api, ws)
    with monkeypatch.context() as patch:
        stage = task_board_conversion._create_task_row

        def expire(*args, **kw):
            result = stage(*args, **kw)
            patch.setattr(identity_locks, "session_valid", lambda *_: False)
            return result

        patch.setattr(task_board_conversion, "_create_task_row", expire)
        assert api.post(url, json=body).status_code == 401
    row = api.post(url, json=body).json()
    original = task_board_conversion._board
    calls = 0

    def revoke(*args, **kw):
        nonlocal calls
        board = original(*args, **kw)
        calls += 1
        if calls == 1:
            with db_factory() as db:
                db.execute(delete(Membership).where(Membership.user_id == ids["users"]["ben"]))
                db.commit()
        return board

    monkeypatch.setattr(task_board_conversion, "_board", revoke)
    result = api.get(f"/todos/lists/{target['id']}/tasks/{row['id']}/source")
    assert result.status_code == 404 and ws not in result.text


def test_source_purged_during_final_identity_refresh_is_uniformly_missing(
    as_user, ids, db_factory, monkeypatch
):
    from labadda.api import task_board_conversion

    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    target, url, body = prepare(api, ws)
    row = api.post(url, json=body).json()
    original = task_board_conversion._actor
    calls = 0

    def purge(*args, **kw):
        nonlocal calls
        calls += 1
        if calls == 2:
            with db_factory() as db:
                db.execute(delete(Board).where(Board.workspace_id == ws))
                db.commit()
        return original(*args, **kw)

    monkeypatch.setattr(task_board_conversion, "_actor", purge)
    assert api.get(f"/todos/lists/{target['id']}/tasks/{row['id']}/source").status_code == 404


def test_context_lookup_is_bounded_private_and_requires_existing_board(as_user, ids):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    _, _, body = prepare(api, ws)
    assert api.get("/todos/board-context/" + ws).json() == {
        "epoch": body["source_epoch"],
        "revision": body["source_revision"],
    }
    for name in ["chen", "dana", "admin"]:
        assert as_user(name).get("/todos/board-context/" + ws).status_code == 404
    assert api.get("/todos/board-context/" + ws, headers={"X-LabAdda-Panel": "1"}).status_code == 401
