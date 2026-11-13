"""Private whiteboards isolate owners and preserve history and competing drafts."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import select

from labadda.cli import alembic_config
from labadda.models import PersonalBoardRevision


def note(text="Private test note"):
    return {"id": str(uuid.uuid4()), "kind": "sticky", "color": "yellow", "text": text}


def test_save_read_retry_and_conflict(as_user, db_factory):
    owner = as_user("asha")
    assert owner.get("/me/whiteboard").json() == {"revision": 0, "objects": []}
    body = {"revision": 0, "objects": [note()]}
    saved = owner.put("/me/whiteboard", json=body)
    assert saved.status_code == 200
    assert owner.put("/me/whiteboard", json=body).json() == saved.json()
    assert owner.get("/me/whiteboard").json() == saved.json()
    conflict = owner.put("/me/whiteboard", json={"revision": 0, "objects": [note("Competing edit")]})
    assert conflict.status_code == 409
    assert owner.get("/me/whiteboard").json() == saved.json()
    assert owner.put("/me/whiteboard", json={"revision": 1, "objects": []}).status_code == 200
    with db_factory() as db:
        rows = db.scalars(select(PersonalBoardRevision).order_by(PersonalBoardRevision.revision)).all()
        assert len(rows) == 2
        assert rows[0].objects[0]["text"] == "Private test note"


@pytest.mark.parametrize("other", ["ben", "chen", "dana", "admin", "eli"])
def test_no_other_user_or_admin_content_access(as_user, other):
    as_user("asha").put("/me/whiteboard", json={"revision": 0, "objects": [note("Private marker")]})
    client = as_user(other)
    assert client.get("/me/whiteboard").json() == {"revision": 0, "objects": []}
    assert client.put("/me/whiteboard", json={"revision": 0, "objects": [note(other)]}).status_code == 200
    assert as_user("asha").get("/me/whiteboard").json()["objects"][0]["text"] == "Private marker"


def test_denied_and_scope_injection(as_user, make_client):
    client = make_client()
    assert client.get("/me/whiteboard").status_code == 401
    assert client.login("fay").status_code == 401
    owner = as_user("asha")
    for path, headers in [("/me/whiteboard", {"X-LabAdda-Panel": "1"}), ("/me/whiteboard?panel=1", {})]:
        assert owner.get(path, headers=headers).status_code == 401
        assert owner.put(path, json={"revision": 0, "objects": []}, headers=headers).status_code == 401
    assert (
        owner.put(
            "/me/whiteboard", json={"revision": 0, "objects": [], "owner_id": str(uuid.uuid4())}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "objects", [[{**note(), "x": -1}], [{**note(), "points": [[1001, 0]]}], [note()] * 501]
)
def test_invalid_documents_rejected(as_user, objects):
    assert as_user("asha").put("/me/whiteboard", json={"revision": 0, "objects": objects}).status_code == 422


def test_two_tabs_cannot_overwrite_each_other(as_user):
    first, second = as_user("asha"), as_user("asha")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda client: client.put("/me/whiteboard", json={"revision": 0, "objects": [note()]}),
                [first, second],
            )
        )
    assert sorted(response.status_code for response in results) == [200, 409]


def test_populated_migration_cannot_discard_work(as_user, settings):
    as_user("asha").put("/me/whiteboard", json={"revision": 0, "objects": [note()]})
    with pytest.raises(RuntimeError, match="Personal whiteboard history exists"):
        command.downgrade(alembic_config(settings.database_url), "0036")
