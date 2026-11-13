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
    with pytest.raises(WebSocketDisconnect), api.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()


def test_bad_origin_rejected(as_user, settings):
    with (
        pytest.raises(WebSocketDisconnect),
        as_user("bharat").client.websocket_connect(
            ws_url(settings), headers={"origin": "http://evil.example"}
        ) as c,
    ):
        c.receive_json()


def test_subscribe_scope_and_live_chat(as_user, ids, settings):
    bharat, asha = as_user("bharat"), as_user("asha")
    a = ids["workspaces"]["section_a"]
    with bharat.client.websocket_connect(ws_url(settings)) as conn:
        assert conn.receive_json()["type"] == "hello"
        conn.send_json({"type": "subscribe", "workspace_id": ids["workspaces"]["section_b"]})
        assert conn.receive_json()["type"] == "subscribe_failed"
        conn.send_json({"type": "subscribe", "workspace_id": a})
        assert recv_until(conn, "subscribed")["workspace_id"] == a
        asha.post(f"/workspaces/{a}/chat", json={"body": "live hello", "client_id": "live-0001"})
        msg = recv_until(conn, "chat.message")
        assert msg["message"]["body"] == "live hello"


def test_membership_removal_revokes_subscription(as_user, ids, settings):
    bharat, asha = as_user("bharat"), as_user("asha")
    a = ids["workspaces"]["section_a"]
    with bharat.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": a})
        recv_until(conn, "subscribed")
        as_user("admin").delete(f"/admin/workspaces/{a}/memberships/{ids['users']['bharat']}")
        assert recv_until(conn, "revoked")["workspace_id"] == a
        asha.post(f"/workspaces/{a}/chat", json={"body": "after removal", "client_id": "live-0002"})
        conn.send_json({"type": "ping"})
        for _ in range(5):
            m = conn.receive_json()
            assert m["type"] != "chat.message"
            if m["type"] == "pong":
                break


def test_deactivation_ends_socket(as_user, ids, settings):
    bharat = as_user("bharat")
    with bharat.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": ids["workspaces"]["section_a"]})
        recv_until(conn, "subscribed")
        as_user("admin").patch(f"/admin/users/{ids['users']['bharat']}", json={"is_active": False})
        assert recv_until(conn, "session_ended")


def test_board_preview_relay(as_user, ids, settings):
    a = ids["workspaces"]["section_a"]
    with (
        as_user("bharat").client.websocket_connect(ws_url(settings)) as b,
        as_user("asha").client.websocket_connect(ws_url(settings)) as s,
    ):
        for c in (b, s):
            c.receive_json()
            c.send_json({"type": "subscribe", "workspace_id": a})
            recv_until(c, "subscribed")
        b.send_json(
            {"type": "board.preview", "workspace_id": a, "preview_id": "p1", "stroke": {"points": [[1, 2]]}}
        )
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
    with shared_loop_sockets(app, settings, [as_user("bharat"), as_user("asha")], a) as socks:
        for i in range(60):
            app.state.hub.publish(
                a,
                {"type": "chat.message", "message": {"workspace_id": a, "seq": i, "client_id": f"burst-{i}"}},
            )
        for sock in socks:
            seqs = []
            while len(seqs) < 60:
                msg = sock.receive_json()
                if msg["type"] == "chat.message":
                    seqs.append(msg["message"]["seq"])
            assert seqs == list(range(60))


def test_batched_recheck_drops_only_the_revoked_subscriber(as_user, ids, settings, app):
    a = ids["workspaces"]["section_a"]
    with shared_loop_sockets(app, settings, [as_user("bharat"), as_user("asha")], a) as (bharat_ws, asha_ws):
        # Remove access directly in the database, bypassing the hub's revalidation signal:
        # the per-delivery recheck alone must stop delivery.
        from sqlalchemy import text

        with app.state.session_factory() as db:
            db.execute(
                text("delete from memberships where user_id = :u and workspace_id = :w"),
                {"u": ids["users"]["bharat"], "w": a},
            )
            db.commit()
        app.state.hub.publish(
            a, {"type": "chat.message", "message": {"workspace_id": a, "client_id": "after"}}
        )
        assert recv_until(bharat_ws, "revoked")["workspace_id"] == a
        assert recv_until(asha_ws, "chat.message")["message"]["client_id"] == "after"
        bharat_ws.send_json({"type": "ping"})
        for _ in range(5):
            msg = bharat_ws.receive_json()
            assert msg["type"] != "chat.message"
            if msg["type"] == "pong":
                break


