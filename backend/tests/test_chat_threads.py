"""C4 threads preserve actual scope, retry identity and current authority."""

import uuid

import pytest
from alembic import command
from labadda.cli import alembic_config
from labadda.models import ChatMessage
from sqlalchemy import select


def post(api, ws, body="Research root", parent=None, key=None):
    return api.post(
        f"/workspaces/{ws}/chat",
        json={"body": body, "client_id": key or str(uuid.uuid4()), "parent_id": parent},
    )


def test_reply_stream_retry_and_bounded_thread(as_user, ids):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    root = post(api, ws).json()
    key = str(uuid.uuid4())
    reply = post(as_user("asha"), ws, "Controls agreed", root["id"], key)
    assert reply.status_code == 201 and reply.json()["parent_id"] == root["id"]
    assert post(as_user("asha"), ws, "Controls agreed", root["id"], key).json()["id"] == reply.json()["id"]
    assert post(as_user("asha"), ws, "Controls agreed", None, key).status_code == 409
    for i in range(3):
        assert post(api, ws, "Reply " + str(i), root["id"]).status_code == 201
    path = f"/workspaces/{ws}/chat/{root['id']}/replies"
    page = api.get(path + "?limit=2").json()
    assert [m["body"] for m in page["messages"]] == ["Reply 1", "Reply 2"] and page["next_before"]
    older = api.get(path + f"?limit=2&before={page['next_before']}").json()
    assert [m["body"] for m in older["messages"]] == ["Controls agreed", "Reply 0"]
    stream = api.get(f"/workspaces/{ws}/chat?after={root['seq']}").json()["messages"]
    assert len(stream) == 4 and all(m["parent_id"] == root["id"] for m in stream)
    assert post(api, ws, "Nested", reply.json()["id"]).status_code == 422


@pytest.mark.parametrize(
    "scope,allowed,denied",
    [("section_a", "asha", "chen"), ("division", "chen", "eli"), ("reading_club", "chen", "dana")],
)
def test_thread_scope_and_parent_spoofing(as_user, ids, scope, allowed, denied):
    ws = ids["workspaces"][scope]
    api = as_user("ben")
    root = post(api, ws).json()
    path = f"/workspaces/{ws}/chat/{root['id']}/replies"
    assert post(as_user(allowed), ws, "Accepted", root["id"]).status_code == 201
    for who in [denied, "admin"]:
        assert as_user(who).get(path).status_code == 404
        assert post(as_user(who), ws, "Denied", root["id"]).status_code == 404
    other = ids["workspaces"]["root"]
    assert post(api, other, "Spoofed", root["id"]).status_code == 404
    assert api.get(path, headers={"X-LabAdda-Panel": "1"}).status_code == 401


def test_replay_after_revocation_and_expiry_before_commit(as_user, ids, db_factory, monkeypatch):
    from labadda import identity_locks
    from labadda.api import chat

    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    root = post(api, ws).json()
    original = chat._root

    def expire(*args):
        result = original(*args)
        monkeypatch.setattr(identity_locks, "session_valid", lambda *_: False)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(chat, "_root", expire)
        assert post(api, ws, "Must not commit", root["id"]).status_code == 401
    with db_factory() as db:
        assert len(db.scalars(select(ChatMessage)).all()) == 1


def test_thread_downgrade_guard(as_user, ids, settings):
    api = as_user("ben")
    ws = ids["workspaces"]["section_a"]
    root = post(api, ws).json()
    assert post(api, ws, "Kept reply", root["id"]).status_code == 201
    with pytest.raises(Exception, match="Chat replies exist"):
        command.downgrade(alembic_config(settings.database_url), "0022")


def test_two_authors_cannot_commit_higher_sequence_first(as_user, ids, db_factory, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from labadda.api import chat

    ben, asha = as_user("ben"), as_user("asha")
    ws = ids["workspaces"]["section_a"]
    entered, release = Event(), Event()
    original = chat._mark_read

    def pause(db, user, workspace, seq):
        original(db, user, workspace, seq)
        if str(user) == ids["users"]["ben"]:
            entered.set()
            assert release.wait(1.5)

    monkeypatch.setattr(chat, "_mark_read", pause)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(post, ben, ws, "First committed")
        assert entered.wait(1)
        second = pool.submit(post, asha, ws, "Second committed")
        try:
            import time

            time.sleep(0.1)
            with db_factory() as db:
                assert db.scalar(select(ChatMessage)) is None
        finally:
            release.set()
        assert first.result(timeout=3).status_code == 201 and second.result(timeout=3).status_code == 201
    messages = ben.get(f"/workspaces/{ws}/chat").json()["messages"]
    assert [m["body"] for m in messages] == ["First committed", "Second committed"]
