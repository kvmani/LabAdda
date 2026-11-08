"""T10 (subset): socket auth, scoped subscription, live delivery and revocation."""

from contextlib import ExitStack, contextmanager

import pytest
from fastapi.testclient import TestClient
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



@contextmanager
def shared_loop_sockets(app, settings, apis, workspace_id):
    """Open one socket per signed-in client through a single TestClient portal (one event loop, as in
    production under uvicorn) and subscribe each to ``workspace_id``."""
    with TestClient(app) as tc, ExitStack() as stack:
        socks = []
        for api in apis:
            cookie = f"{settings.cookie_name}={api.client.cookies.get(settings.cookie_name)}"
            sock = stack.enter_context(tc.websocket_connect(ws_url(settings), headers={"cookie": cookie}))
            sock.receive_json()
            sock.send_json({"type": "subscribe", "workspace_id": workspace_id})
            recv_until(sock, "subscribed")
            socks.append(sock)
        yield socks


def test_fanout_is_ordered_and_complete_for_every_subscriber(as_user, ids, settings, app):
    """A burst of events reaches every subscriber, in commit order, through one batched recheck."""
    a = ids["workspaces"]["section_a"]
    with shared_loop_sockets(app, settings, [as_user("ben"), as_user("asha")], a) as socks:
        for i in range(60):
            app.state.hub.publish(a, {"type": "chat.message",
                                      "message": {"workspace_id": a, "seq": i, "client_id": f"burst-{i}"}})
        for sock in socks:
            seqs = []
            while len(seqs) < 60:
                msg = sock.receive_json()
                if msg["type"] == "chat.message":
                    seqs.append(msg["message"]["seq"])
            assert seqs == list(range(60))


def test_batched_recheck_drops_only_the_revoked_subscriber(as_user, ids, settings, app):
    a = ids["workspaces"]["section_a"]
    with shared_loop_sockets(app, settings, [as_user("ben"), as_user("asha")], a) as (ben_ws, asha_ws):
        # Remove access directly in the database, bypassing the hub's revalidation signal:
        # the per-delivery recheck alone must stop delivery.
        from sqlalchemy import text
        with app.state.session_factory() as db:
            db.execute(text("delete from memberships where user_id = :u and workspace_id = :w"),
                       {"u": ids["users"]["ben"], "w": a})
            db.commit()
        app.state.hub.publish(a, {"type": "chat.message", "message": {"workspace_id": a, "client_id": "after"}})
        assert recv_until(ben_ws, "revoked")["workspace_id"] == a
        assert recv_until(asha_ws, "chat.message")["message"]["client_id"] == "after"
        ben_ws.send_json({"type": "ping"})
        for _ in range(5):
            msg = ben_ws.receive_json()
            assert msg["type"] != "chat.message"
            if msg["type"] == "pong":
                break


def test_stalled_client_is_closed_without_blocking_others(as_user, ids, settings, app, monkeypatch):
    import asyncio

    from labadda import realtime
    a = ids["workspaces"]["section_a"]
    monkeypatch.setattr(realtime, "SEND_TIMEOUT_SECONDS", 0.2)
    with shared_loop_sockets(app, settings, [as_user("ben"), as_user("asha")], a) as (_ben_ws, asha_ws):
        hub = app.state.hub
        ben_conn = next(c for c in hub.connections if str(c.user_id) == ids["users"]["ben"])
        original = hub._send

        async def stalled(conn, payload):
            if conn is ben_conn and payload.get("type") == "chat.message":
                await asyncio.sleep(5)  # simulates a client whose socket buffer never drains
            await original(conn, payload)

        monkeypatch.setattr(hub, "_send", stalled)
        import time
        started = time.monotonic()
        hub.publish(a, {"type": "chat.message", "message": {"workspace_id": a, "client_id": "one"}})
        hub.publish(a, {"type": "chat.message", "message": {"workspace_id": a, "client_id": "two"}})
        assert recv_until(asha_ws, "chat.message")["message"]["client_id"] == "one"
        assert recv_until(asha_ws, "chat.message")["message"]["client_id"] == "two"
        assert time.monotonic() - started < 3  # not held for the stalled client's 5 s
        deadline = time.monotonic() + 3
        while ben_conn in hub.connections and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ben_conn not in hub.connections  # the stalled client was closed, not waited on