def test_stalled_client_is_closed_without_blocking_others(as_user, ids, settings, app, monkeypatch):
    import asyncio

    from labadda import realtime

    a = ids["workspaces"]["section_a"]
    monkeypatch.setattr(realtime, "SEND_TIMEOUT_SECONDS", 0.2)
    with shared_loop_sockets(app, settings, [as_user("bharat"), as_user("asha")], a) as (_bharat_ws, asha_ws):
        hub = app.state.hub
        bharat_conn = next(c for c in hub.connections if str(c.user_id) == ids["users"]["bharat"])
        original = hub._send

        async def stalled(conn, payload, **kwargs):
            if conn is bharat_conn and payload.get("type") == "chat.message":
                await asyncio.sleep(5)  # simulates a client whose socket buffer never drains
            await original(conn, payload, **kwargs)

        monkeypatch.setattr(hub, "_send", stalled)
        import time

        started = time.monotonic()
        hub.publish(a, {"type": "chat.message", "message": {"workspace_id": a, "client_id": "one"}})
        hub.publish(a, {"type": "chat.message", "message": {"workspace_id": a, "client_id": "two"}})
        assert recv_until(asha_ws, "chat.message")["message"]["client_id"] == "one"
        assert recv_until(asha_ws, "chat.message")["message"]["client_id"] == "two"
        assert time.monotonic() - started < 3  # not held for the stalled client's 5 s
        deadline = time.monotonic() + 3
        while bharat_conn in hub.connections and time.monotonic() < deadline:
            time.sleep(0.05)
        assert bharat_conn not in hub.connections  # the stalled client was closed, not waited on


def test_revocation_during_batch_stops_remaining_content(settings, monkeypatch):
    import asyncio
    import json
    import uuid

    from labadda.realtime import Connection, Hub

    async def scenario():
        workspace = uuid.uuid4()
        started, release = asyncio.Event(), asyncio.Event()
        frames = []

        class Socket:
            async def send_text(self, raw):
                message = json.loads(raw)
                if message.get("seq") == 1:
                    started.set()
                    await release.wait()
                frames.append(message)

        hub = Hub(None, settings)
        conn = Connection(Socket(), uuid.uuid4(), "session", "Synthetic", {workspace})
        hub.connections.add(conn)
        monkeypatch.setattr(hub, "_check_many", lambda *_: {conn: (True, True, True)})
        delivery = asyncio.create_task(
            hub._deliver(workspace, [{"type": "chat.message", "seq": 1}, {"type": "chat.message", "seq": 2}])
        )
        await asyncio.wait_for(started.wait(), 1)
        dropped = asyncio.create_task(hub._drop(conn, workspace))
        await asyncio.sleep(0)  # run invalidation up to its first awaited socket operation
        assert workspace not in conn.subscriptions
        release.set()
        await asyncio.wait_for(asyncio.gather(delivery, dropped), 1)
        assert not any(frame.get("seq") == 2 for frame in frames)
        revoked = next(i for i, frame in enumerate(frames) if frame["type"] == "revoked")
        assert not any(frame["type"] == "chat.message" for frame in frames[revoked + 1 :])

    asyncio.run(scenario())


def test_stalled_revocation_control_does_not_block_healthy_delivery(settings, monkeypatch):
    import asyncio
    import json
    import uuid

    from labadda import realtime

    async def scenario():
        workspace = uuid.uuid4()
        received = asyncio.Event()

        class Stalled:
            async def send_text(self, raw):
                await asyncio.Event().wait()

            async def close(self, **kwargs):
                await asyncio.Event().wait()

        class Healthy:
            async def send_text(self, raw):
                if json.loads(raw)["type"] == "chat.message":
                    received.set()

        hub = realtime.Hub(None, settings)
        bad = realtime.Connection(Stalled(), uuid.uuid4(), "bad", "Synthetic", {workspace})
        good = realtime.Connection(Healthy(), uuid.uuid4(), "good", "Synthetic", {workspace})
        hub.connections.update([bad, good])
        monkeypatch.setattr(realtime, "SEND_TIMEOUT_SECONDS", 0.05)
        monkeypatch.setattr(
            hub, "_check_many", lambda *_: {bad: (False, False, False), good: (True, True, True)}
        )
        task = asyncio.create_task(hub._deliver(workspace, [{"type": "chat.message"}]))
        await asyncio.wait_for(received.wait(), 0.5)
        await asyncio.wait_for(task, 0.5)
        assert bad not in hub.connections and good in hub.connections

    asyncio.run(scenario())


