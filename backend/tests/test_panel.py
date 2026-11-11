"""T11 (API and socket): board-only touch-panel sessions."""

from dataclasses import replace
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from labadda.models import AuthSession, PanelPairing
from labadda.security import utcnow

PANEL = {"X-LabAdda-Panel": "1"}


def ws(ids, key="section_a"):
    return ids["workspaces"][key]


class Panel:
    """A kiosk browser context: only the panel cookie, panel header on every request."""

    def __init__(self, api, data):
        self.api, self.csrf = api, data["csrf_token"]
        self.data = data

    def get(self, path, **kw):
        return self.api.client.get(self.api.url(path), headers=PANEL, **kw)

    def post(self, path, json=None):
        return self.api.client.post(
            self.api.url(path), json=json, headers={**PANEL, "X-CSRF-Token": self.csrf}
        )


def pair(as_user, make_client, ids, user="ben", key="section_a"):
    code = as_user(user).post("/panel/pairings", json={"workspace_id": ws(ids, key)})
    assert code.status_code == 201, code.text
    kiosk = make_client()
    r = kiosk.client.post(kiosk.url("/panel/claim"), json={"code": code.json()["code"]})
    assert r.status_code == 200, r.text
    return Panel(kiosk, r.json())


def stroke(op_id, obj):
    return {
        "op_id": op_id,
        "epoch": 1,
        "type": "add",
        "object_id": obj,
        "payload": {"kind": "stroke", "data": {"points": [[0, 0], [5, 5]], "color": "#1f2933", "width": 3}},
    }


def test_pairing_requires_access_and_is_single_use(as_user, make_client, ids):
    assert as_user("chen").post("/panel/pairings", json={"workspace_id": ws(ids)}).status_code == 404
    assert as_user("admin").post("/panel/pairings", json={"workspace_id": ws(ids)}).status_code == 404
    assert make_client().post("/panel/pairings", json={"workspace_id": ws(ids)}).status_code == 401
    code = as_user("ben").post("/panel/pairings", json={"workspace_id": ws(ids)}).json()["code"]
    k1, k2 = make_client(), make_client()
    assert (
        k1.client.post(k1.url("/panel/claim"), json={"code": code.lower().replace("-", " ")}).status_code
        == 200
    )
    again = k2.client.post(k2.url("/panel/claim"), json={"code": code})
    assert again.status_code == 422 and again.json()["error"]["code"] == "code_invalid"


def test_expired_code_and_rate_limit(as_user, make_client, ids, db_factory):
    code = as_user("ben").post("/panel/pairings", json={"workspace_id": ws(ids)}).json()["code"]
    with db_factory() as db:
        for p in db.query(PanelPairing).all():
            p.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    kiosk = make_client()
    assert kiosk.client.post(kiosk.url("/panel/claim"), json={"code": code}).status_code == 422
    codes = [
        kiosk.client.post(kiosk.url("/panel/claim"), json={"code": "WRONG-CODE"}).status_code
        for _ in range(12)
    ]
    assert codes[-1] == 429


