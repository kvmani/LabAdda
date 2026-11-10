"""Content-free workspace invalidation; personal work never enters shared channels."""
from __future__ import annotations

import uuid

from fastapi import Request


def publish_changed(request: Request, workspace_id: uuid.UUID | None) -> None:
    """Call only after a new mutation commits, using the actual list scope.

    Hints are deliberately unordered and lossy: subscribers refetch authorized
    HTTP state after a hint/reconnect. No task/list/comment/author metadata.
    The existing hub rechecks current delivery access and excludes board panels.
    """
    if workspace_id is not None:
        request.app.state.hub.publish(workspace_id, {
            'type': 'tasks.changed', 'workspace_id': str(workspace_id)})