@pytest.mark.parametrize("regrant", [False, True])
@pytest.mark.parametrize("check_kind", ["batch", "revalidation"])
def test_stale_batch_decision_cannot_restore_write_or_drop_new_subscription(
    settings, monkeypatch, regrant, check_kind
):
    import asyncio
    import threading
    import uuid

    from labadda.realtime import Connection, Hub

    async def scenario():
        workspace = uuid.uuid4()
        started, release = threading.Event(), threading.Event()

        class Socket:
            async def send_text(self, raw):
                pass

        hub = Hub(None, settings)
        conn = Connection(Socket(), uuid.uuid4(), "session", "Synthetic", {workspace}, {workspace})
        hub.connections.add(conn)

        def paused_check(*_):
            started.set()
            assert release.wait(2)
            if check_kind == "batch":
                return {conn: (True, not regrant, not regrant)}
            allowed = set() if regrant else {workspace}
            return True, allowed, allowed

        monkeypatch.setattr(hub, "_check_many" if check_kind == "batch" else "_check", paused_check)
        task = asyncio.create_task(
            hub._deliver(workspace, [{"type": "board.op"}])
            if check_kind == "batch"
            else hub._revalidate(lambda c: True)
        )
        try:
            assert await asyncio.to_thread(started.wait, 1)
            await hub._drop(conn, workspace)
            if regrant:
                monkeypatch.setattr(hub, "_check", lambda *_: (True, {workspace}, {workspace}))
                # New presence checks see the regrant; the already-running batch retains its stale result.
                monkeypatch.setattr(
                    hub, "_check_many", lambda conns, _ws: dict.fromkeys(conns, (True, True, True))
                )
                await hub._handle(conn, {"type": "subscribe", "workspace_id": str(workspace)})
        finally:
            release.set()
        await asyncio.wait_for(task, 1)
        assert (workspace in conn.subscriptions) is regrant
        assert (workspace in conn.writable) is regrant

    asyncio.run(scenario())


def test_batch_timeout_does_not_cancel_transport_cleanup(settings, monkeypatch):
    import asyncio
    import json
    import uuid

    from labadda import realtime

    async def scenario():
        workspace = uuid.uuid4()
        closed = asyncio.Event()

        class Socket:
            async def send_text(self, raw):
                if json.loads(raw)["type"] == "chat.message":
                    raise OSError("synthetic failed transport")
                await asyncio.Event().wait()

            async def close(self, **kwargs):
                closed.set()

        hub = realtime.Hub(None, settings)
        conn = realtime.Connection(Socket(), uuid.uuid4(), "session", "Synthetic", {workspace})
        hub.connections.add(conn)
        monkeypatch.setattr(realtime, "SEND_TIMEOUT_SECONDS", 0.05)
        await hub._send_all(conn, workspace, [{"type": "chat.message"}], 0)
        await asyncio.wait_for(closed.wait(), 0.5)
        assert conn not in hub.connections

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["logout", "password", "activate"])
def test_auth_revocation_closes_existing_socket(as_user, ids, settings, app, action):
    from labadda.credentials import issue_credential
    from labadda.models import User

    bharat = as_user("bharat")
    with shared_loop_sockets(app, settings, [bharat], ids["workspaces"]["section_a"]) as (sock,):
        if action == "activate":
            with app.state.session_factory() as db:
                user = db.get(User, ids["users"]["bharat"])
                token, _credential = issue_credential(db, user, "reset", None, settings)
                db.commit()
            response = bharat.post(
                "/auth/activate", json={"token": token, "password": "new-fixture-pass-123"}
            )
        elif action == "password":
            response = bharat.post(
                "/auth/password",
                json={"current_password": "fixture-pass-123", "new_password": "new-fixture-pass-123"},
            )
        else:
            response = bharat.post("/auth/logout")
        assert response.status_code == 200
        assert recv_until(sock, "session_ended")["reason"] == "session_ended"