def test_panel_uses_its_board_only(as_user, make_client, ids):
    panel = pair(as_user, make_client, ids)
    assert panel.data["workspace"]["name"] == "Thin Films Section"
    assert panel.get("/panel/session").status_code == 200
    board = panel.get(f"/workspaces/{ws(ids)}/board")
    assert board.status_code == 200 and board.json()["can_moderate"] is False
    op = panel.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke("op-panel-01", "p1"))
    assert op.status_code == 200
    # Attribution and own-undo belong to the person who paired the panel.
    assert op.json()["committed"]["actor_id"] == ids["users"]["ben"]
    assert (
        panel.post(
            f"/workspaces/{ws(ids)}/board/ops", json={"op_id": "op-panel-u1", "epoch": 1, "type": "undo"}
        ).status_code
        == 200
    )
    # Same user's other board (division) is out of scope for this panel.
    assert panel.get(f"/workspaces/{ws(ids, 'division')}/board").status_code == 404
    assert (
        panel.post(
            f"/workspaces/{ws(ids, 'division')}/board/ops", json=stroke("op-panel-02", "p2")
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/workspaces"),
        ("get", "/auth/session"),
        ("get", "/notes"),
        ("get", "/notifications"),
        ("get", "/admin/users"),
        ("get", "/directory"),
        ("get", "/workspaces/{ws}/posts"),
        ("get", "/workspaces/{ws}/chat"),
        ("get", "/workspaces/{ws}/search?q=ab"),
        ("get", "/workspaces/{ws}/members"),
        ("get", "/workspaces/{ws}/board/render?revision=0&x=0&y=0&w=10&h=10"),
        ("get", "/workspaces/{ws}/board/snapshot-destinations"),
        ("post", "/workspaces/{ws}/posts"),
        ("post", "/workspaces/{ws}/chat"),
        ("post", "/uploads"),
        ("post", "/workspaces/{ws}/board/restore"),
        ("post", "/workspaces/{ws}/board/snapshots"),
        ("post", "/groups"),
    ],
)
def test_panel_cookie_reaches_nothing_else(as_user, make_client, ids, method, path):
    panel = pair(as_user, make_client, ids, user="asha")  # asha is a steward: still no moderation on a panel
    url = path.replace("{ws}", ws(ids))
    # With and without the panel header the kiosk cookie never acts as a normal session.
    for headers in (PANEL, {}):
        r = getattr(panel.api.client, method)(
            panel.api.url(url),
            headers={**headers, "X-CSRF-Token": panel.csrf},
            **({"json": {}} if method == "post" else {}),
        )
        assert r.status_code == 401, (url, r.status_code, r.text)


def test_panel_images_only_from_its_board(as_user, make_client, ids):
    from .test_files import PDF, png_bytes

    ben = as_user("ben")
    board_img = ben.post("/uploads", files={"file": ("a.png", png_bytes(), "image/png")}).json()["id"]
    ben.post(
        f"/workspaces/{ws(ids)}/board/ops",
        json={
            "op_id": "op-ben-img1",
            "epoch": 1,
            "type": "add",
            "object_id": "img",
            "payload": {"kind": "image", "data": {"x": 0, "y": 0, "w": 10, "h": 10, "asset_id": board_img}},
        },
    )
    post_file = ben.post("/uploads", files={"file": ("a.pdf", PDF, "application/pdf")}).json()["id"]
    ben.post(f"/workspaces/{ws(ids)}/posts", json={"body": "file", "attachment_ids": [post_file]})
    panel = pair(as_user, make_client, ids)
    assert panel.get(f"/files/{board_img}/preview").status_code == 200
    assert panel.get(f"/files/{post_file}").status_code == 404
    # No file picker on the panel: placing images is refused.
    r = panel.post(
        f"/workspaces/{ws(ids)}/board/ops",
        json={
            "op_id": "op-panel-img",
            "epoch": 1,
            "type": "add",
            "object_id": "img2",
            "payload": {"kind": "image", "data": {"x": 0, "y": 0, "w": 10, "h": 10, "asset_id": board_img}},
        },
    )
    assert r.status_code == 403


