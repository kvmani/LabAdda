"""Single-process realtime fanout over WebSockets (S4).

Durable writes happen through the JSON API. After commit, routers call
``Hub.publish`` and the hub delivers to subscribers, rechecking each
recipient's current access first. Membership and identity changes call
``revalidate_*`` so stale subscriptions close with a revocation signal.
Clients catch up from committed state over the API after (re)subscribing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field

from fastapi import WebSocket

from . import policy
from .config import Settings
from .deps import origin_allowed
from .models import AuthSession, User
from .security import digest, session_valid

log = logging.getLogger("labadda.realtime")
MAX_PREVIEW_BYTES = 16_000
MAX_MESSAGE_BYTES = 32_000


@dataclass(eq=False)
class Connection:
    ws: WebSocket
    user_id: uuid.UUID
    session_id: str
    display_name: str
    subscriptions: set[uuid.UUID] = field(default_factory=set)
    writable: set[uuid.UUID] = field(default_factory=set)


class Hub:
    def __init__(self, factory, settings: Settings):
        self.factory = factory
        self.settings = settings
        self.connections: set[Connection] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    # ---- thread-safe entry points used by sync routers -----------------
    def _schedule(self, coro_fn, *args) -> None:
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(coro_fn(*args))
        else:
            asyncio.run_coroutine_threadsafe(coro_fn(*args), loop)

    def publish(self, workspace_id: uuid.UUID, event: dict) -> None:
        self._schedule(self._deliver, workspace_id, event)

    def revalidate_user(self, user_id: uuid.UUID) -> None:
        self._schedule(self._revalidate, lambda c: c.user_id == user_id)

    def revalidate_workspace(self, workspace_id: uuid.UUID) -> None:
        self._schedule(self._revalidate, lambda c: workspace_id in c.subscriptions)

    def revalidate_all(self) -> None:
        self._schedule(self._revalidate, lambda c: True)

    # ---- access checks run in a worker thread --------------------------
    def _check(self, conn: Connection, workspace_ids: set[uuid.UUID]):
        """Return (session_ok, readable subset, writable subset)."""
        with self.factory() as db:
            sess = db.get(AuthSession, conn.session_id)
            user = db.get(User, conn.user_id)
            if sess is None or user is None or not user.is_active or not session_valid(sess, self.settings):
                return False, set(), set()
            readable, writable = set(), set()
            for ws_id in workspace_ids:
                access = policy.resolve(db, user, ws_id)
                if access is not None:
                    readable.add(ws_id)
                    if access.can_write:
                        writable.add(ws_id)
            return True, readable, writable

    async def _send(self, conn: Connection, payload: dict) -> None:
        try:
            await conn.ws.send_text(json.dumps(payload))
        except Exception:
            self.connections.discard(conn)

    async def _deliver(self, workspace_id: uuid.UUID, event: dict) -> None:
        targets = [c for c in list(self.connections) if workspace_id in c.subscriptions]
        for conn in targets:
            ok, readable, writable = await asyncio.to_thread(self._check, conn, {workspace_id})
            if not ok:
                await self._close(conn, "session_ended")
                continue
            if workspace_id not in readable:
                await self._drop(conn, workspace_id)
                continue
            conn.writable = (conn.writable - {workspace_id}) | writable
            await self._send(conn, event)

    async def _drop(self, conn: Connection, workspace_id: uuid.UUID) -> None:
        conn.subscriptions.discard(workspace_id)
        conn.writable.discard(workspace_id)
        await self._send(conn, {"type": "revoked", "workspace_id": str(workspace_id)})
        await self._presence(workspace_id)

    async def _close(self, conn: Connection, reason: str) -> None:
        subs = set(conn.subscriptions)
        self.connections.discard(conn)
        try:
            await conn.ws.send_text(json.dumps({"type": "session_ended", "reason": reason}))
            await conn.ws.close(code=4401)
        except Exception:
            pass
        for ws_id in subs:
            await self._presence(ws_id)

    async def _revalidate(self, predicate) -> None:
        for conn in [c for c in list(self.connections) if predicate(c)]:
            ok, readable, writable = await asyncio.to_thread(self._check, conn, set(conn.subscriptions))
            if not ok:
                await self._close(conn, "session_ended")
                continue
            for ws_id in set(conn.subscriptions) - readable:
                await self._drop(conn, ws_id)
            conn.writable = writable
            await self._send(conn, {"type": "access_changed"})

    async def _presence(self, workspace_id: uuid.UUID) -> None:
        present = {}
        for c in self.connections:
            if workspace_id in c.subscriptions:
                present[str(c.user_id)] = c.display_name
        payload = {"type": "presence", "workspace_id": str(workspace_id),
                   "users": [{"id": k, "display_name": v} for k, v in sorted(present.items(), key=lambda kv: kv[1])]}
        for c in [c for c in list(self.connections) if workspace_id in c.subscriptions]:
            await self._send(c, payload)

    # ---- socket endpoint ------------------------------------------------
    def _authenticate(self, token: str | None):
        if not token:
            return None
        with self.factory() as db:
            sess = db.get(AuthSession, digest(token))
            if sess is None or sess.kind != "normal" or not session_valid(sess, self.settings):
                return None
            user = db.get(User, sess.user_id)
            if user is None or not user.is_active:
                return None
            return sess.id, user.id, user.display_name

    async def serve(self, ws: WebSocket) -> None:
        self.loop = asyncio.get_running_loop()
        host = ws.headers.get("host")
        if not origin_allowed(ws.headers.get("origin"), host, self.settings):
            await ws.close(code=4403)
            return
        ident = await asyncio.to_thread(self._authenticate, ws.cookies.get(self.settings.cookie_name))
        if ident is None:
            await ws.close(code=4401)
            return
        await ws.accept()
        conn = Connection(ws=ws, session_id=ident[0], user_id=ident[1], display_name=ident[2])
        self.connections.add(conn)
        await self._send(conn, {"type": "hello"})
        try:
            while True:
                raw = await ws.receive_text()
                if len(raw) > MAX_MESSAGE_BYTES:
                    await self._send(conn, {"type": "error", "code": "too_large"})
                    continue
                try:
                    msg = json.loads(raw)
                    await self._handle(conn, msg)
                except (ValueError, KeyError, TypeError):
                    await self._send(conn, {"type": "error", "code": "bad_message"})
        except Exception:
            pass
        finally:
            self.connections.discard(conn)
            for ws_id in set(conn.subscriptions):
                await self._presence(ws_id)

    async def _handle(self, conn: Connection, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "ping":
            await self._send(conn, {"type": "pong"})
            return
        ws_id = uuid.UUID(str(msg["workspace_id"]))
        if kind == "subscribe":
            ok, readable, writable = await asyncio.to_thread(self._check, conn, {ws_id})
            if not ok:
                await self._close(conn, "session_ended")
                return
            if ws_id not in readable:
                # Same answer for unknown and out-of-scope IDs.
                await self._send(conn, {"type": "subscribe_failed", "workspace_id": str(ws_id)})
                return
            conn.subscriptions.add(ws_id)
            conn.writable = (conn.writable - {ws_id}) | writable
            await self._send(conn, {"type": "subscribed", "workspace_id": str(ws_id)})
            await self._presence(ws_id)
        elif kind == "unsubscribe":
            conn.subscriptions.discard(ws_id)
            conn.writable.discard(ws_id)
            await self._presence(ws_id)
        elif kind == "board.preview":
            # Transient stroke preview: bounded, never stored, only from writers.
            if ws_id not in conn.writable or len(json.dumps(msg.get("stroke", {}))) > MAX_PREVIEW_BYTES:
                return
            event = {"type": "board.preview", "workspace_id": str(ws_id), "actor_id": str(conn.user_id),
                     "stroke": msg.get("stroke"), "preview_id": str(msg.get("preview_id", ""))[:64],
                     "done": bool(msg.get("done"))}
            for other in [c for c in list(self.connections) if ws_id in c.subscriptions and c is not conn]:
                await self._send(other, event)
