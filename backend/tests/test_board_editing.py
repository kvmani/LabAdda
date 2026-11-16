"""Small font vocabulary survives shared/private saves and offline image exports."""

import uuid

import pytest

from labadda.board_fonts import board_font
from labadda.boardstate import render_png


def shared_note(client, workspace, **style):
    return client.post(
        f"/workspaces/{workspace}/board/ops",
        json={
            "op_id": uuid.uuid4().hex,
            "epoch": 1,
            "type": "add",
            "object_id": uuid.uuid4().hex,
            "payload": {
                "kind": "text",
                "data": {"x": 10, "y": 10, "text": "Materials research", "color": "#1f2933", **style},
            },
        },
    )


@pytest.mark.parametrize("family", ["sans", "serif", "mono", "handwritten"])
def test_shared_board_font_round_trip(as_user, ids, family):
    client = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    saved = shared_note(client, workspace, font_family=family, font_size=32)
    assert saved.status_code == 200
    replay = client.get(f"/workspaces/{workspace}/board").json()["ops"]
    assert replay[0]["payload"]["data"]["font_family"] == family
    assert replay[0]["payload"]["data"]["font_size"] == 32
    assert board_font({"font_family": family, "font_size": 32}, 1).getlength("Materials") > 0


@pytest.mark.parametrize(
    "style",
    [
        {"font_family": "../../some-file"},
        {"font_family": "url(https://outside.example)"},
        {"font_family": None},
        {"font_size": True},
        {"font_size": "32"},
        {"font_size": 7},
        {"font_size": 49},
        {"font_size": 12.5},
    ],
)
def test_shared_font_validation_is_atomic(as_user, ids, style):
    client = as_user("bharat")
    workspace = ids["workspaces"]["section_a"]
    assert shared_note(client, workspace, **style).status_code == 422
    assert client.get(f"/workspaces/{workspace}/board").json()["revision"] == 0


def test_private_board_preserves_font_and_position(as_user):
    client = as_user("bharat")
    object_id = str(uuid.uuid4())
    response = client.put(
        "/me/whiteboard",
        json={
            "revision": 0,
            "objects": [
                {
                    "id": object_id,
                    "kind": "sticky",
                    "text": "Private material idea",
                    "x": 100,
                    "y": 80,
                    "font_family": "handwritten",
                    "font_size": 24,
                }
            ],
        },
    )
    assert response.status_code == 200
    restored = client.get("/me/whiteboard").json()["objects"][0]
    assert restored["id"] == object_id
    assert restored["font_family"] == "handwritten"
    assert restored["font_size"] == 24
    assert restored["x"] == 100
    assert restored["y"] == 80
    assert as_user("asha").get("/me/whiteboard").json()["objects"] == []


def test_offline_snapshot_uses_requested_font_and_size():
    images = []
    for family, size in [("sans", 16), ("handwritten", 32), ("mono", 24)]:
        objects = {
            "note": {
                "kind": "text",
                "data": {
                    "x": 10,
                    "y": 10,
                    "text": "Stress and strain",
                    "color": "#1f2933",
                    "font_family": family,
                    "font_size": size,
                },
                "alive": True,
            }
        }
        images.append(render_png(objects, (0, 0, 400, 150), lambda _: None))
    assert len(set(images)) == 3
    assert all(image.startswith(b"\x89PNG") for image in images)
