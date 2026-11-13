"""T47: reviewed copies, independent source access and atomic durable provenance."""

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from labadda.cli import alembic_config
from labadda.models import Membership, Post, TodoChange, TodoSource, TodoTask, Workspace
from tests.migration_helpers import downgrade_legacy
from tests.test_panel import pair
from tests.test_todos import new_list


def source(api, workspace, kind):
    url = f"/workspaces/{workspace}/" + ("posts" if kind == "post" else "chat")
    response = api.post(url, json={"body": "Source-only measurement α", "client_id": str(uuid.uuid4())})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def conversion(source_id, kind="post", **fields):
    return {
        "client_id": str(uuid.uuid4()),
        "title": "Reviewed action",
        "description": "Deliberately chosen task text",
        "source_kind": kind,
        "source_id": source_id,
        **fields,
    }


@pytest.mark.parametrize("kind", ["post", "chat"])
@pytest.mark.parametrize("destination", ["section_a", "division", None])
def test_conversion_copy_audience_provenance_and_replay(as_user, ids, db_factory, kind, destination):
    bharat = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    src = source(bharat, workspace, kind)
    target = new_list(bharat, ids["workspaces"][destination] if destination else None)
    url = f"/todos/lists/{target['id']}/from-conversation"
    body = conversion(src, kind)
    if destination == "division":
        response = bharat.post(url, json=body)
        assert (
            response.status_code == 422
            and response.json()["error"]["code"] == "audience_confirmation_required"
        )
        body["confirm_audience"] = True
    response = bharat.post(url, json=body)
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["has_source"] is True
    path = f"/todos/lists/{target['id']}/tasks/{row['id']}"
    assert row["description"] == "Deliberately chosen task text"
    assert "Source-only" not in str(row) and src not in str(row)
    assert bharat.get(path + "/source").json()["body"] == "Source-only measurement α"
    assert bharat.post(url, json=body).json()["id"] == row["id"]
    assert bharat.post(url, json={**body, "title": "Different intent"}).status_code == 409
    # Original creation endpoint cannot reuse a conversion identity.
    assert (
        bharat.post(
            f"/todos/lists/{target['id']}/tasks",
            json={k: v for k, v in body.items() if k not in ["source_kind", "source_id", "confirm_audience"]},
        ).status_code
        == 409
    )
    with db_factory() as db:
        assert len(db.scalars(select(TodoSource)).all()) == 1
        assert len(db.scalars(select(TodoChange)).all()) == 1
    if destination == "division":
        chitra = as_user("chitra")
        assert chitra.get(path).status_code == 200
        denied = chitra.get(path + "/source")
        assert denied.status_code == 404 and src not in denied.text
        assert src not in str(chitra.get(path + "/history").json())
    if destination is None:
        assert as_user("asha").get(path + "/source").status_code == 404
    with db_factory() as db:
        db.execute(
            delete(Membership).where(
                Membership.user_id == ids["users"]["bharat"], Membership.workspace_id == workspace
            )
        )
        db.commit()
    assert bharat.get(path + "/source").status_code == 404
    assert bharat.post(url, json=body).status_code == 404
    if destination is None:
        assert bharat.get(path).status_code == 200  # Reviewed private copy survives source grant loss.


def test_denied_source_and_destination_and_panel(as_user, ids, make_client):
    bharat = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    src = source(bharat, workspace, "post")
    row = new_list(bharat)
    url = f"/todos/lists/{row['id']}/from-conversation"
    body = conversion(src)
    for name in ["chitra", "deepa", "admin"]:
        own = new_list(as_user(name))
        assert as_user(name).post(f"/todos/lists/{own['id']}/from-conversation", json=body).status_code == 404
        assert as_user(name).post(url, json=body).status_code == 404
    panel = pair(as_user, make_client, ids)
    assert panel.post(url, json=body).status_code == 401
    assert bharat.post(url, json=conversion(str(uuid.uuid4()))).status_code == 404
    assert bharat.post(url, json=conversion(src, "chat")).status_code == 404


def test_read_only_source_allowed_but_destination_denied(as_user, ids, db_factory):
    bharat = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    src = source(bharat, workspace, "post")
    private = new_list(bharat)
    shared = new_list(bharat, workspace)
    with db_factory() as db:
        db.get(Workspace, workspace).posting_policy = "read_only"
        db.commit()
    assert (
        bharat.post(f"/todos/lists/{shared['id']}/from-conversation", json=conversion(src)).status_code == 403
    )
    assert (
        bharat.post(f"/todos/lists/{private['id']}/from-conversation", json=conversion(src)).status_code
        == 201
    )


def test_removed_or_purged_source_becomes_unavailable_without_deleting_task(as_user, ids, db_factory):
    bharat = as_user("bharat")
    src = source(bharat, ids["workspaces"]["section_a"], "post")
    target = new_list(bharat)
    response = bharat.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src))
    path = f"/todos/lists/{target['id']}/tasks/{response.json()['id']}"
    assert bharat.delete("/posts/" + src).status_code == 200
    assert bharat.get(path + "/source").status_code == 404
    assert (
        bharat.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src)).status_code == 404
    )
    with db_factory() as db:
        db.execute(delete(Post).where(Post.id == src))
        db.commit()
        assert db.get(TodoSource, response.json()["id"]).post_id is None
    assert bharat.get(path).status_code == 200
    assert bharat.get(path + "/source").status_code == 404


