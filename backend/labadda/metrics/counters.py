"""Feature counters, recorded only for work that the database has committed.

Callers count after their own ``db.commit()`` or, where the commit happens elsewhere (shared
helpers such as notification creation), register the count on the session with
``count_workspace_on_commit``: it is applied by the root commit and dropped by a rollback.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

from ..models import Workspace
from . import catalog
from .registry import REGISTRY

_PENDING = "labadda.metrics.pending"


def count(name: str, dimension: str = catalog.NO_DIMENSION, amount: float = 1) -> None:
    """Count committed work under one catalogued dimension value."""
    REGISTRY.count(name, dimension, amount)


def workspace_dimensions(workspace: Workspace) -> tuple[str, ...]:
    """The unit kind, plus the organisation unit for ``org`` workspaces (AD-08)."""
    if workspace.kind == "org":
        return (workspace.kind, catalog.unit_dimension(workspace.id))
    return (workspace.kind,)


def count_workspace(name: str, workspace: Workspace, amount: float = 1) -> None:
    """Count committed work in a workspace by unit kind and, for org units, by unit."""
    for dimension in workspace_dimensions(workspace):
        REGISTRY.count(name, dimension, amount)


def count_workspace_on_commit(db: Session, name: str, workspace: Workspace, amount: float = 1) -> None:
    """Count work in a workspace once the session's outermost transaction commits."""
    entry = catalog.metric(name)
    dimensions = workspace_dimensions(workspace)
    for dimension in dimensions:
        catalog.check_dimension(entry, dimension)
    db.info.setdefault(_PENDING, []).append((name, dimensions, amount))


@event.listens_for(Session, "after_commit")
def _apply_pending(session: Session) -> None:
    # Releasing a savepoint also fires after_commit; only the outermost commit is durable.
    if session.in_nested_transaction():
        return
    for name, dimensions, amount in session.info.pop(_PENDING, []):
        for dimension in dimensions:
            REGISTRY.count(name, dimension, amount)


@event.listens_for(Session, "after_transaction_end")
def _drop_uncommitted(session: Session, transaction: SessionTransaction) -> None:
    if transaction.parent is None:
        session.info.pop(_PENDING, None)
