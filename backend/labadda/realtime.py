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
from sqlalchemy import select

from . import policy
from .config import Settings
from .deps import origin_allowed
from .models import AuthSession, User, Workspace
from .security import digest, session_valid

log = logging.getLogger("labadda.realtime")
MAX_PREVIEW_BYTES = 16_000
MAX_MESSAGE_BYTES = 32_000
SEND_TIMEOUT_SECONDS = 10.0  # per client and batch; bounds head-of-line blocking
# A board-only panel receives board activity only: no chat, feed or other content.
PANEL_EVENTS = {
    "board.op",
    "board.epoch",
    "board.preview",
    "presence",
    "revoked",
    "access_changed",
    "subscribed",
    "subscribe_failed",
    "session_ended",
    "hello",
    "pong",
    "error",
}


@dataclass(eq=False)
class Connection:
    ws: WebSocket
    user_id: uuid.UUID
    session_id: str
    display_name: str
    subscriptions: set[uuid.UUID] = field(default_factory=set)
    writable: set[uuid.UUID] = field(default_factory=set)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscription_generations: dict[uuid.UUID, int] = field(default_factory=dict)
    panel_workspace: uuid.UUID | None = None  # set for board-only touch-panel sessions


class Hub:
    def __init__(self, factory, settings: Settings):
        self.factory = factory
        self.settings = settings
        # One FIFO and worker per workspace: ordered fanout, batched access rechecks.
        self._queues: dict[uuid.UUID, asyncio.Queue] = {}
        self._workers: dict[uuid.UUID, asyncio.Task] = {}
        self.connections: set[Connection] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    def backlog(self) -> int:
        """Events queued for delivery across all workspaces; a snapshot for the health page."""
        return sum(queue.qsize() for queue in list(self._queues.values()))

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

    def publish(self, workspace_id: uuid.UUID | str, event: dict) -> None:
        # Normalize so a string ID can never silently miss UUID-keyed subscriptions.
        self._schedule(self._enqueue, uuid.UUID(str(workspace_id)), event)

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

    async def _send(
        self,
        conn: Connection,
        payload: dict,
        *,
        workspace_id: uuid.UUID | None = None,
        generation: int | None = None,
    ) -> None:
        if conn.panel_workspace is not None and payload.get("type") not in PANEL_EVENTS:
            return
        try:
            async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                async with conn.send_lock:
                    if conn not in self.connections:
                        return
                    if workspace_id is not None and (
                        workspace_id not in conn.subscriptions
                        or (
                            generation is not None
                            and generation != conn.subscription_generations.get(workspace_id, 0)
                        )
                    ):
                        return
                    await conn.ws.send_text(json.dumps(payload))
        except Exception:  # noqa: BLE001 — any transport failure closes this connection only
            # A batch timeout must not cancel an already-started transport cleanup.
            await asyncio.shield(self._close(conn, "send_failed"))

    def _check_many(self, conns: list[Connection], workspace_id: uuid.UUID) -> dict[Connection, tuple]:
        """Batched form of ``_check`` for one workspace: (session_ok, readable, writable) per connection.

        Uses the shared policy's eligible-reader set, which matches ``policy.resolve``: active users with
        a direct grant on the workspace or (for org units) on a descendant. Writable follows the same
        archive/posting-policy/direct-steward rule.
        """
        with self.factory() as db:
            sessions = {
                s.id: s
                for s in db.scalars(
                    select(AuthSession).where(AuthSession.id.in_({c.session_id for c in conns}))
                )
            }
            workspace = db.get(Workspace, workspace_id)
            readers = policy.eligible_reader_ids(db, workspace) if workspace is not None else set()
            stewards = {
                uid
                for uid, role in policy.direct_grants_for_workspace(db, workspace_id).items()
                if role == "steward"
            }
            result = {}
            for conn in conns:
                sess = sessions.get(conn.session_id)
                if sess is None or sess.user_id != conn.user_id or not session_valid(sess, self.settings):
                    result[conn] = (False, False, False)
                    continue
                readable = conn.user_id in readers  # eligible readers are already active users
                writable = (
                    readable
                    and not workspace.archived
                    and (workspace.posting_policy == "open" or conn.user_id in stewards)
                )
                result[conn] = (True, readable, writable)
            return result

    async def _enqueue(self, workspace_id: uuid.UUID, event: dict) -> None:
        queue = self._queues.get(workspace_id)
        if queue is None:
            queue = self._queues[workspace_id] = asyncio.Queue()
        queue.put_nowait(event)
        worker = self._workers.get(workspace_id)
        if worker is None or worker.done():
            self._workers[workspace_id] = asyncio.get_running_loop().create_task(self._worker(workspace_id))

    async def _worker(self, workspace_id: uuid.UUID, batch_limit: int = 200) -> None:
        """Deliver this workspace's events in commit order; exits when idle."""
        queue = self._queues[workspace_id]
        while True:
            try:
                batch = [await asyncio.wait_for(queue.get(), timeout=30)]
            except TimeoutError:
                if queue.empty():
                    self._queues.pop(workspace_id, None)
                    self._workers.pop(workspace_id, None)
                    return
                continue
            while len(batch) < batch_limit and not queue.empty():
                batch.append(queue.get_nowait())
            try:
                await self._deliver(workspace_id, batch)
            except Exception:  # keep the worker alive; clients catch up from committed state
                log.exception("realtime.delivery_failed")

    async def _deliver(self, workspace_id: uuid.UUID, events: list[dict]) -> None:
        targets = [c for c in list(self.connections) if workspace_id in c.subscriptions]
        if not targets:
            return
        # Recheck current access after commit and before sending, once per batch for all receivers.
        generations = {c: c.subscription_generations.get(workspace_id, 0) for c in targets}
        decisions = await asyncio.to_thread(self._check_many, targets, workspace_id)
        sends = []
        for conn in targets:
            if (
                conn not in self.connections
                or workspace_id not in conn.subscriptions
                or generations[conn] != conn.subscription_generations.get(workspace_id, 0)
            ):
                continue
            ok, readable, writable = decisions[conn]
            if not ok:
                sends.append(self._close(conn, "session_ended"))
            elif not readable:
                sends.append(self._drop(conn, workspace_id))
            else:
                conn.writable = (conn.writable - {workspace_id}) | ({workspace_id} if writable else set())
                sends.append(self._send_all(conn, workspace_id, events, generations[conn]))
        await asyncio.gather(*sends)

    async def _send_all(
        self, conn: Connection, workspace_id: uuid.UUID, events: list[dict], generation: int
    ) -> None:
        """Send a batch to one client; a client that cannot keep up is closed rather than stalling the
        workspace's ordered fanout. It reconnects and catches up from committed state."""

        async def send() -> None:
            for event in events:
                if (
                    conn not in self.connections
                    or workspace_id not in conn.subscriptions
                    or generation != conn.subscription_generations.get(workspace_id, 0)
                ):
                    return
                await self._send(conn, event, workspace_id=workspace_id, generation=generation)

        try:
            await asyncio.wait_for(send(), timeout=SEND_TIMEOUT_SECONDS)
        except TimeoutError:
            log.warning("realtime.slow_client_closed")
            await self._close(conn, "slow_client")

    async def _drop(self, conn: Connection, workspace_id: uuid.UUID) -> None:
        conn.subscription_generations[workspace_id] = conn.subscription_generations.get(workspace_id, 0) + 1
        conn.subscriptions.discard(workspace_id)
        conn.writable.discard(workspace_id)
        await self._send(conn, {"type": "revoked", "workspace_id": str(workspace_id)})
        await self._presence(workspace_id)

    async def _close(self, conn: Connection, reason: str) -> None:
        if conn not in self.connections:
            return
        subs = set(conn.subscriptions)
        self.connections.discard(conn)
        conn.subscriptions.clear()
        conn.writable.clear()
        try:
            async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                async with conn.send_lock:
                    await conn.ws.send_text(json.dumps({"type": "session_ended", "reason": reason}))
        except Exception:  # noqa: BLE001, S110 — best-effort notice on a connection being closed
            pass
        try:
            async with asyncio.timeout(SEND_TIMEOUT_SECONDS):
                await conn.ws.close(code=4401)
        except Exception:  # noqa: BLE001, S110 — best-effort close of a connection that may be dead
            pass
        for ws_id in subs:
            await self._presence(ws_id)

    async def _revalidate(self, predicate) -> None:
        for conn in [c for c in list(self.connections) if predicate(c)]:
            generations = {ws: conn.subscription_generations.get(ws, 0) for ws in conn.subscriptions}
            ok, readable, writable = await asyncio.to_thread(self._check, conn, set(generations))
            if not ok:
                await self._close(conn, "session_ended")
                continue
            for ws_id, generation in generations.items():
                if (
                    conn not in self.connections
                    or ws_id not in conn.subscriptions
                    or generation != conn.subscription_generations.get(ws_id, 0)
                ):
                    continue
                if ws_id not in readable:
                    await self._drop(conn, ws_id)
                elif ws_id in writable:
                    conn.writable.add(ws_id)
                else:
                    conn.writable.discard(ws_id)
            await self._send(conn, {"type": "access_changed"})

    async def _presence(self, workspace_id: uuid.UUID) -> None:
        present = {}
        for c in self.connections:
            if workspace_id in c.subscriptions:
                present[str(c.user_id)] = c.display_name
        payload = {
            "type": "presence",
            "workspace_id": str(workspace_id),
            "users": [{"id": k, "display_name": v} for k, v in sorted(present.items(), key=lambda kv: kv[1])],
        }
        await asyncio.gather(
            *(
                self._send(c, payload, workspace_id=workspace_id)
                for c in list(self.connections)
                if workspace_id in c.subscriptions
            )
        )

    # ---- socket endpoint ------------------------------------------------
    def _authenticate(self, token: str | None, kind: str):
        if not token:
            return None
        with self.factory() as db:
            sess = db.get(AuthSession, digest(token))
            if sess is None or sess.kind != kind or not session_valid(sess, self.settings):
                return None
            user = db.get(User, sess.user_id)
            if user is None or not user.is_active:
                return None
            return sess.id, user.id, user.display_name, sess.workspace_id

    async def serve(self, ws: WebSocket) -> None:
        self.loop = asyncio.get_running_loop()
        host = ws.headers.get("host")
        if not origin_allowed(ws.headers.get("origin"), host, self.settings):
            await ws.close(code=4403)
            return
        panel = ws.query_params.get("panel") == "1"
        cookie = self.settings.panel_cookie_name if panel else self.settings.cookie_name
        ident = await asyncio.to_thread(
            self._authenticate, ws.cookies.get(cookie), "board" if panel else "normal"
        )
        if ident is None:
            await ws.close(code=4401)
            return
        await ws.accept()
        conn = Connection(
            ws=ws,
            session_id=ident[0],
            user_id=ident[1],
            display_name=ident[2],
            panel_workspace=ident[3] if panel else None,
        )
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
        except Exception:  # noqa: BLE001, S110 — a broken socket ends this connection; cleanup runs below
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
        if conn.panel_workspace is not None and ws_id != conn.panel_workspace:
            # Same answer as for an unknown workspace.
            if kind == "subscribe":
                await self._send(conn, {"type": "subscribe_failed", "workspace_id": str(ws_id)})
            return
        if kind == "subscribe":
            generation = conn.subscription_generations.get(ws_id, 0)
            ok, readable, writable = await asyncio.to_thread(self._check, conn, {ws_id})
            if conn not in self.connections or generation != conn.subscription_generations.get(ws_id, 0):
                return
            if not ok:
                await self._close(conn, "session_ended")
                return
            if ws_id not in readable:
                # Same answer for unknown and out-of-scope IDs.
                await self._send(conn, {"type": "subscribe_failed", "workspace_id": str(ws_id)})
                return
            conn.subscription_generations[ws_id] = conn.subscription_generations.get(ws_id, 0) + 1
            conn.subscriptions.add(ws_id)
            conn.writable = (conn.writable - {ws_id}) | writable
            await self._send(conn, {"type": "subscribed", "workspace_id": str(ws_id)})
            await self._presence(ws_id)
        elif kind == "unsubscribe":
            conn.subscription_generations[ws_id] = conn.subscription_generations.get(ws_id, 0) + 1
            conn.subscriptions.discard(ws_id)
            conn.writable.discard(ws_id)
            await self._presence(ws_id)
        elif kind == "board.preview":
            # Transient stroke preview: bounded, never stored, only from writers.
            if (
                conn not in self.connections
                or ws_id not in conn.subscriptions
                or ws_id not in conn.writable
                or len(json.dumps(msg.get("stroke", {}))) > MAX_PREVIEW_BYTES
            ):
                return
            event = {
                "type": "board.preview",
                "workspace_id": str(ws_id),
                "actor_id": str(conn.user_id),
                "stroke": msg.get("stroke"),
                "preview_id": str(msg.get("preview_id", ""))[:64],
                "done": bool(msg.get("done")),
            }
            for other in [c for c in list(self.connections) if ws_id in c.subscriptions and c is not conn]:
                await self._send(other, event, workspace_id=ws_id)
