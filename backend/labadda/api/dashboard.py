"""Bounded personal collaboration overview; never a site-wide content inventory."""

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .. import policy
from ..deps import Actor, current_actor, get_db, get_settings
from ..models import ChatMessage, ChatRead, Note, TodoList, TodoTask, Workspace
from ..security import utcnow
from ..serialize import iso
from .notifications import _visible
from .todos import _actor, _task_json

router = APIRouter(tags=["dashboard"])

TASK_LIMIT = 25
NOTE_LIMIT = 10
CHAT_LIMIT = 10
UPDATE_LIMIT = 10


def _workspace_names(db: Session, workspace_ids: set) -> dict:
    """Map each readable workspace id to its display name."""
    workspaces = db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids)))
    return {workspace.id: workspace.name for workspace in workspaces}


def _open_task_rows(db: Session, user, readable_ids: set) -> list:
    """Open tasks the user owns or is assigned in a readable workspace, one past the display limit."""
    own_or_assigned = or_(
        TodoList.owner_id == user.id,
        and_(TodoTask.assignee_id == user.id, TodoList.workspace_id.in_(readable_ids)),
    )
    priority_rank = case((TodoTask.priority == "high", 0), (TodoTask.priority == "normal", 1), else_=2)
    query = (
        select(TodoTask, TodoList)
        .join(TodoList, TodoTask.list_id == TodoList.id)
        .where(TodoTask.done.is_(False), own_or_assigned)
        .order_by(TodoTask.due_date.asc().nulls_last(), priority_rank, TodoTask.id)
        .limit(TASK_LIMIT + 1)
    )
    return db.execute(query).all()


def _task_items(task_rows: list, workspace_names: dict) -> list[dict]:
    """Serialize the displayed tasks with their list and workspace labels."""
    return [
        {
            **_task_json(task),
            "list_title": todo_list.title,
            "workspace_id": str(todo_list.workspace_id) if todo_list.workspace_id else None,
            "workspace_name": workspace_names.get(todo_list.workspace_id),
        }
        for task, todo_list in task_rows[:TASK_LIMIT]
    ]


def _dated_notes(db: Session, user) -> list:
    """The user's notes that have a due time, one past the display limit."""
    return db.scalars(
        select(Note)
        .where(Note.owner_id == user.id, Note.due_at.is_not(None))
        .order_by(Note.due_at, Note.id)
        .limit(NOTE_LIMIT + 1)
    ).all()


def _unread_chat_items(db: Session, user, readable_ids: set, workspace_names: dict) -> list[dict]:
    """Unread chat message counts per readable workspace, excluding the user's own messages."""
    own_read_marker = and_(ChatRead.workspace_id == ChatMessage.workspace_id, ChatRead.user_id == user.id)
    unread_counts = db.execute(
        select(ChatMessage.workspace_id, func.count())
        .outerjoin(ChatRead, own_read_marker)
        .where(
            ChatMessage.workspace_id.in_(readable_ids),
            ChatMessage.author_id != user.id,
            ChatMessage.seq > func.coalesce(ChatRead.last_seq, 0),
        )
        .group_by(ChatMessage.workspace_id)
    ).all()
    return [
        {"workspace_id": str(workspace_id), "workspace_name": workspace_names[workspace_id], "unread": count}
        for workspace_id, count in unread_counts
    ]


def _update_items(db: Session, actor: Actor) -> list[dict]:
    """The newest notifications the actor may still see."""
    return [
        {
            "id": str(notification.id),
            "kind": notification.kind,
            "created_at": iso(notification.created_at),
            "read": notification.read_at is not None,
            **info,
        }
        for notification, info in _visible(db, actor, UPDATE_LIMIT)
    ]


@router.get("/dashboard")
def overview(request: Request, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    user = _actor(request, actor, db)
    readable_ids = set(policy.readable_workspace_ids(db, user))
    workspace_names = _workspace_names(db, readable_ids)
    task_rows = _open_task_rows(db, user, readable_ids)
    tasks = _task_items(task_rows, workspace_names)
    notes = _dated_notes(db, user)
    note_items = [
        {"id": str(note.id), "title": note.title, "due_at": iso(note.due_at)} for note in notes[:NOTE_LIMIT]
    ]
    chats = _unread_chat_items(db, user, readable_ids, workspace_names)

    # Access is re-read while building the response; anything that changed mid-way is
    # dropped and the page is told to reload instead of showing stale grants.
    readable_after_first_check = set(policy.readable_workspace_ids(db, _actor(request, actor, db)))
    updates = _update_items(db, actor)
    readable_now = set(policy.readable_workspace_ids(db, _actor(request, actor, db)))
    allowed_ids = {str(workspace_id) for workspace_id in readable_now}
    access_changed = readable_now != readable_ids or readable_after_first_check != readable_ids

    tasks = [task for task in tasks if task["workspace_id"] is None or task["workspace_id"] in allowed_ids]
    chats = [chat for chat in chats if chat["workspace_id"] in allowed_ids]
    updates = [
        update
        for update in updates
        if update["workspace"] is None or update["workspace"]["id"] in allowed_ids
    ]
    busiest_chats = sorted(chats, key=lambda chat: (-chat["unread"], chat["workspace_name"]))
    timezone = get_settings(request).timezone
    return {
        "today": utcnow().astimezone(ZoneInfo(timezone)).date().isoformat(),
        "timezone": timezone,
        "tasks": tasks,
        "tasks_more": len(task_rows) > TASK_LIMIT and not access_changed,
        "notes": note_items,
        "notes_more": len(notes) > NOTE_LIMIT,
        "updates": updates,
        "chats": busiest_chats[:CHAT_LIMIT],
        "chats_more": len(chats) > CHAT_LIMIT and not access_changed,
        "restart_required": access_changed,
        "observed_at": iso(utcnow()),
    }
