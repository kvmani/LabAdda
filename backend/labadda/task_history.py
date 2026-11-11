"""Revision content history. Read using current list permission, never usage.read."""

from .models import TodoChange

FIELDS = ("title", "description", "due_date", "priority", "checklist", "done", "status")


def snapshot(task):
    result = {key: getattr(task, key) for key in FIELDS}
    result["assignee"] = (
        {"id": str(task.assignee_id), "display_name": task.assignee.display_name}
        if task.assignee_id
        else None
    )
    result["due_date"] = task.due_date.isoformat() if task.due_date else None
    return result


def record(db, task, actor_id, before=None):
    after = snapshot(task)
    changes = {
        key: {"before": before.get(key) if before else None, "after": value}
        for key, value in after.items()
        if before is None or value != before.get(key)
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
