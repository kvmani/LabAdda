"""T10 (subset): socket auth, scoped subscription, live delivery and revocation."""

import pytest
from starlette.websockets import WebSocketDisconnect


def ws_url(settings):
    return f"{settings.base_path}/ws/"


def recv_until(conn, kind, limit=10):
    for _ in range(limit):
        msg = conn.receive_json()
        if msg["type"] == kind:
            return msg
    raise AssertionError(f"no {kind}")


def test_unauthenticated_socket_rejected(make_client, settings):
    api = make_client()
    with pytest.raises(WebSocketDisconnect):
        with api.client.websocket_connect(ws_url(settings)) as conn:
            conn.receive_json()


def test_bad_origin_rejected(as_user, settings):
    with pytest.raises(WebSocketDisconnect):
        with as_user("ben").client.websocket_connect(ws_url(settings), headers={"origin": "http://evil.example"}) as c:
            c.receive_json()


def test_subscribe_scope_and_live_chat(as_user, ids, settings):
    ben, asha = as_user("ben"), as_user("asha")
    a = ids["workspaces"]["section_a"]
    with ben.client.websocket_connect(ws_url(settings)) as conn:
        assert conn.receive_json()["type"] == "hello"
        conn.send_json({"type": "subscribe", "workspace_id": ids["workspaces"]["section_b"]})
        assert conn.receive_json()["type"] == "subscribe_failed"
        conn.send_json({"type": "subscribe", "workspace_id": a})
        assert recv_until(conn, "subscribed")["workspace_id"] == a
        asha.post(f"/workspaces/{a}/chat", json={"body": "live hello", "client_id": "live-0001"})
        msg = recv_until(conn, "chat.message")
        assert msg["message"]["body"] == "live hello"


def test_membership_removal_revokes_subscription(as_user, ids, settings):
    ben, asha = as_user("ben"), as_user("asha")
    a = ids["workspaces"]["section_a"]
    with ben.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": a})
        recv_until(conn, "subscribed")
        as_user("admin").delete(f"/admin/workspaces/{a}/memberships/{ids['users']['ben']}")
        assert recv_until(conn, "revoked")["workspace_id"] == a
        asha.post(f"/workspaces/{a}/chat", json={"body": "after removal", "client_id": "live-0002"})
        conn.send_json({"type": "ping"})
        for _ in range(5):
            m = conn.receive_json()
            assert m["type"] != "chat.message"
            if m["type"] == "pong":
                break


def test_deactivation_ends_socket(as_user, ids, settings):
    ben = as_user("ben")
    with ben.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": ids["workspaces"]["section_a"]})
        recv_until(conn, "subscribed")
        as_user("admin").patch(f"/admin/users/{ids['users']['ben']}", json={"is_active": False})
        assert recv_until(conn, "session_ended")


def test_board_preview_relay(as_user, ids, settings):
    a = ids["workspaces"]["section_a"]
    with as_user("ben").client.websocket_connect(ws_url(settings)) as b, \
            as_user("asha").client.websocket_connect(ws_url(settings)) as s:
        for c in (b, s):
            c.receive_json()
            c.send_json({"type": "subscribe", "workspace_id": a})
            recv_until(c, "subscribed")
        b.send_json({"type": "board.preview", "workspace_id": a, "preview_id": "p1", "stroke": {"points": [[1, 2]]}})
        msg = recv_until(s, "board.preview")
        assert msg["stroke"]["points"] == [[1, 2]]