def test_idle_lock_absolute_expiry_and_activity(as_user, make_client, ids, db_factory, app):
    app.state.settings = replace(app.state.settings, panel_idle_seconds=60)
    panel = pair(as_user, make_client, ids)
    with db_factory() as db:
        for s in db.query(AuthSession).filter(AuthSession.kind == "board"):
            s.last_seen_at = utcnow() - timedelta(seconds=50)
        db.commit()
    # Reads do not keep a panel alive; an interaction does.
    assert panel.get(f"/workspaces/{ws(ids)}/board").status_code == 200
    assert panel.post("/panel/activity").status_code == 200
    with db_factory() as db:
        s = db.query(AuthSession).filter(AuthSession.kind == "board").one()
        assert utcnow() - s.last_seen_at < timedelta(seconds=5)
        s.last_seen_at = utcnow() - timedelta(seconds=61)
        db.commit()
    assert panel.get(f"/workspaces/{ws(ids)}/board").status_code == 401
    second = pair(as_user, make_client, ids)
    with db_factory() as db:
        for s in db.query(AuthSession).filter(AuthSession.kind == "board", AuthSession.revoked_at.is_(None)):
            s.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert second.get("/panel/session").status_code == 401


def test_end_and_lock_are_audited(as_user, make_client, ids):
    panel = pair(as_user, make_client, ids)
    assert panel.post("/panel/end", json={"reason": "idle_lock"}).status_code == 200
    assert panel.get(f"/workspaces/{ws(ids)}/board").status_code == 401
    other = pair(as_user, make_client, ids)
    assert other.post("/panel/end", json={}).status_code == 200
    events = as_user("admin").get("/admin/audit").json()["events"]
    actions = [e["action"] for e in events]
    assert {"panel.pairing_created", "panel.start", "panel.lock", "panel.end"} <= set(actions)
    # Desktop session of the same user is unaffected.
    assert as_user("ben").get("/auth/session").status_code == 200


def test_access_changes_apply_to_panel(as_user, make_client, ids):
    panel = pair(as_user, make_client, ids)
    as_user("admin").delete(f"/admin/workspaces/{ws(ids)}/memberships/{ids['users']['ben']}")
    assert panel.get(f"/workspaces/{ws(ids)}/board").status_code == 404
    panel2 = pair(as_user, make_client, ids, user="asha")
    as_user("admin").patch(f"/admin/users/{ids['users']['asha']}", json={"is_active": False})
    assert panel2.get(f"/workspaces/{ws(ids)}/board").status_code == 401


def test_archive_freezes_panel_drawing(as_user, make_client, ids):
    panel = pair(as_user, make_client, ids)
    as_user("admin").patch(f"/admin/workspaces/{ws(ids)}", json={"archived": True})
    r = panel.post(f"/workspaces/{ws(ids)}/board/ops", json=stroke("op-panel-03", "p3"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "workspace_archived"


def test_panel_socket_gets_board_events_only(as_user, make_client, ids, settings):
    panel = pair(as_user, make_client, ids)
    a = ws(ids)
    with pytest.raises(WebSocketDisconnect):  # without the panel flag the kiosk has no normal session
        with panel.api.client.websocket_connect(f"{settings.base_path}/ws/") as c:
            c.receive_json()
    with panel.api.client.websocket_connect(f"{settings.base_path}/ws/?panel=1") as conn:
        assert conn.receive_json()["type"] == "hello"
        conn.send_json({"type": "subscribe", "workspace_id": ws(ids, "division")})
        assert conn.receive_json()["type"] == "subscribe_failed"
        conn.send_json({"type": "subscribe", "workspace_id": a})
        while conn.receive_json()["type"] != "subscribed":
            pass
        asha = as_user("asha")
        asha.post(f"/workspaces/{a}/chat", json={"body": "private chat", "client_id": "chat-panel-1"})
        asha.post(f"/workspaces/{a}/posts", json={"body": "feed item"})
        from tests.test_task_assignment import task

        task(asha, a)
        asha.post(f"/workspaces/{a}/board/ops", json=stroke("op-ash-p01", "a1"))
        seen = []
        while True:
            msg = conn.receive_json()
            seen.append(msg["type"])
            if msg["type"] == "board.op":
                break
        assert (
            "chat.message" not in seen and "noticeboard.changed" not in seen and "tasks.changed" not in seen
        )
        panel.post("/panel/end", json={})
        while conn.receive_json()["type"] != "session_ended":
            pass
