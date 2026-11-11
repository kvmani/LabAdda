"""T44 assignment never grants access; current-grant aggregate and lock safety."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import delete

from labadda.cli import alembic_config
from labadda.models import Membership, User
from tests.test_todos import new_list, task_body


def task(api, workspace=None):
    row = new_list(api, workspace)
    path = f"/todos/lists/{row['id']}/tasks"
    result = api.post(path, json=task_body()).json()
    return row, result, path + "/" + result["id"]


def test_shared_assignment_history_and_mine(as_user, ids):
    ben = as_user("ben")
    _row, created, path = task(ben, ids["workspaces"]["section_a"])
    response = ben.put(path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 1})
    assert response.status_code == 200, response.text
    assigned = response.json()
    assert assigned["assignee"]["display_name"] == "Asha Rao" and assigned["revision"] == 2
    assert as_user("asha").get("/todos/mine").json()["items"][0]["id"] == created["id"]
    assert ben.get("/todos/mine").json()["items"] == []
    history = ben.get(path + "/history").json()["items"][0]
    assert history["changes"]["assignee"]["after"]["id"] == ids["users"]["asha"]
    assert history["changes"]["assignee"]["after"]["display_name"] == "Asha Rao"
    assert (
        ben.put(path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 1}).status_code == 409
    )
    assert (
        ben.put(path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 2}).json()["revision"]
        == 2
    )
    assert ben.put(path + "/assignee", json={"user_id": None, "revision": 2}).json()["revision"] == 3
    assert as_user("asha").get("/todos/mine").json()["items"] == []


@pytest.mark.parametrize("name", ["chen", "dana", "admin", "fay"])
def test_sibling_parent_admin_disabled_cannot_be_assigned(as_user, ids, name):
    api = as_user("ben")
    _, _, path = task(api, ids["workspaces"]["section_a"])
    response = api.put(path + "/assignee", json={"user_id": ids["users"][name], "revision": 1})
    assert response.status_code == 422
    assert as_user("admin").get(path).status_code == 404


def test_personal_is_owner_only_and_mine_includes_unassigned_personal(as_user, ids):
    api = as_user("ben")
    row, created, path = task(api)
    assert [r["id"] for r in api.get("/todos/mine").json()["items"]] == [created["id"]]
    assert (
        api.put(path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 1}).status_code == 422
    )
    assert (
        api.put(path + "/assignee", json={"user_id": ids["users"]["ben"], "revision": 1}).status_code == 200
    )
    assert as_user("admin").get("/todos/mine").json()["items"] == []
    assert api.get(f"/todos/lists/{row['id']}/assignees").json()["items"][0]["id"] == ids["users"]["ben"]


def test_upward_and_direct_group_project_eligibility(as_user, ids):
    ben = as_user("ben")
    _, _, path = task(ben, ids["workspaces"]["division"])
    assert (
        ben.put(path + "/assignee", json={"user_id": ids["users"]["chen"], "revision": 1}).status_code == 200
    )
    _, _, path = task(ben, ids["workspaces"]["reading_club"])
    assert (
        ben.put(path + "/assignee", json={"user_id": ids["users"]["chen"], "revision": 1}).status_code == 200
    )
    _, _, path = task(as_user("eli"), ids["workspaces"]["project"])
    assert (
        as_user("eli")
        .put(path + "/assignee", json={"user_id": ids["users"]["dana"], "revision": 1})
        .status_code
        == 200
    )
    assert len(as_user("chen").get("/todos/mine").json()["items"]) == 2


def test_revocation_hides_mine_without_rewriting_assignment(as_user, ids):
    ben = as_user("ben")
    _, _created, path = task(ben, ids["workspaces"]["section_a"])
    ben.put(path + "/assignee", json={"user_id": ids["users"]["ben"], "revision": 1})
    assert len(ben.get("/todos/mine").json()["items"]) == 1
    as_user("admin").delete(
        f"/admin/workspaces/{ids['workspaces']['section_a']}/memberships/{ids['users']['ben']}"
    )
    assert ben.get("/todos/mine").json()["items"] == []
    assert ben.get(path).status_code == 404
    assert as_user("asha").get(path).json()["assignee"]["id"] == ids["users"]["ben"]


def test_directory_and_mine_filter_pages(as_user, ids):
    api = as_user("ben")
    row, _, _path = task(api, ids["workspaces"]["division"])
    directory = f"/todos/lists/{row['id']}/assignees"
    first = api.get(directory + "?limit=1").json()
    second = api.get(directory + "?limit=1&after=" + first["next_cursor"]).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert api.get(directory + "?q=Ben").json()["items"][0]["id"] == ids["users"]["ben"]
    assert api.get(directory + "?q=%25").json()["items"] == []
    for _i in range(3):
        task(api)
    page = api.get("/todos/mine?limit=2").json()
    following = api.get("/todos/mine?limit=2&after=" + page["next_cursor"]).json()
    assert len(page["items"]) == 2 and len(following["items"]) == 1
    assert api.get("/todos/mine?status=done").json()["items"] == []
    assert api.get("/todos/mine?limit=51").status_code == 422
    assert api.get("/todos/mine?status=invalid").status_code == 422


def test_panel_csrf_and_nonmember_denied(as_user, ids):
    api = as_user("ben")
    row, _, path = task(api, ids["workspaces"]["section_a"])
    for url in ["/todos/mine", f"/todos/lists/{row['id']}/assignees"]:
        assert api.get(url, headers={"X-LabAdda-Panel": "1"}).status_code == 401
    assert (
        as_user("chen")
        .put(path + "/assignee", json={"user_id": ids["users"]["chen"], "revision": 1})
        .status_code
        == 404
    )
    assert (
        api.client.put(api.url(path + "/assignee"), json={"user_id": None, "revision": 1}).status_code == 403
    )


def test_mine_rechecks_grants_after_serialization(as_user, ids, db_factory, monkeypatch):
    from labadda.api import task_assignment

    api = as_user("ben")
    _, _, path = task(api, ids["workspaces"]["section_a"])
    api.put(path + "/assignee", json={"user_id": ids["users"]["ben"], "revision": 1})
    serialize = task_assignment._task_json

    def revoke(row):
        result = serialize(row)
        with db_factory() as db:
            db.execute(delete(Membership).where(Membership.user_id == ids["users"]["ben"]))
            db.commit()
        return result

    monkeypatch.setattr(task_assignment, "_task_json", revoke)
    result = api.get("/todos/mine").json()
    assert result["items"] == [] and result["next_cursor"] is None and result["restart_required"]


def test_reciprocal_assignments_use_consistent_identity_order(as_user, ids):
    ben, asha = as_user("ben"), as_user("asha")
    _, _, one = task(ben, ids["workspaces"]["section_a"])
    _, _, two = task(asha, ids["workspaces"]["section_a"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(api.put, path + "/assignee", json={"user_id": ids["users"][target], "revision": 1})
            for api, path, target in [(ben, one, "asha"), (asha, two, "ben")]
        ]
        assert [r.result(timeout=5).status_code for r in futures] == [200, 200]


def test_inactive_assignee_and_queued_authority_change(as_user, ids, db_factory):
    api = as_user("ben")
    _, _, path = task(api, ids["workspaces"]["section_a"])
    api.put(path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 1})
    with db_factory() as db:
        db.get(User, ids["users"]["asha"]).is_active = False
        db.commit()
    assert api.get(path).json()["assignee"]["is_active"] is False
    assert (
        api.put(path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 2}).status_code == 422
    )
    assert api.put(path + "/assignee", json={"user_id": None, "revision": 2}).status_code == 200


def test_migration_protects_current_and_past_assignments(as_user, ids, settings):
    api = as_user("ben")
    _, _, path = task(api)
    api.put(path + "/assignee", json={"user_id": ids["users"]["ben"], "revision": 1})
    api.put(path + "/assignee", json={"user_id": None, "revision": 2})
    with pytest.raises(RuntimeError, match="Task assignments exist"):
        command.downgrade(alembic_config(settings.database_url), "0018")


def test_target_deactivation_while_assignment_waits_rejects_stale_eligibility(as_user, ids, db_factory):
    import time

    from sqlalchemy import select, text

    api = as_user("ben")
    _, _, path = task(api, ids["workspaces"]["section_a"])
    with db_factory() as writer, ThreadPoolExecutor(max_workers=1) as pool:
        target = writer.scalar(select(User).where(User.id == ids["users"]["asha"]).with_for_update())
        pending = pool.submit(
            api.put, path + "/assignee", json={"user_id": ids["users"]["asha"], "revision": 1}
        )
        deadline = time.monotonic() + 1.5
        blocked = False
        while time.monotonic() < deadline:
            writer.execute(text("select pg_stat_clear_snapshot()"))
            blocked = writer.scalar(
                text(
                    "select exists(select 1 from pg_stat_activity where datname=current_database() and "
                    "wait_event_type='Lock' and query like '%ORDER BY users.id FOR NO KEY UPDATE%')"
                )
            )
            if blocked:
                break
            time.sleep(0.01)
        try:
            assert blocked, "Assignment must block on sorted target identity lock"
            target.is_active = False
            writer.commit()
        except BaseException:
            writer.rollback()
            raise
        assert pending.result(timeout=5).status_code == 422
    current = api.get(path).json()
    assert current["assignee"] is None and current["revision"] == 1
