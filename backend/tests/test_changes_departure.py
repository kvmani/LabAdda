"""T56 leave, return, retirement, suspension and reinstatement; stale, concurrent, atomic, denied."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from labadda import audit, positions
from labadda.models import AuditEvent, Notification, UnitPosition, User
from tests.test_capabilities import grant
from tests.test_changes_authority import (
    apply,
    change,
    current_positions,
    make_head,
    site_today,
    start_of,
)
from tests.test_changes_edit import reviewed
from tests.test_changes_transfer import codes, grants, preview
from tests.test_panel import pair
from tests.test_realtime import recv_until, ws_url
from tests.test_todos import new_list, task_body

TASK_TITLE = "Recognisable spectrometer handover task"
POST_TEXT = "Recognisable notice about the vacuum pump"


def assign_task(as_user, ids, owner, workspace, assignee):
    client = as_user(owner)
    row = new_list(client, ids["workspaces"][workspace])
    created = client.post(f"/todos/lists/{row['id']}/tasks", json=task_body(title=TASK_TITLE)).json()
    path = f"/todos/lists/{row['id']}/tasks/{created['id']}/assignee"
    assert client.put(path, json={"user_id": ids["users"][assignee], "revision": 1}).status_code == 200


def retirement(ids, settings, **fields):
    ends = (site_today(settings) + timedelta(days=60)).isoformat()
    successors = [
        {
            "workspace_id": ids["workspaces"]["division"],
            "successor_id": ids["users"]["asha"],
            "acting": True,
            "ends_on": ends,
        },
        {"workspace_id": ids["workspaces"]["project"], "successor_id": ids["users"]["eli"]},
    ]
    return change(ids, "retire", person_id="dana", status="retired", successors=successors, **fields)


def test_scenario_dana_retires_and_asha_acts_as_head_for_sixty_days(as_user, ids, db_factory, settings):
    """Scenario step 1, end to end, including the acting term ending on its date."""
    make_head(db_factory, ids)
    assign_task(as_user, ids, "dana", "project", "dana")
    dana = as_user("dana")
    admin = as_user("admin")
    bare = preview(admin, change(ids, "retire", person_id="dana", status="retired"))
    assert codes(bare["blockers"]) == ["position_needs_successor", "group_needs_steward"]
    request = retirement(ids, settings)
    plan = preview(admin, request)
    assert plan["blockers"] == []
    ends = site_today(settings) + timedelta(days=60)
    assert [step["summary"] for step in plan["steps"]] == [
        "End the position of Dana Whitfield as Head of Surface Science Division",
        "Add Asha Rao to Surface Science Division as steward",
        f"Appoint Asha Rao as acting Head of Surface Science Division until {ends.isoformat()}",
        "Set the role of Eli Novak in Project Aurora to steward",
        "Remove Dana Whitfield from Project Aurora",
        "Remove Dana Whitfield from Surface Science Division",
        "Set the employment status of Dana Whitfield to retired and end their sign-in and open sessions",
    ]
    assert codes(plan["warnings"]) == ["last_steward", "last_steward", "open_tasks"]
    tasks = [item for item in plan["warnings"] if item["code"] == "open_tasks"]
    assert [(item["target_id"], item["count"]) for item in tasks] == [(ids["workspaces"]["project"], 1)]
    with dana.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        receipt = apply(admin, request)
        assert recv_until(conn, "session_ended")["type"] == "session_ended"
    assert receipt["stewards_notified"] == 1
    assert dana.get("/auth/session").status_code == 401
    assert dana.login("dana").status_code in (401, 403)
    assert grants(db_factory, ids["users"]["dana"]) == {}
    division = ids["workspaces"]["division"]
    assert current_positions(db_factory, division) == [(ids["users"]["asha"], "head", True)]
    notices = as_user("eli").get("/notifications").json()["items"]
    assert [item["title"][:40] for item in notices] == ["Dana Whitfield has retired or left. 1 op"]
    assert TASK_TITLE not in str(notices) + str(plan) + str(receipt)
    with db_factory() as db:
        assert positions.expire_due(db, settings, now=start_of(ends, settings)) == 1
    assert current_positions(db_factory, division) == []
    assert division not in grants(db_factory, ids["users"]["asha"])
    assert as_user("asha").get(f"/workspaces/{division}").status_code == 200  # inherited from Thin Films


def test_retiring_the_last_administrator_is_blocked(as_user, ids):
    admin = as_user("admin")
    plan = preview(admin, change(ids, "retire", person_id="admin", status="left"))
    assert codes(plan["blockers"]) == ["last_admin", "self_change"]
    for kind in ("suspend",):
        assert "last_admin" in codes(preview(admin, change(ids, kind, person_id="admin"))["blockers"])
    leave = change(ids, "leave", person_id="admin", expected_return_on="2099-01-01", block_sign_in=True)
    assert "last_admin" in codes(preview(admin, leave)["blockers"])


def test_retiring_a_group_last_steward_needs_a_member_successor(as_user, ids, db_factory):
    admin = as_user("admin")
    club = ids["workspaces"]["reading_club"]
    request = change(ids, "retire", person_id="ben", status="left")
    assert "group_needs_steward" in codes(preview(admin, request)["blockers"])
    outsider = change(
        ids,
        "retire",
        person_id="ben",
        status="left",
        successors=[{"workspace_id": club, "successor_id": ids["users"]["dana"]}],
    )
    assert "successor_not_member" in codes(preview(admin, outsider)["blockers"])
    chosen = change(
        ids,
        "retire",
        person_id="ben",
        status="left",
        successors=[{"workspace_id": club, "successor_id": ids["users"]["chen"]}],
    )
    plan = preview(admin, chosen)
    assert plan["blockers"] == []
    apply(admin, chosen)
    assert grants(db_factory, ids["users"]["chen"])[club] == "steward"
    with db_factory() as db:
        assert db.get(User, ids["users"]["ben"]).status == "left"


def test_retire_keeps_listed_memberships_and_refuses_strangers(as_user, ids, db_factory):
    admin = as_user("admin")
    stranger = change(
        ids, "retire", person_id="chen", status="retired", keep_workspace_ids=[ids["workspaces"]["project"]]
    )
    assert codes(preview(admin, stranger)["blockers"]) == ["not_a_member"]
    keep = change(
        ids,
        "retire",
        person_id="chen",
        status="retired",
        keep_workspace_ids=[ids["workspaces"]["reading_club"]],
    )
    apply(admin, keep)
    assert grants(db_factory, ids["users"]["chen"]) == {ids["workspaces"]["reading_club"]: "member"}
    assert as_user("ben").get(f"/workspaces/{ids['workspaces']['reading_club']}").status_code == 200


def test_unit_last_steward_needs_acknowledgement(as_user, ids):
    admin = as_user("admin")
    request = change(ids, "retire", person_id="asha", status="retired")
    assert codes(preview(admin, request)["blockers"]) == ["unit_without_steward"]
    acknowledged = change(ids, "retire", person_id="asha", status="retired", acknowledge_no_steward=True)
    plan = preview(admin, acknowledged)
    assert plan["blockers"] == [] and "unit_without_steward" in codes(plan["warnings"])


def test_leave_with_acting_cover_and_return_ends_it(as_user, ids, db_factory, settings):
    head = make_head(db_factory, ids)
    admin = as_user("admin")
    back = (site_today(settings) + timedelta(days=90)).isoformat()
    request = change(
        ids,
        "leave",
        person_id="dana",
        expected_return_on=back,
        acting=[{"position_id": head, "successor_id": ids["users"]["asha"]}],
    )
    plan = preview(admin, request)
    assert plan["steps"][0]["after"] == {"status": "on_leave", "sign_in": True, "expected_return_on": back}
    apply(admin, request)
    division = ids["workspaces"]["division"]
    assert sorted(current_positions(db_factory, division)) == sorted(
        [(ids["users"]["dana"], "head", False), (ids["users"]["asha"], "head", True)]
    )
    assert as_user("dana").get("/auth/session").status_code == 200
    assert "not_on_leave" in codes(preview(admin, change(ids, "return", person_id="ben"))["blockers"])
    returning = change(ids, "return", person_id="dana")
    plan = preview(admin, returning)
    assert plan["steps"][1]["summary"] == (
        "End the position of Asha Rao as acting Head of Surface Science Division "
        "and remove the membership given for it"
    )
    apply(admin, returning)
    assert current_positions(db_factory, division) == [(ids["users"]["dana"], "head", False)]
    assert division not in grants(db_factory, ids["users"]["asha"])
    with db_factory() as db:
        dana = db.get(User, ids["users"]["dana"])
        assert (dana.status, dana.expected_return_on) == ("active", None)


def test_leave_blocking_sign_in_ends_sessions(as_user, ids, db_factory, settings):
    admin, chen = as_user("admin"), as_user("chen")
    back = (site_today(settings) + timedelta(days=30)).isoformat()
    request = change(ids, "leave", person_id="chen", expected_return_on=back, block_sign_in=True)
    apply(admin, request)
    assert chen.get("/auth/session").status_code == 401
    assert chen.login("chen").status_code in (401, 403)
    blockers = codes(
        preview(admin, change(ids, "leave", person_id="ben", expected_return_on="2020-01-01"))["blockers"]
    )
    assert blockers == ["invalid_date"]


def test_suspend_ends_sessions_and_sockets_at_once(as_user, ids, db_factory, settings):
    make_head(db_factory, ids, username="asha", unit="section_a")
    ben, admin = as_user("ben"), as_user("admin")
    section = ids["workspaces"]["section_a"]
    with ben.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": section})
        recv_until(conn, "subscribed")
        apply(admin, change(ids, "suspend", person_id="ben"))
        assert recv_until(conn, "session_ended")["type"] == "session_ended"
    assert ben.get("/auth/session").status_code == 401
    assert ben.login("ben").status_code in (401, 403)
    assert ids["workspaces"]["section_a"] in grants(db_factory, ids["users"]["ben"])
    plan = preview(admin, change(ids, "suspend", person_id="asha"))
    assert plan["steps"][0]["summary"] == "End the position of Asha Rao as Head of Thin Films Section"
    assert "no_active_steward" in codes(plan["warnings"])
    assert codes(preview(admin, change(ids, "suspend", person_id="fay"))["blockers"]) == [
        "person_unavailable"
    ]


def test_reinstate_issues_a_new_code_and_restores_no_access(as_user, ids, db_factory, make_client):
    admin = as_user("admin")
    apply(admin, change(ids, "retire", person_id="chen", status="retired"))
    assert codes(preview(admin, change(ids, "reinstate", person_id="ben"))["blockers"]) == ["not_departed"]
    request = change(ids, "reinstate", person_id="chen")
    plan = preview(admin, request)
    placement = [item["message"] for item in plan["warnings"] if item["code"] == "last_placement"]
    assert placement and "Catalysis Section (member)" in placement[0]
    assert "Microscopy Reading Club (member)" in placement[0]
    receipt = apply(admin, request)
    code = receipt["activation"]["code"]
    assert code not in str(plan)
    with db_factory() as db:
        chen = db.get(User, ids["users"]["chen"])
        assert (chen.status, chen.is_active, chen.must_set_password, chen.password_hash) == (
            "invited",
            True,
            True,
            None,
        )
        assert code not in str(db.scalars(select(AuditEvent.detail)).all())
    assert grants(db_factory, ids["users"]["chen"]) == {}
    newcomer = make_client()
    response = newcomer.client.post(
        newcomer.url("/auth/activate"), json={"token": code, "password": "a-long-password"}
    )
    assert response.status_code == 200
    for key in ("section_b", "reading_club", "division"):
        assert newcomer.get(f"/workspaces/{ids['workspaces'][key]}").status_code == 404


def test_reinstating_a_suspended_admin_removes_retained_access_and_admin_role(as_user, ids, db_factory):
    with db_factory() as db:
        db.get(User, ids["users"]["ben"]).is_admin = True
        db.commit()
    admin = as_user("admin")
    apply(admin, change(ids, "suspend", person_id="ben"))
    plan = preview(admin, change(ids, "reinstate", person_id="ben"))
    summaries = [step["summary"] for step in plan["steps"]]
    assert "Do not restore the administrator role of Ben Okafor" in summaries
    assert "Remove Ben Okafor from Thin Films Section" in summaries
    apply(admin, change(ids, "reinstate", person_id="ben"))
    with db_factory() as db:
        assert db.get(User, ids["users"]["ben"]).is_admin is False
    assert grants(db_factory, ids["users"]["ben"]) == {}


def test_stale_retirement_writes_nothing(as_user, ids, db_factory, settings):
    make_head(db_factory, ids)
    admin = as_user("admin")
    confirmation = reviewed(admin, retirement(ids, settings))
    assign_task(as_user, ids, "dana", "project", "dana")
    response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 409 and response.json()["error"]["code"] == "plan_stale"
    with db_factory() as db:
        assert db.get(User, ids["users"]["dana"]).status == "active"
        assert db.scalar(select(func.count()).where(AuditEvent.action.like("people.change%"))) == 0


def test_concurrent_plans_on_one_person_one_wins(as_user, ids, db_factory):
    first, second = as_user("admin"), as_user("admin")
    confirmations = [
        reviewed(first, change(ids, "suspend", person_id="chen")),
        reviewed(second, change(ids, "promote", person_id="chen", designation="Scientific Officer D")),
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


def test_failure_in_last_step_leaves_every_row_unchanged(as_user, ids, db_factory, settings):
    make_head(db_factory, ids)
    assign_task(as_user, ids, "dana", "project", "dana")
    admin = as_user("admin")
    confirmation = reviewed(admin, retirement(ids, settings))
    before = {name: grants(db_factory, ids["users"][name]) for name in ("dana", "asha", "eli")}
    original = audit.record_step

    def fail_last(*args, **kwargs):
        if kwargs["index"] == 6:
            raise RuntimeError("Synthetic final-step failure")
        return original(*args, **kwargs)

    with patch.object(audit, "record_step", side_effect=fail_last), pytest.raises(RuntimeError):
        admin.post("/admin/changes/apply", json=confirmation)
    assert {name: grants(db_factory, ids["users"][name]) for name in before} == before
    assert current_positions(db_factory) == [(ids["users"]["dana"], "head", False)]
    with db_factory() as db:
        assert db.get(User, ids["users"]["dana"]).is_active
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        assert db.scalar(select(func.count()).where(AuditEvent.action.like("p%.%"))) == 0


def test_parent_step_and_position_audits(as_user, ids, db_factory, settings):
    make_head(db_factory, ids)
    admin = as_user("admin")
    apply(admin, retirement(ids, settings))
    with db_factory() as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action.like("people.change%")).order_by(AuditEvent.id)
        ).all()
        assert [event.action for event in events] == ["people.change"] + ["people.change_step"] * 7
        assert events[0].detail["kind"] == "retire" and events[0].target_id == ids["users"]["dana"]
        assert all(event.reason == "Annual staff review" for event in events)
        assert events[-1].detail["after"]["status"] == "retired"
        positions_audit = db.scalars(
            select(AuditEvent.action).where(AuditEvent.action.like("position.%"))
        ).all()
        assert sorted(positions_audit) == ["position.appoint", "position.end"]
    timeline = admin.get(f"/admin/people/{ids['users']['asha']}/timeline").json()["items"]
    assert "Position given" in [item["summary"] for item in timeline]


def test_no_content_in_any_p3_response(as_user, ids, db_factory, settings):
    """T61: recognisable post, task and note text never reaches a plan, receipt or profile."""
    make_head(db_factory, ids)
    assign_task(as_user, ids, "dana", "project", "dana")
    dana = as_user("dana")
    assert dana.post(
        f"/workspaces/{ids['workspaces']['division']}/posts", json={"body": POST_TEXT}
    ).status_code in (200, 201)
    assert dana.post(
        "/notes", json={"title": "Recognisable private note title", "body": "x"}
    ).status_code in (200, 201)
    admin = as_user("admin")
    texts = []
    for request in (
        retirement(ids, settings),
        change(ids, "promote", person_id="chen", workspace_id="section_b", role="steward"),
        change(ids, "suspend", person_id="ben"),
    ):
        texts.append(admin.post("/admin/changes/preview", json=request).text)
        texts.append(admin.post("/admin/changes/apply", json=reviewed(admin, request)).text)
    texts.append(admin.get(f"/admin/people/{ids['users']['dana']}").text)
    texts.append(admin.get("/admin/people").text)
    texts.append(admin.get(f"/admin/people/{ids['users']['dana']}/timeline").text)
    for text in texts:
        for secret in (TASK_TITLE, POST_TEXT, "Recognisable private note title"):
            assert secret not in text


KINDS = [
    ("promote", {"person_id": "chen", "designation": "Scientific Officer D"}),
    ("change_authority", {"workspace_id": "division", "position": "head", "successor_id": "asha"}),
    ("additional_charge", {"person_id": "chen", "workspace_id": "section_a", "role": "member"}),
    ("leave", {"person_id": "chen", "expected_return_on": "2099-01-01"}),
    ("return", {"person_id": "chen"}),
    ("retire", {"person_id": "chen", "status": "retired"}),
    ("suspend", {"person_id": "chen"}),
    ("reinstate", {"person_id": "fay"}),
]


@pytest.mark.parametrize(("kind", "fields"), KINDS)
@pytest.mark.parametrize("username", ["asha", "ben", "dana", "eli"])
def test_members_and_stewards_cannot_make_p3_changes(kind, fields, username, as_user, ids):
    """Sibling member, parent-only steward, project guest and unit steward: all 403."""
    request = change(ids, kind, **fields)
    member = as_user(username)
    assert member.post("/admin/changes/preview", json=request).status_code == 403
    assert member.post("/admin/changes/apply", json=request).status_code == 403


@pytest.mark.parametrize(("kind", "fields"), KINDS)
def test_signed_out_panels_and_usage_readers_cannot_make_p3_changes(kind, fields, as_user, ids, make_client):
    request = change(ids, kind, **fields)
    assert make_client().post("/admin/changes/preview", json=request).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/preview", json=request).status_code == 401
    assert grant(as_user("admin"), ids["users"]["eli"]).status_code in (200, 201)
    assert as_user("eli").post("/admin/changes/preview", json=request).status_code == 403


def test_deactivated_administrator_cannot_preview(as_user, ids, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        db.get(User, ids["users"]["admin"]).is_active = False
        db.commit()
    assert (
        admin.post("/admin/changes/preview", json=change(ids, "suspend", person_id="chen")).status_code == 401
    )


def test_expired_rows_stay_as_history(as_user, ids, db_factory, settings):
    head = make_head(db_factory, ids)
    admin = as_user("admin")
    apply(admin, change(ids, "suspend", person_id="dana"))
    with db_factory() as db:
        row = db.get(UnitPosition, head)
        assert row is not None and row.end_reason == "ended" and row.ended_at is not None
