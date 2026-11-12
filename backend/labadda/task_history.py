"""Revision content history. Read using current list permission, never usage.read."""

from .models import TodoChange

FIELDS = ("title", "description", "due_date", "priority", "checklist", "done", "status")


def snapshot(task) -> dict:
    """The tracked fields of a task as plain JSON-safe values."""
    fields = {name: getattr(task, name) for name in FIELDS}
    fields["assignee"] = (
        {"id": str(task.assignee_id), "display_name": task.assignee.display_name}
        if task.assignee_id
        else None
    )
    fields["due_date"] = task.due_date.isoformat() if task.due_date else None
    return fields


def record(db, task, actor_id, before: dict | None = None) -> None:
    """Add a history row holding only the fields that differ from `before` (all fields on create)."""
    after = snapshot(task)
    changes = {
        name: {"before": before.get(name) if before else None, "after": value}
        for name, value in after.items()
        if before is None or value != before.get(name)
    }
    db.add(
        TodoChange(
            task_id=task.id,
            revision=task.revision,
            actor_id=actor_id,
            action="created" if before is None else "updated",
            changes=changes,
        )
    )
