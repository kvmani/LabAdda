"""Authorize transient strokes at send time without queueing obsolete previews."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .realtime import Connection, Hub

MAX_PREVIEW_BYTES = 16_000


async def relay_preview(hub: Hub, conn: Connection, workspace_id: uuid.UUID, message: dict) -> None:
    """Check the sender and each recipient against current session and workspace access."""
    if (
        conn not in hub.connections
        or workspace_id not in conn.subscriptions
        or len(json.dumps(message.get("stroke", {}))) > MAX_PREVIEW_BYTES
    ):
        return
    generation = conn.subscription_generations.get(workspace_id, 0)
    ok, readable, writable = await asyncio.to_thread(hub._check, conn, {workspace_id})
    if (
        conn not in hub.connections
        or workspace_id not in conn.subscriptions
        or generation != conn.subscription_generations.get(workspace_id, 0)
    ):
        return
    if not ok:
        await hub._close(conn, "session_ended")
        return
    if workspace_id not in readable:
        await hub._drop(conn, workspace_id)
        return
    if workspace_id not in writable:
        conn.writable.discard(workspace_id)
        return
    conn.writable.add(workspace_id)
    event = {
        "type": "board.preview",
        "workspace_id": str(workspace_id),
        "actor_id": str(conn.user_id),
        "stroke": message.get("stroke"),
        "preview_id": str(message.get("preview_id", ""))[:64],
        "done": bool(message.get("done")),
    }
    await hub._deliver(workspace_id, [event], exclude=conn)
