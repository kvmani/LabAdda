"""Private whiteboards isolate owners and preserve history and competing drafts."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import select

from labadda.cli import alembic_config
from labadda.models import PersonalBoardRevision, User
from tests.test_panel import pair


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


@pytest.mark.parametrize("other", ["bharat", "chitra", "deepa", "admin", "esha"])
def test_no_other_user_or_admin_content_access(as_user, other):
    as_user("asha").put("/me/whiteboard", json={"revision": 0, "objects": [note("Private marker")]})
    client = as_user(other)
    assert client.get("/me/whiteboard").json() == {"revision": 0, "objects": []}
    assert client.put("/me/whiteboard", json={"revision": 0, "objects": [note(other)]}).status_code == 200
    assert as_user("asha").get("/me/whiteboard").json()["objects"][0]["text"] == "Private marker"


def test_denied_and_scope_injection(as_user, make_client):
    client = make_client()
    assert client.get("/me/whiteboard").status_code == 401
    assert client.login("farhan").status_code == 401
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


def test_real_panel_session_and_deactivated_owner_are_refused(as_user, make_client, ids, db_factory):
    owner = as_user("asha")
    owner.put("/me/whiteboard", json={"revision": 0, "objects": [note("Hidden")]})
    kiosk = pair(as_user, make_client, ids, user="asha")
    assert kiosk.get("/me/whiteboard").status_code == 401
    with db_factory() as db:
        db.get(User, ids["users"]["asha"]).is_active = False
        db.commit()
    assert owner.get("/me/whiteboard").status_code == 401
    assert owner.put("/me/whiteboard", json={"revision": 1, "objects": []}).status_code == 401


def stroke(points):
    return {**note(), "kind": "stroke", "color": "teal", "points": points}


def test_oversized_documents_are_rejected_and_nothing_is_stored(as_user):
    owner = as_user("asha")
    many_points = [stroke([[1.0, 2.0]] * 2000) for _ in range(11)]
    assert owner.put("/me/whiteboard", json={"revision": 0, "objects": many_points}).status_code == 422
    big_text = [note("x" * 1000) for _ in range(500)]
    assert owner.put("/me/whiteboard", json={"revision": 0, "objects": big_text}).status_code == 422
    assert owner.get("/me/whiteboard").json() == {"revision": 0, "objects": []}


def test_personal_tabbed_whiteboard(as_user):
    """Personal whiteboard supports multiple tabbed boards with independent state."""
    bharat = as_user("bharat")

    # 1. Fetch tabs
    tabs_res = bharat.get("/me/whiteboard/tabs")
    assert tabs_res.status_code == 200
    assert len(tabs_res.json()) >= 1

    # 2. Update titles for Board 0 and Board 1 with short names (<= 10 chars)
    r_t0 = bharat.patch("/me/whiteboard/0/title", json={"title": "Brainstorm"})
    assert r_t0.status_code == 200
    assert r_t0.json()["title"] == "Brainstorm"

    r_t1 = bharat.patch("/me/whiteboard/1/title", json={"title": "Priorities"})
    assert r_t1.status_code == 200
    assert r_t1.json()["title"] == "Priorities"

    # Custom names > 10 chars are rejected with 422
    assert bharat.patch("/me/whiteboard/0/title", json={"title": "LongPersonalTitle"}).status_code == 422

    # 3. Save objects to Board 1
    sticky_id = str(uuid.uuid4())
    b1_save = bharat.put(
        "/me/whiteboard",
        json={
            "revision": 0,
            "board_index": 1,
            "objects": [
                {
                    "id": sticky_id,
                    "kind": "sticky",
                    "x": 100,
                    "y": 100,
                    "w": 140,
                    "h": 140,
                    "text": "Review SEM sample preparation",
                    "color": "#fff",
                }
            ],
        },
    )
    assert b1_save.status_code == 200
    saved_b1 = b1_save.json()
    assert saved_b1["revision"] == 1
    assert saved_b1["board_index"] == 1

    # 4. Verify Board 0 remains clean
    b0 = bharat.get("/me/whiteboard?board_index=0").json()
    assert b0["revision"] == 0
    assert b0["objects"] == []

    # 5. Verify Board 1 returns its saved object
    b1 = bharat.get("/me/whiteboard?board_index=1").json()
    assert b1["revision"] == 1
    assert len(b1["objects"]) == 1
    assert b1["objects"][0]["text"] == "Review SEM sample preparation"
