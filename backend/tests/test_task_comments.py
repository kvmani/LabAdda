"""T45 scoped immutable discussion, retry identity and monotonic append sequence."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import delete, select

from labadda.cli import alembic_config
from labadda.models import Membership, TodoComment, Workspace
from tests.test_task_assignment import task


def body(text="Observe sample α", key=None):
    return {"client_id": key or str(uuid.uuid4()), "body": text}


def test_comment_create_replay_binding_and_task_revision(as_user):
    api = as_user("ben")
    _, created, path = task(api)
    payload = body()
    one = api.post(path + "/comments", json=payload)
    assert one.status_code == 201, one.text
    assert one.json()["sequence"] == 1 and one.json()["author"]["display_name"] == "Ben Okafor"
    assert api.post(path + "/comments", json=payload).json()["id"] == one.json()["id"]
    assert api.post(path + "/comments", json={**payload, "body": "changed"}).status_code == 409
    _, _, other = task(api)
    assert api.post(other + "/comments", json=payload).status_code == 409
    assert api.get(path).json()["revision"] == created["revision"]
    assert len(api.get(path + "/comments").json()["items"]) == 1


def test_personal_comments_are_owner_only(as_user):
    api = as_user("ben")
    _, _, path = task(api)
    api.post(path + "/comments", json=body())
    for name in ["asha", "chen", "dana", "admin"]:
        assert as_user(name).get(path + "/comments").status_code == 404
        assert as_user(name).post(path + "/comments", json=body()).status_code == 404


@pytest.mark.parametrize(
    "author,scope,reader,outsider",
    [
        ("ben", "section_a", "asha", "chen"),
        ("ben", "division", "chen", "eli"),
        ("ben", "reading_club", "chen", "dana"),
        ("eli", "project", "dana", "ben"),
    ],
)
def test_shared_comments_follow_actual_source_policy(as_user, ids, author, scope, reader, outsider):
    api = as_user(author)
    _, _, path = task(api, ids["workspaces"][scope])
    assert api.post(path + "/comments", json=body()).status_code == 201
    assert as_user(reader).get(path + "/comments").status_code == 200
    assert as_user(reader).post(path + "/comments", json=body()).status_code == 201
    assert as_user(outsider).get(path + "/comments").status_code == 404
    assert as_user("admin").get(path + "/comments").status_code == 404


def test_read_only_archive_and_revoked_access(as_user, ids, db_factory):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    _, _, path = task(api, ws)
    payload = body()
    api.post(path + "/comments", json=payload)
    with db_factory() as db:
        db.get(Workspace, ws).posting_policy = "read_only"
        db.commit()
    assert api.get(path + "/comments").status_code == 200
    assert api.post(path + "/comments", json=body()).status_code == 403
    assert api.post(path + "/comments", json=payload).status_code == 403
    assert as_user("asha").post(path + "/comments", json=body()).status_code == 201
    with db_factory() as db:
        db.get(Workspace, ws).archived = True
        db.commit()
    assert as_user("asha").post(path + "/comments", json=body()).status_code == 403
    assert (
        as_user("admin").delete(f"/admin/workspaces/{ws}/memberships/{ids['users']['ben']}").status_code
        == 200
    )
    assert api.get(path + "/comments").status_code == 404


def test_parallel_writers_sequence_and_page_bounds(as_user, ids):
    api = as_user("ben")
    other = as_user("asha")
    _, _, path = task(api, ids["workspaces"]["section_a"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(actor.post, path + "/comments", json=body(text))
            for actor, text in [(api, "first"), (other, "second")]
        ]
        assert sorted(r.result().json()["sequence"] for r in results) == [1, 2]
    api.post(path + "/comments", json=body("third"))
    first = api.get(path + "/comments?limit=2").json()
    second = api.get(path + "/comments?before=" + str(first["next_cursor"])).json()
    assert [r["sequence"] for r in first["items"]] == [3, 2]
    assert [r["sequence"] for r in second["items"]] == [1]
    assert api.get(path + "/comments?limit=51").status_code == 422
    assert api.get(path + "/comments?before=0").status_code == 422


@pytest.mark.parametrize("text", [" ", "x" * 4001])
def test_comment_validation(as_user, text):
    api = as_user("ben")
    _, _, path = task(api)
    assert api.post(path + "/comments", json=body(text)).status_code == 422


def test_panel_csrf_and_wrong_task_parent(as_user):
    api = as_user("ben")
    _row, created, path = task(api)
    other, _, _ = task(api)
    assert api.get(path + "/comments", headers={"X-LabAdda-Panel": "1"}).status_code == 401
    assert api.get(path + "/comments?panel=1").status_code == 401
    assert api.client.post(api.url(path + "/comments"), json=body()).status_code == 403
    assert api.get(f"/todos/lists/{other['id']}/tasks/{created['id']}/comments").status_code == 404


def test_read_rechecks_grants_after_serialization(as_user, ids, db_factory, monkeypatch):
    from labadda.api import task_comments

    api = as_user("ben")
    _, _, path = task(api, ids["workspaces"]["section_a"])
    api.post(path + "/comments", json=body())
    serialize = task_comments._json

    def revoke(row):
        result = serialize(row)
        with db_factory() as db:
            db.execute(delete(Membership).where(Membership.user_id == ids["users"]["ben"]))
            db.commit()
        return result

    monkeypatch.setattr(task_comments, "_json", revoke)
    assert api.get(path + "/comments").status_code == 404


def test_capacity_replay_at_limit(as_user, db_factory):
    api = as_user("ben")
    _, _created, path = task(api)
    payload = body()
    saved = api.post(path + "/comments", json=payload).json()
    with db_factory() as db:
        # A high sequence simulates the immutable append ceiling without1000 HTTP writes.
        row = db.scalar(select(TodoComment))
        row.sequence = 1000
        db.commit()
    assert api.post(path + "/comments", json=payload).json()["id"] == saved["id"]
    assert api.post(path + "/comments", json=body()).status_code == 422


def test_expiry_before_commit_does_not_append(as_user, monkeypatch, db_factory):
    from labadda import identity_locks
    from labadda.api import task_comments

    api = as_user("ben")
    _, _, path = task(api)
    authorize = task_comments._task

    def expire(db, user, list_id, task_id, write=False):
        result = authorize(db, user, list_id, task_id, write)
        if write:
            monkeypatch.setattr(identity_locks, "session_valid", lambda *_: False)
        return result

    monkeypatch.setattr(task_comments, "_task", expire)
    assert api.post(path + "/comments", json=body()).status_code == 401
    with db_factory() as db:
        assert db.scalar(select(TodoComment)) is None


def test_comment_history_protected_by_downgrade(as_user, settings):
    api = as_user("ben")
    _, _, path = task(api)
    api.post(path + "/comments", json=body())
    with pytest.raises(RuntimeError, match="Task comments exist"):
        command.downgrade(alembic_config(settings.database_url), "0019")
