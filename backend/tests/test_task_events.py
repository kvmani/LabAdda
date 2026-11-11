"""T46: shared invalidation has no private payload and follows commit/access."""

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from labadda.models import Membership, TodoList, TodoTask, TodoComment
from tests.test_realtime import recv_until, shared_loop_sockets
from tests.test_todos import task_body
from tests.test_task_assignment import task


def test_mutations_publish_only_after_commit_and_replays_stay_quiet(
    as_user, ids, app, db_factory, monkeypatch
):
    api = as_user("ben")
    workspace = ids["workspaces"]["section_a"]
    observed = []

    def publish(scope, event):
        assert str(scope) == workspace
        assert event == {"type": "tasks.changed", "workspace_id": workspace}
        # A different connection must see each committed mutation at fanout time.
        with db_factory() as db:
            observed.append(
                (
                    db.scalars(select(TodoList)).all(),
                    db.scalars(select(TodoTask)).all(),
                    db.scalars(select(TodoComment)).all(),
                )
            )

    monkeypatch.setattr(app.state.hub, "publish", publish)
    body = {"client_id": str(uuid.uuid4()), "title": "Shared", "workspace_id": workspace}
    row = api.post("/todos/lists", json=body).json()
    assert len(observed) == 1 and observed[-1][0][0].title == "Shared"
    assert api.post("/todos/lists", json=body).status_code == 201
    assert len(observed) == 1
    path = f"/todos/lists/{row['id']}"
    assert api.put(path, json={"revision": 1, "title": "Renamed"}).status_code == 200
    assert len(observed) == 2 and observed[-1][0][0].title == "Renamed"
    body = task_body()
    created = api.post(path + "/tasks", json=body).json()
    assert len(observed) == 3 and observed[-1][1][0].id == uuid.UUID(created["id"])
    assert api.post(path + "/tasks", json=body).status_code == 201
    assert len(observed) == 3
    detail = path + "/tasks/" + created["id"]
    edit = {**body, "revision": 1, "title": "Reviewed"}
    edit.pop("client_id")
    assert api.put(detail, json=edit).status_code == 200
    assert len(observed) == 4 and observed[-1][1][0].title == "Reviewed"
    assert (
        api.put(detail + "/assignee", json={"revision": 2, "user_id": ids["users"]["asha"]}).status_code
        == 200
    )
    assert len(observed) == 5 and str(observed[-1][1][0].assignee_id) == ids["users"]["asha"]
    assert (
        api.put(detail + "/assignee", json={"revision": 3, "user_id": ids["users"]["asha"]}).status_code
        == 200
    )
    assert len(observed) == 5
    comment = {"client_id": str(uuid.uuid4()), "body": "Actual discussion"}
    assert api.post(detail + "/comments", json=comment).status_code == 201
    assert len(observed) == 6 and observed[-1][2][0].body == comment["body"]
    assert api.post(detail + "/comments", json=comment).status_code == 201
    assert len(observed) == 6
    assert api.put(detail, json=edit).status_code == 409
    assert as_user("chen").post(detail + "/comments", json=comment).status_code == 404
    assert len(observed) == 6


def test_personal_mutations_never_enter_workspace_channels(as_user, app, monkeypatch, ids):
    events = []
    monkeypatch.setattr(app.state.hub, "publish", lambda *args: events.append(args))
    api = as_user("ben")
    row, created, path = task(api)
    api.put("/todos/lists/" + row["id"], json={"revision": 1, "title": "Private rename"})
    fields = task_body()
    fields.pop("client_id")
    assert api.put(path, json={**fields, "revision": 1}).status_code == 200
    assert (
        api.put(path + "/assignee", json={"revision": 2, "user_id": ids["users"]["ben"]}).status_code == 200
    )
    assert (
        api.post(path + "/comments", json={"client_id": str(uuid.uuid4()), "body": "Private"}).status_code
        == 201
    )
    assert events == []


def test_commit_failure_emits_nothing(as_user, ids, app, db_factory, monkeypatch):
    api = as_user("ben")
    events = []
    monkeypatch.setattr(app.state.hub, "publish", lambda *args: events.append(args))
    with monkeypatch.context() as patch:

        def fail(_):
            raise RuntimeError("synthetic commit failure")

        patch.setattr(Session, "commit", fail)
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            api.post(
                "/todos/lists",
                json={
                    "client_id": str(uuid.uuid4()),
                    "title": "Uncommitted",
                    "workspace_id": ids["workspaces"]["section_a"],
                },
            )
    assert events == []
    with db_factory() as db:
        assert db.scalar(select(TodoList)) is None


def test_delivery_rechecks_grants_and_reconnect_reads_durable_state(as_user, ids, settings, app, db_factory):
    workspace = ids["workspaces"]["section_a"]
    ben, asha = as_user("ben"), as_user("asha")
    row, created, path = task(asha, workspace)
    with shared_loop_sockets(app, settings, [ben, asha], workspace) as (ben_ws, asha_ws):
        # Bypass explicit socket revocation: delivery itself must enforce the new grant.
        with db_factory() as db:
            db.execute(
                delete(Membership).where(
                    Membership.user_id == ids["users"]["ben"], Membership.workspace_id == workspace
                )
            )
            db.commit()
        assert (
            asha.post(
                path + "/comments", json={"client_id": str(uuid.uuid4()), "body": "After removal"}
            ).status_code
            == 201
        )
        assert recv_until(ben_ws, "revoked")["workspace_id"] == workspace
        assert recv_until(asha_ws, "tasks.changed") == {"type": "tasks.changed", "workspace_id": workspace}
        assert ben.get(path + "/comments").status_code == 404
    # No socket is open during this write. HTTP catch-up still returns committed state.
    assert (
        asha.post(
            path + "/comments", json={"client_id": str(uuid.uuid4()), "body": "Offline write"}
        ).status_code
        == 201
    )
    with shared_loop_sockets(app, settings, [asha], workspace):
        assert asha.get(path + "/comments").json()["items"][0]["body"] == "Offline write"
