"""Feature counters at commit points: kinds and units, retries once, personal work excluded (T62)."""

import uuid
from datetime import UTC, datetime, timedelta

from labadda import metrics, notify
from labadda.metrics import REGISTRY
from labadda.models import Workspace

from .test_chat_attachments import upload
from .test_panel import stroke, ws
from .test_todos import list_body, task_body


def counts(metric):
    rows = REGISTRY.closed(datetime.now(UTC) + timedelta(minutes=2))
    return {row.dimension: row.value for row in rows if row.metric == metric}


def unit(ids, key="section_a"):
    return f"unit:{ids['workspaces'][key]}"


def test_retried_post_counts_once_by_kind_and_unit(as_user, ids):
    asha = as_user("asha")
    body = {"body": "Calibration notes", "client_id": "retry-post-0001"}
    first = asha.post(f"/workspaces/{ws(ids)}/posts", json=body)
    again = asha.post(f"/workspaces/{ws(ids)}/posts", json=body)
    assert first.status_code == 201
    assert again.json()["id"] == first.json()["id"]
    assert counts("posts.created") == {"org": 1, unit(ids): 1}


def test_replies_in_a_project_count_by_kind_only(as_user, ids):
    esha = as_user("esha")
    post = esha.post(f"/workspaces/{ws(ids, 'project')}/posts", json={"body": "Plan"}).json()
    reply = {"body": "Agreed", "client_id": "retry-reply-01"}
    assert esha.post(f"/posts/{post['id']}/replies", json=reply).status_code == 201
    assert esha.post(f"/posts/{post['id']}/replies", json=reply).status_code == 201
    assert counts("replies.created") == {"project": 1}
    assert counts("posts.created") == {"project": 1}


def test_chat_message_and_its_attachment_are_counted_once(as_user, ids):
    bharat = as_user("bharat")
    asset, data = upload(bharat)
    assert counts("uploads.count") == {}
    message = {"body": "Files attached", "client_id": "chat-retry-01", "attachment_ids": [asset["id"]]}
    path = f"/workspaces/{ws(ids, 'reading_club')}/chat"
    assert bharat.post(path, json=message).status_code == 201
    assert bharat.post(path, json=message).status_code in (200, 201)
    assert counts("chat.messages") == {"group": 1}
    assert counts("uploads.count") == {"group": 1}
    assert counts("uploads.bytes") == {"group": len(data)}
    assert counts("uploads.size_band") == {"under_100kb": 1}


def test_duplicate_board_operation_counts_once(as_user, ids):
    asha = as_user("asha")
    path = f"/workspaces/{ws(ids)}/board/ops"
    assert asha.post(path, json=stroke("op-metric-01", "m1")).json()["duplicate"] is False
    assert asha.post(path, json=stroke("op-metric-01", "m1")).json()["duplicate"] is True
    assert counts("board.operations") == {"org": 1, unit(ids): 1}


def test_workspace_tasks_count_creation_and_completion(as_user, ids):
    asha = as_user("asha")
    task_list = asha.post("/todos/lists", json=list_body(workspace_id=ws(ids))).json()
    body = task_body()
    path = f"/todos/lists/{task_list['id']}/tasks"
    task = asha.post(path, json=body).json()
    assert asha.post(path, json=body).status_code in (200, 201)
    edit = {**task_body(done=True), "revision": task["revision"]}
    edit.pop("client_id")
    assert asha.put(f"{path}/{task['id']}", json=edit).status_code == 200
    assert counts("tasks.created") == {"org": 1, unit(ids): 1}
    assert counts("tasks.completed") == {"org": 1, unit(ids): 1}


def test_personal_task_lists_are_never_counted(as_user):
    asha = as_user("asha")
    task_list = asha.post("/todos/lists", json=list_body()).json()
    assert asha.post(f"/todos/lists/{task_list['id']}/tasks", json=task_body(done=True)).status_code == 201
    assert counts("tasks.created") == {}
    assert counts("tasks.completed") == {}


def test_mention_notifications_are_counted(as_user, ids):
    asha = as_user("asha")
    assert asha.post(f"/workspaces/{ws(ids)}/posts", json={"body": "Ask @bharat"}).status_code == 201
    assert counts("notifications.created") == {"org": 1, unit(ids): 1}


def test_rolled_back_work_is_not_counted(db_factory, ids):
    with db_factory() as db:
        workspace = db.get(Workspace, uuid.UUID(ws(ids, "project")))
        notify.create(
            db,
            recipients=[uuid.UUID(ids["users"]["esha"])],
            kind="mention",
            workspace_id=workspace.id,
            source_type="post",
            source_id=uuid.uuid4(),
            occurrence="rolled-back",
        )
        metrics.count_workspace_on_commit(db, "posts.created", workspace)
        db.rollback()
        db.commit()
    assert counts("notifications.created") == {}
    assert counts("posts.created") == {}


def test_sign_ins_are_counted_by_outcome(make_client):
    make_client("asha")
    assert make_client().login("asha", "wrong-password-1").status_code == 401
    assert make_client().login("farhan").status_code == 401
    assert counts("auth.signin_ok") == {"": 1}
    assert counts("auth.signin_failed") == {"": 2}
