"""Presence contains only current readers and reaches only current readers."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .realtime import Hub


async def publish_presence(hub: Hub, workspace_id: uuid.UUID) -> None:
    """Remove stale subscribers without recursively broadcasting intermediate presence."""
    targets = [conn for conn in list(hub.connections) if workspace_id in conn.subscriptions]
    if not targets:
        return
    generations = {conn: conn.subscription_generations.get(workspace_id, 0) for conn in targets}
    decisions = await asyncio.to_thread(hub._check_many, targets, workspace_id)
    readers = []
    cleanup = []
    for conn in targets:
        if (
            conn not in hub.connections
            or workspace_id not in conn.subscriptions
            or generations[conn] != conn.subscription_generations.get(workspace_id, 0)
        ):
            continue
        ok, readable, writable = decisions[conn]
        if not ok:
            cleanup.append(hub._close(conn, "session_ended", notify_presence=False))
        elif not readable:
            cleanup.append(hub._drop(conn, workspace_id, notify_presence=False))
        else:
            conn.writable = (conn.writable - {workspace_id}) | ({workspace_id} if writable else set())
            readers.append(conn)
    present = {str(conn.user_id): conn.display_name for conn in readers}
    payload = {
        "type": "presence",
        "workspace_id": str(workspace_id),
        "users": [
            {"id": user_id, "display_name": name}
            for user_id, name in sorted(present.items(), key=lambda item: item[1])
        ],
    }
    await asyncio.gather(
        *cleanup,
        *(
            hub._send(conn, payload, workspace_id=workspace_id, generation=generations[conn])
            for conn in readers
        ),
    )
