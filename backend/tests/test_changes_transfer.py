"""T55 reviewed transfers: memberships, real access, sockets, steward notices and guards."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from labadda import audit
from labadda.changes.kinds import transfer
from labadda.models import AuditEvent, Membership, Notification, TodoTask, User, Workspace
from tests.test_changes_edit import edit, reviewed
from tests.test_panel import pair
from tests.test_realtime import recv_until, ws_url
from tests.test_todos import new_list, task_body

TASK_TITLE = "Recognisable furnace calibration task"


def move(ids, person="ben", unit="section_b", role="member", **options):
    """Build a fictional transfer request; Ben to Catalysis by default (scenario step 2)."""
    return {
        "request": {
            "kind": "transfer",
            "person_id": ids["users"][person],
            "to_unit_id": ids["workspaces"].get(unit, unit),
            "role": role,
            **options,
        }
    }


def preview(admin, request):
    response = admin.post("/admin/changes/preview", json=request)
    assert response.status_code == 200, response.text
    return response.json()


def codes(items):
    return [item["code"] for item in items]


def assign_tasks(as_user, ids, db_factory, open_count=2):
    """Asha (steward of Thin Films) assigns Ben open tasks there, plus one finished task."""
    asha = as_user("asha")
    row = new_list(asha, ids["workspaces"]["section_a"])
    for index in range(open_count + 1):
        created = asha.post(f"/todos/lists/{row['id']}/tasks", json=task_body(title=TASK_TITLE)).json()
        path = f"/todos/lists/{row['id']}/tasks/{created['id']}/assignee"
        assert asha.put(path, json={"user_id": ids["users"]["ben"], "revision": 1}).status_code == 200
        if index == open_count:
            with db_factory() as db:
                db.execute(
                    TodoTask.__table__.update()
                    .where(TodoTask.id == created["id"])
                    .values(done=True, status="done")
                )
                db.commit()
    return row


def grants(db_factory, person_id):
    with db_factory() as db:
        rows = db.execute(
            select(Membership.workspace_id, Membership.role).where(Membership.user_id == person_id)
        )
        return {str(workspace): role for workspace, role in rows}


def test_scenario_transfer_moves_home_and_memberships_and_notifies_stewards(as_user, ids, db_factory):
    assign_tasks(as_user, ids, db_factory)
    admin = as_user("admin")
    plan = preview(admin, move(ids))
    assert [step["summary"] for step in plan["steps"]] == [
        "Change the home unit of Ben Okafor to Catalysis Section",
        "Add Ben Okafor to Catalysis Section as member",
        "Remove Ben Okafor from Thin Films Section",
    ]
    assert plan["steps"][0]["before"]["home_unit"] == "Thin Films Section"
    assert plan["blockers"] == []
    tasks = [warning for warning in plan["warnings"] if warning["code"] == "open_tasks"]
    assert [(warning["target_id"], warning["count"]) for warning in tasks] == [
        (ids["workspaces"]["section_a"], 2)
    ]
    assert codes(plan["warnings"]) == ["access_gained", "access_lost", "open_tasks"]
    assert plan["affected_people"] == 1
    response = admin.post("/admin/changes/apply", json=reviewed(admin, move(ids)))
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["kind"] == "transfer" and receipt["stewards_notified"] == 1
    for text in (json_text(plan), response.text):
        assert TASK_TITLE not in text
    assert grants(db_factory, ids["users"]["ben"]) == {
        ids["workspaces"]["section_b"]: "member",
        ids["workspaces"]["reading_club"]: "steward",
    }
    assert (
        admin.get(f"/admin/people/{ids['users']['ben']}").json()["home_unit"]["name"] == "Catalysis Section"
    )
    notices = as_user("asha").get("/notifications").json()["items"]
    assert len(notices) == 1
    assert notices[0]["kind"] == "reassign"
    assert notices[0]["title"].startswith("Ben Okafor has moved to another unit. 2 open shared tasks")
    assert TASK_TITLE not in str(notices)
    assert notices[0]["link"] == {"view": "todos", "workspace_id": ids["workspaces"]["section_a"]}
    for name in ("dana", "chen", "ben"):
        assert as_user(name).get("/notifications").json()["items"] == []
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Notification)) == 1


def json_text(value) -> str:
    return str(value)


def test_transfer_revokes_old_socket_subscription_and_delayed_reads(as_user, ids, settings, db_factory):
    row = assign_tasks(as_user, ids, db_factory, open_count=1)
    ben, admin = as_user("ben"), as_user("admin")
    thin_films = ids["workspaces"]["section_a"]
    confirmation = reviewed(admin, move(ids))
    with ben.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": thin_films})
        recv_until(conn, "subscribed")
        assert admin.post("/admin/changes/apply", json=confirmation).status_code == 200
        assert recv_until(conn, "revoked")["workspace_id"] == thin_films
    for path in (f"/workspaces/{thin_films}", f"/workspaces/{thin_films}/posts", f"/todos/lists/{row['id']}"):
        response = ben.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert ben.get(f"/workspaces/{ids['workspaces']['section_b']}").status_code == 200


def test_inherited_access_gained_and_lost_match_real_reads(as_user, ids, db_factory):
    with db_factory() as db:
        optics = Workspace(kind="org", name="Optics Division", parent_id=ids["workspaces"]["root"])
        db.add(optics)
        db.flush()
        lasers = Workspace(kind="org", name="Lasers Section", parent_id=optics.id)
        db.add(lasers)
        db.commit()
        names = {"optics": str(optics.id), "lasers": str(lasers.id)}
    ids["workspaces"].update(names)
    admin, ben = as_user("admin"), as_user("ben")
    plan = preview(admin, move(ids, unit="lasers"))
    gained = {item["target_id"] for item in plan["warnings"] if item["code"] == "access_gained"}
    lost = {item["target_id"] for item in plan["warnings"] if item["code"] == "access_lost"}
    assert gained == {names["optics"], names["lasers"]}
    expected_lost = {ids["workspaces"][key] for key in ("section_a", "division", "group")}
    assert lost == expected_lost
    everything = set(ids["workspaces"].values())
    before = {space for space in everything if ben.get(f"/workspaces/{space}").status_code == 200}
    assert (
        admin.post("/admin/changes/apply", json=reviewed(admin, move(ids, unit="lasers"))).status_code == 200
    )
    after = {space for space in everything if ben.get(f"/workspaces/{space}").status_code == 200}
    assert after - before == gained
    assert before - after == lost
    assert ids["workspaces"]["root"] in after and ids["workspaces"]["reading_club"] in after


def test_keep_previous_unit_as_additional_access(as_user, ids, db_factory):
    admin = as_user("admin")
    request = move(ids, role="steward", keep_previous=True)
    plan = preview(admin, request)
    assert codes(plan["warnings"]) == ["access_gained"]
    assert admin.post("/admin/changes/apply", json=reviewed(admin, request)).status_code == 200
    assert grants(db_factory, ids["users"]["ben"]) == {
        ids["workspaces"]["section_a"]: "member",
        ids["workspaces"]["section_b"]: "steward",
        ids["workspaces"]["reading_club"]: "steward",
    }


def test_unticked_group_is_left_and_last_group_steward_is_blocked(as_user, ids, db_factory):
    admin = as_user("admin")
    club = ids["workspaces"]["reading_club"]
    blocked = preview(admin, move(ids, leave_workspace_ids=[club]))
    assert codes(blocked["blockers"]) == ["group_needs_steward"]
    request = move(ids, person="chen", unit="section_a", leave_workspace_ids=[club])
    plan = preview(admin, request)
    assert plan["blockers"] == []
    assert "Remove Chen Li from Microscopy Reading Club" in [step["summary"] for step in plan["steps"]]
    assert admin.post("/admin/changes/apply", json=reviewed(admin, request)).status_code == 200
    assert grants(db_factory, ids["users"]["chen"]) == {ids["workspaces"]["section_a"]: "member"}
    assert as_user("chen").get(f"/workspaces/{club}").status_code == 404


def test_unit_left_without_steward_needs_acknowledgement(as_user, ids):
    admin = as_user("admin")
    request = move(ids, person="asha")
    plan = preview(admin, request)
    assert codes(plan["blockers"]) == ["unit_without_steward"]
    assert admin.post("/admin/changes/apply", json=reviewed(admin, request)).status_code == 422
    acknowledged = move(ids, person="asha", acknowledge_no_steward=True)
    plan = preview(admin, acknowledged)
    assert plan["blockers"] == []
    assert "unit_without_steward" in codes(plan["warnings"])
    assert admin.post("/admin/changes/apply", json=reviewed(admin, acknowledged)).status_code == 200


@pytest.mark.parametrize(
    ("person", "options", "code"),
    [
        ("ben", {"unit": "section_a"}, "same_unit"),
        ("ben", {"unit": "project"}, "unit_unavailable"),
        ("fay", {}, "person_inactive"),
        ("ben", {"leave_workspace_ids": ["section_b"]}, "not_a_member"),
        ("ben", {"leave_workspace_ids": ["project"]}, "not_a_member"),
    ],
)
def test_transfer_blockers(person, options, code, as_user, ids):
    if "leave_workspace_ids" in options:
        options["leave_workspace_ids"] = [ids["workspaces"][key] for key in options["leave_workspace_ids"]]
    admin = as_user("admin")
    request = move(ids, person=person, **options)
    assert code in codes(preview(admin, request)["blockers"])
    response = admin.post("/admin/changes/apply", json=reviewed(admin, request))
    assert response.status_code == 422


def test_missing_person_or_unit_is_uniform_404(as_user, ids):
    admin = as_user("admin")
    assert admin.post("/admin/changes/preview", json=move(ids, unit=ids["users"]["ben"])).status_code == 404
    request = move(ids)
    request["request"]["person_id"] = ids["workspaces"]["section_a"]
    assert admin.post("/admin/changes/preview", json=request).status_code == 404


def test_stale_transfer_writes_nothing(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, move(ids))
    assign_tasks(as_user, ids, db_factory, open_count=1)
    response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_stale"
    assert ids["workspaces"]["section_a"] in grants(db_factory, ids["users"]["ben"])
    with db_factory() as db:
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "people.change")) is None


def test_concurrent_edit_and_transfer_of_one_person_one_wins(as_user, ids, db_factory):
    first, second = as_user("admin"), as_user("admin")
    confirmations = [
        reviewed(first, move(ids)),
        reviewed(second, edit(ids, designation="Research Officer E")),
    ]
    barrier = Barrier(2)

    def confirm(pair_):
        client, body = pair_
        barrier.wait(timeout=5)
        return client.post("/admin/changes/apply", json=body).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(confirm, zip([first, second], confirmations, strict=True)))
    assert sorted(results) == [200, 409]
    with db_factory() as db:
        assert db.scalar(select(func.count()).where(AuditEvent.action == "people.change")) == 1


def test_failure_in_last_step_leaves_every_row_unchanged(as_user, ids, db_factory):
    assign_tasks(as_user, ids, db_factory)
    admin = as_user("admin")
    confirmation = reviewed(admin, move(ids))
    before = grants(db_factory, ids["users"]["ben"])
    original = audit.record_step

    def fail_last(*args, **kwargs):
        if kwargs["index"] == 2:
            raise RuntimeError("Synthetic final-step failure")
        return original(*args, **kwargs)

    with patch.object(audit, "record_step", side_effect=fail_last), pytest.raises(RuntimeError):
        admin.post("/admin/changes/apply", json=confirmation)
    assert grants(db_factory, ids["users"]["ben"]) == before
    with db_factory() as db:
        person = db.get(User, ids["users"]["ben"])
        assert str(person.home_workspace_id) == ids["workspaces"]["section_a"]
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        changes = db.scalar(select(func.count()).where(AuditEvent.action.like("people.change%")))
        assert changes == 0


def test_parent_and_step_audits_record_actor_before_after_and_reason(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, move(ids))
    assert admin.post("/admin/changes/apply", json=confirmation).status_code == 200
    with db_factory() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("people.change%")).order_by(AuditEvent.id)
        ).all()
        assert [event.action for event in events] == ["people.change"] + ["people.change_step"] * 3
        assert events[0].detail["kind"] == "transfer"
        assert all(event.reason == "Annual staff review" for event in events)
        assert all(str(event.actor_id) == ids["users"]["admin"] for event in events)
        assert events[1].detail["after"]["home_unit"] == "Catalysis Section"
        assert events[3].detail["before"] == {"role": "member"} and events[3].detail["after"] == {
            "role": None
        }
        assert events[3].target_id == ids["workspaces"]["section_a"]
        memberships = db.scalars(
            select(AuditEvent.action).where(AuditEvent.action.like("membership.%"))
        ).all()
        assert sorted(memberships) == ["membership.remove", "membership.set"]


@pytest.mark.parametrize("username", ["asha", "ben", "chen", "dana", "eli"])
def test_members_cannot_transfer(username, as_user, ids):
    member = as_user(username)
    assert member.post("/admin/changes/preview", json=move(ids)).status_code == 403
    assert member.post("/admin/changes/apply", json=move(ids)).status_code == 403


def test_signed_out_and_panels_cannot_transfer(as_user, ids, make_client):
    assert make_client().post("/admin/changes/preview", json=move(ids)).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/preview", json=move(ids)).status_code == 401


@pytest.mark.parametrize(
    "change",
    [
        {"role": "owner"},
        {"keep_previous": "yes"},
        {"leave_workspace_ids": ["not-an-id"]},
        {"handover_until": "2026-11-19"},
        {"person_id": None},
    ],
)
def test_transfer_bounds(change, as_user, ids):
    request = move(ids)
    request["request"].update(change)
    assert as_user("admin").post("/admin/changes/preview", json=request).status_code == 422


def test_notice_disappears_when_steward_loses_access(as_user, ids, db_factory):
    assign_tasks(as_user, ids, db_factory, open_count=1)
    admin = as_user("admin")
    assert admin.post("/admin/changes/apply", json=reviewed(admin, move(ids))).status_code == 200
    with db_factory() as db:
        db.execute(
            Membership.__table__.delete().where(
                Membership.user_id == ids["users"]["asha"],
                Membership.workspace_id == ids["workspaces"]["section_a"],
            )
        )
        db.commit()
    assert as_user("asha").get("/notifications").json()["items"] == []


def test_demoting_the_last_steward_of_the_new_unit_needs_acknowledgement(as_user, ids, db_factory):
    with db_factory() as db:
        db.get(User, ids["users"]["asha"]).home_workspace_id = ids["workspaces"]["section_b"]
        db.commit()
    admin = as_user("admin")
    request = move(ids, person="asha", unit="section_a", role="member")
    plan = preview(admin, request)
    assert [(item["code"], item["target_id"]) for item in plan["blockers"]] == [
        ("unit_without_steward", ids["workspaces"]["section_a"])
    ]
    assert admin.post("/admin/changes/apply", json=reviewed(admin, request)).status_code == 422
    assert grants(db_factory, ids["users"]["asha"])[ids["workspaces"]["section_a"]] == "steward"
    acknowledged = move(ids, person="asha", unit="section_a", role="member", acknowledge_no_steward=True)
    assert "unit_without_steward" in codes(preview(admin, acknowledged)["warnings"])
    assert admin.post("/admin/changes/apply", json=reviewed(admin, acknowledged)).status_code == 200
    assert grants(db_factory, ids["users"]["asha"])[ids["workspaces"]["section_a"]] == "member"


def test_home_unit_moved_between_scope_read_and_row_lock_is_stale(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, move(ids))
    original = transfer.lock_scope

    def move_home_after_scope_read(db, request):
        scope = original(db, request)
        with db_factory() as writer:
            writer.get(User, ids["users"]["ben"]).home_workspace_id = ids["workspaces"]["division"]
            writer.commit()
        return scope

    with (
        patch.object(transfer, "lock_scope", side_effect=move_home_after_scope_read),
        patch.object(transfer, "build", side_effect=AssertionError("built from an unlocked scope")),
    ):
        response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "plan_stale"
    assert ids["workspaces"]["section_a"] in grants(db_factory, ids["users"]["ben"])
    with db_factory() as db:
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "people.change")) is None
