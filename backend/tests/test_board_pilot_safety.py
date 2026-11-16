"""Board edits are atomic, revisioned, attributed and scoped to their selected board."""

import uuid

from sqlalchemy import select

from labadda.boardstate import state_at
from labadda.charges import board_key
from labadda.models import Board, ContentCharge


def operation(client, path, kind, *, index=0, object_id="note", revision=None, data=None):
    return client.post(
        path + "/ops",
        json={
            "op_id": uuid.uuid4().hex,
            "epoch": 1,
            "board_index": index,
            "type": kind,
            "object_id": object_id,
            "base_revision": revision,
            "payload": {"kind": "sticky", "data": data or {"x": 10, "y": 20, "text": "Original"}},
        },
    )


def test_atomic_edit_validates_before_replace_and_preserves_author(as_user, ids, db_factory):
    asha, bharat = as_user("asha"), as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    path = f"/workspaces/{workspace}/board"
    assert operation(bharat, path, "add").status_code == 200
    assert operation(asha, path, "update", revision=1, data={"text": ""}).status_code == 422
    assert (
        operation(asha, path, "update", revision=1, data={"x": 10, "y": 20, "text": "Edited"}).status_code
        == 200
    )
    assert operation(bharat, path, "update", revision=1).status_code == 409
    with db_factory() as db:
        obj = state_at(db, db.get(Board, uuid.UUID(workspace)))["note"]
        assert obj["data"]["text"] == "Edited"
        assert obj["author"] == ids["users"]["bharat"]
        assert obj["alive"]
    assert operation(asha, path, "undo").status_code == 200
    with db_factory() as db:
        assert state_at(db, db.get(Board, uuid.UUID(workspace)))["note"]["data"]["text"] == "Original"


def test_restore_on_secondary_preserves_first_board_and_ledger(as_user, ids, db_factory):
    client = as_user("asha")
    workspace = ids["workspaces"]["section_a"]
    path = f"/workspaces/{workspace}/board"
    assert operation(client, path, "add", index=0).status_code == 200
    assert operation(client, path, "add", index=1).status_code == 200
    assert client.post(path + "/restore", json={"revision": 0, "board_index": 1}).status_code == 200
    assert client.get(path).json()["epoch"] == 1
    assert client.get(path + "?board_index=1").json()["epoch"] == 2
    with db_factory() as db:
        charges = db.scalars(select(ContentCharge).where(ContentCharge.item_type == "board_object")).all()
        assert [(row.item_key, row.board_index) for row in charges] == [
            (board_key(uuid.UUID(workspace), "note"), 0)
        ]


def test_board_charge_keys_cannot_alias_across_boards():
    workspace = uuid.uuid4()
    assert board_key(workspace, "1:note", 0) != board_key(workspace, "note", 1)
    assert board_key(workspace, "1%3Anote", 0) != board_key(workspace, "1:note", 0)


def test_snapshot_retry_cannot_change_board_or_region(as_user, ids):
    client = as_user("asha")
    workspace = ids["workspaces"]["section_a"]
    path = f"/workspaces/{workspace}/board"
    for index in (0, 1):
        assert operation(client, path, "add", index=index).status_code == 200
    payload = {
        "revision": 1,
        "region": {"x": 0, "y": 0, "w": 200, "h": 120},
        "destination_id": workspace,
        "summary": "Tensile board snapshot",
        "client_id": uuid.uuid4().hex,
        "board_index": 1,
    }
    first = client.post(path + "/snapshots", json=payload)
    assert first.status_code == 201, first.text
    retry = client.post(path + "/snapshots", json=payload)
    assert retry.status_code == 201 and retry.json()["duplicate"]
    assert client.post(path + "/snapshots", json={**payload, "board_index": 0}).status_code == 409
    assert (
        client.post(
            path + "/snapshots", json={**payload, "region": {"x": 0, "y": 0, "w": 50, "h": 50}}
        ).status_code
        == 409
    )