def test_rollback_keeps_task_history_reference_and_event_atomic(as_user, ids, app, db_factory, monkeypatch):
    bharat = as_user("bharat")
    src = source(bharat, ids["workspaces"]["section_a"], "chat")
    target = new_list(bharat)
    events = []
    monkeypatch.setattr(app.state.hub, "publish", lambda *args: events.append(args))

    def fail(db):
        raise RuntimeError("synthetic reference failure")

    monkeypatch.setattr(Session, "commit", fail)
    with pytest.raises(RuntimeError, match="synthetic reference failure"):
        bharat.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src, "chat"))
    with db_factory() as db:
        assert db.scalar(select(TodoTask)) is None
        assert db.scalar(select(TodoChange)) is None
        assert db.scalar(select(TodoSource)) is None
    assert events == []


def test_populated_reference_blocks_lossy_downgrade(as_user, ids, settings):
    bharat = as_user("bharat")
    src = source(bharat, ids["workspaces"]["section_a"], "post")
    target = new_list(bharat)
    assert (
        bharat.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src)).status_code == 201
    )
    with pytest.raises(Exception, match="Task sources exist"):
        downgrade_legacy(alembic_config(settings.database_url), "0020")


@pytest.mark.parametrize("shared", [False, True])
def test_source_deleted_while_conversion_waits_is_not_accepted(as_user, ids, db_factory, shared):
    import time
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import text

    from labadda.security import utcnow

    bharat = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    src = source(bharat, workspace, "post")
    target = new_list(bharat, workspace if shared else None)
    with db_factory() as writer, ThreadPoolExecutor(max_workers=1) as pool:
        post = writer.scalar(select(Post).where(Post.id == src).with_for_update())
        pending = pool.submit(
            bharat.post, f"/todos/lists/{target['id']}/from-conversation", json=conversion(src)
        )
        deadline = time.monotonic() + 1.5
        blocked = False
        while time.monotonic() < deadline:
            writer.execute(text("select pg_stat_clear_snapshot()"))
            blocked = writer.scalar(
                text(
                    "select exists(select 1 from pg_stat_activity where datname=current_database() and "
                    "wait_event_type='Lock' and query like '%posts.id%FOR SHARE%')"
                )
            )
            if blocked:
                break
            time.sleep(0.01)
        try:
            assert blocked, "Conversion must wait on the actual source row"
            post.deleted_at = utcnow()
            writer.commit()
        except BaseException:
            writer.rollback()
            raise
        assert pending.result(timeout=5).status_code == 404
    with db_factory() as db:
        assert db.scalar(select(TodoTask)) is None


def test_expired_authority_before_commit_leaves_no_copy(as_user, ids, db_factory, monkeypatch):
    from labadda import identity_locks
    from labadda.api import task_conversion

    bharat = as_user("bharat")
    src = source(bharat, ids["workspaces"]["section_a"], "post")
    target = new_list(bharat)
    stage = task_conversion._create_task_row

    def expire(*args, **kw):
        result = stage(*args, **kw)
        monkeypatch.setattr(identity_locks, "session_valid", lambda *_: False)
        return result

    monkeypatch.setattr(task_conversion, "_create_task_row", expire)
    assert (
        bharat.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src)).status_code == 401
    )
    with db_factory() as db:
        assert db.scalar(select(TodoTask)) is None
        assert db.scalar(select(TodoSource)) is None


def test_source_view_rechecks_access_after_serialization(as_user, ids, db_factory, monkeypatch):
    from labadda.api import task_conversion

    bharat = as_user("bharat")
    src = source(bharat, ids["workspaces"]["section_a"], "chat")
    target = new_list(bharat)
    row = bharat.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src, "chat")).json()
    original = task_conversion.iso

    def revoke(value):
        result = original(value)
        with db_factory() as db:
            db.execute(delete(Membership).where(Membership.user_id == ids["users"]["bharat"]))
            db.commit()
        return result

    monkeypatch.setattr(task_conversion, "iso", revoke)
    response = bharat.get(f"/todos/lists/{target['id']}/tasks/{row['id']}/source")
    assert response.status_code == 404 and "Source-only" not in response.text


def test_hard_source_purge_during_final_refresh_returns_uniform404(as_user, ids, db_factory, monkeypatch):
    from labadda.api import task_conversion

    api = as_user("bharat")
    src = source(api, ids["workspaces"]["section_a"], "post")
    target = new_list(api)
    row = api.post(f"/todos/lists/{target['id']}/from-conversation", json=conversion(src)).json()
    original = task_conversion._actor
    calls = 0

    def purge(*args, **kw):
        nonlocal calls
        calls += 1
        if calls == 2:
            with db_factory() as db:
                db.execute(delete(Post).where(Post.id == src))
                db.commit()
        return original(*args, **kw)

    monkeypatch.setattr(task_conversion, "_actor", purge)
    assert api.get(f"/todos/lists/{target['id']}/tasks/{row['id']}/source").status_code == 404
