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
        {"workspace_id": ids["workspaces"]["project"], "successor_id": ids["users"]["esha"]},
    ]
    return change(ids, "retire", person_id="deepa", status="retired", successors=successors, **fields)


def test_scenario_deepa_retires_and_asha_acts_as_head_for_sixty_days(as_user, ids, db_factory, settings):
    """Scenario step 1, end to end, including the acting term ending on its date."""
    make_head(db_factory, ids)
    assign_task(as_user, ids, "deepa", "project", "deepa")
    deepa = as_user("deepa")
    admin = as_user("admin")
    bare = preview(admin, change(ids, "retire", person_id="deepa", status="retired"))
    assert codes(bare["blockers"]) == ["position_needs_successor", "group_needs_steward"]
    request = retirement(ids, settings)
    plan = preview(admin, request)
    assert plan["blockers"] == []
    ends = site_today(settings) + timedelta(days=60)
    assert [step["summary"] for step in plan["steps"]] == [
        "End the position of Deepa Nair as Head of Surface Engineering Division",
        "Add Asha Rao to Surface Engineering Division as steward",
        f"Appoint Asha Rao as acting Head of Surface Engineering Division until {ends.isoformat()}",
        "Set the role of Esha Menon in Project Tejas to steward",
        "Remove Deepa Nair from Project Tejas",
        "Remove Deepa Nair from Surface Engineering Division",
        "Set the employment status of Deepa Nair to retired and end their sign-in and open sessions",
    ]
    assert codes(plan["warnings"]) == ["last_steward", "last_steward", "open_tasks"]
    tasks = [item for item in plan["warnings"] if item["code"] == "open_tasks"]
    assert [(item["target_id"], item["count"]) for item in tasks] == [(ids["workspaces"]["project"], 1)]
    with deepa.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        receipt = apply(admin, request)
        assert recv_until(conn, "session_ended")["type"] == "session_ended"
    assert receipt["stewards_notified"] == 1
    assert deepa.get("/auth/session").status_code == 401
    assert deepa.login("deepa").status_code in (401, 403)
    assert grants(db_factory, ids["users"]["deepa"]) == {}
    division = ids["workspaces"]["division"]
    assert current_positions(db_factory, division) == [(ids["users"]["asha"], "head", True)]
    notices = as_user("esha").get("/notifications").json()["items"]
    assert [item["title"][:40] for item in notices] == ["Deepa Nair has retired or left. 1 open s"]
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
    request = change(ids, "retire", person_id="bharat", status="left")
    assert "group_needs_steward" in codes(preview(admin, request)["blockers"])
    outsider = change(
        ids,
        "retire",
        person_id="bharat",
        status="left",
        successors=[{"workspace_id": club, "successor_id": ids["users"]["deepa"]}],
    )
    assert "successor_not_member" in codes(preview(admin, outsider)["blockers"])
    chosen = change(
        ids,
        "retire",
        person_id="bharat",
        status="left",
        successors=[{"workspace_id": club, "successor_id": ids["users"]["chitra"]}],
    )
    plan = preview(admin, chosen)
    assert plan["blockers"] == []
    apply(admin, chosen)
    assert grants(db_factory, ids["users"]["chitra"])[club] == "steward"
    with db_factory() as db:
        assert db.get(User, ids["users"]["bharat"]).status == "left"


def test_retire_keeps_listed_memberships_and_refuses_strangers(as_user, ids, db_factory):
    admin = as_user("admin")
    stranger = change(
        ids, "retire", person_id="chitra", status="retired", keep_workspace_ids=[ids["workspaces"]["project"]]
    )
    assert codes(preview(admin, stranger)["blockers"]) == ["not_a_member"]
    keep = change(
        ids,
        "retire",
        person_id="chitra",
        status="retired",
        keep_workspace_ids=[ids["workspaces"]["reading_club"]],
    )
    apply(admin, keep)
    assert grants(db_factory, ids["users"]["chitra"]) == {ids["workspaces"]["reading_club"]: "member"}
    assert as_user("bharat").get(f"/workspaces/{ids['workspaces']['reading_club']}").status_code == 200


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
        person_id="deepa",
        expected_return_on=back,
        acting=[{"position_id": head, "successor_id": ids["users"]["asha"]}],
    )
    plan = preview(admin, request)
    assert plan["steps"][0]["after"] == {"status": "on_leave", "sign_in": True, "expected_return_on": back}
    apply(admin, request)
    division = ids["workspaces"]["division"]
    assert sorted(current_positions(db_factory, division)) == sorted(
        [(ids["users"]["deepa"], "head", False), (ids["users"]["asha"], "head", True)]
    )
    assert as_user("deepa").get("/auth/session").status_code == 200
    assert "not_on_leave" in codes(preview(admin, change(ids, "return", person_id="bharat"))["blockers"])
    returning = change(ids, "return", person_id="deepa")
    plan = preview(admin, returning)
    assert plan["steps"][1]["summary"] == (
        "End the position of Asha Rao as acting Head of Surface Engineering Division "
        "and remove the membership given for it"
    )
    apply(admin, returning)
    assert current_positions(db_factory, division) == [(ids["users"]["deepa"], "head", False)]
    assert division not in grants(db_factory, ids["users"]["asha"])
    with db_factory() as db:
        deepa = db.get(User, ids["users"]["deepa"])
        assert (deepa.status, deepa.expected_return_on) == ("active", None)


def test_leave_blocking_sign_in_ends_sessions(as_user, ids, db_factory, settings):
    admin, chitra = as_user("admin"), as_user("chitra")
    back = (site_today(settings) + timedelta(days=30)).isoformat()
    request = change(ids, "leave", person_id="chitra", expected_return_on=back, block_sign_in=True)
    apply(admin, request)
    assert chitra.get("/auth/session").status_code == 401
    assert chitra.login("chitra").status_code in (401, 403)
    blockers = codes(
        preview(admin, change(ids, "leave", person_id="bharat", expected_return_on="2020-01-01"))["blockers"]
    )
    assert blockers == ["invalid_date"]


def test_suspend_ends_sessions_and_sockets_at_once(as_user, ids, db_factory, settings):
    make_head(db_factory, ids, username="asha", unit="section_a")
    bharat, admin = as_user("bharat"), as_user("admin")
    section = ids["workspaces"]["section_a"]
    with bharat.client.websocket_connect(ws_url(settings)) as conn:
        conn.receive_json()
        conn.send_json({"type": "subscribe", "workspace_id": section})
        recv_until(conn, "subscribed")
        apply(admin, change(ids, "suspend", person_id="bharat"))
        assert recv_until(conn, "session_ended")["type"] == "session_ended"
    assert bharat.get("/auth/session").status_code == 401
    assert bharat.login("bharat").status_code in (401, 403)
    assert ids["workspaces"]["section_a"] in grants(db_factory, ids["users"]["bharat"])
    plan = preview(admin, change(ids, "suspend", person_id="asha"))
    assert plan["steps"][0]["summary"] == "End the position of Asha Rao as Head of Thin Films Section"
    assert "no_active_steward" in codes(plan["warnings"])
    assert codes(preview(admin, change(ids, "suspend", person_id="farhan"))["blockers"]) == [
        "person_unavailable"
    ]


def test_reinstate_issues_a_new_code_and_restores_no_access(as_user, ids, db_factory, make_client):
    admin = as_user("admin")
    apply(admin, change(ids, "retire", person_id="chitra", status="retired"))
    assert codes(preview(admin, change(ids, "reinstate", person_id="bharat"))["blockers"]) == ["not_departed"]
    request = change(ids, "reinstate", person_id="chitra")
    plan = preview(admin, request)
    placement = [item["message"] for item in plan["warnings"] if item["code"] == "last_placement"]
    assert placement and "Corrosion Section (member)" in placement[0]
    assert "Microscopy Journal Club (member)" in placement[0]
    receipt = apply(admin, request)
    code = receipt["activation"]["code"]
    assert code not in str(plan)
    with db_factory() as db:
        chitra = db.get(User, ids["users"]["chitra"])
        assert (chitra.status, chitra.is_active, chitra.must_set_password, chitra.password_hash) == (
            "invited",
            True,
            True,
            None,
        )
        assert code not in str(db.scalars(select(AuditEvent.detail)).all())
    assert grants(db_factory, ids["users"]["chitra"]) == {}
    newcomer = make_client()
    response = newcomer.client.post(
        newcomer.url("/auth/activate"), json={"token": code, "password": "a-long-password"}
    )
    assert response.status_code == 200
    for key in ("section_b", "reading_club", "division"):
        assert newcomer.get(f"/workspaces/{ids['workspaces'][key]}").status_code == 404


def test_reinstating_a_suspended_admin_removes_retained_access_and_admin_role(as_user, ids, db_factory):
    with db_factory() as db:
        db.get(User, ids["users"]["bharat"]).is_admin = True
        db.commit()
    admin = as_user("admin")
    apply(admin, change(ids, "suspend", person_id="bharat"))
    plan = preview(admin, change(ids, "reinstate", person_id="bharat"))
    summaries = [step["summary"] for step in plan["steps"]]
    assert "Do not restore the administrator role of Bharat Kulkarni" in summaries
    assert "Remove Bharat Kulkarni from Thin Films Section" in summaries
    apply(admin, change(ids, "reinstate", person_id="bharat"))
    with db_factory() as db:
        assert db.get(User, ids["users"]["bharat"]).is_admin is False
    assert grants(db_factory, ids["users"]["bharat"]) == {}


def test_stale_retirement_writes_nothing(as_user, ids, db_factory, settings):
    make_head(db_factory, ids)
    admin = as_user("admin")
    confirmation = reviewed(admin, retirement(ids, settings))
    assign_task(as_user, ids, "deepa", "project", "deepa")
    response = admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 409 and response.json()["error"]["code"] == "plan_stale"
    with db_factory() as db:
        assert db.get(User, ids["users"]["deepa"]).status == "active"
        assert db.scalar(select(func.count()).where(AuditEvent.action.like("people.change%"))) == 0


def test_concurrent_plans_on_one_person_one_wins(as_user, ids, db_factory):
    first, second = as_user("admin"), as_user("admin")
    confirmations = [
        reviewed(first, change(ids, "suspend", person_id="chitra")),
        reviewed(second, change(ids, "promote", person_id="chitra", designation="Scientific Officer D")),
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
    assign_task(as_user, ids, "deepa", "project", "deepa")
    admin = as_user("admin")
    confirmation = reviewed(admin, retirement(ids, settings))
    before = {name: grants(db_factory, ids["users"][name]) for name in ("deepa", "asha", "esha")}
    original = audit.record_step

    def fail_last(*args, **kwargs):
        if kwargs["index"] == 6:
            raise RuntimeError("Synthetic final-step failure")
        return original(*args, **kwargs)

    with patch.object(audit, "record_step", side_effect=fail_last), pytest.raises(RuntimeError):
        admin.post("/admin/changes/apply", json=confirmation)
    assert {name: grants(db_factory, ids["users"][name]) for name in before} == before
    assert current_positions(db_factory) == [(ids["users"]["deepa"], "head", False)]
    with db_factory() as db:
        assert db.get(User, ids["users"]["deepa"]).is_active
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
        assert events[0].detail["kind"] == "retire" and events[0].target_id == ids["users"]["deepa"]
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
    assign_task(as_user, ids, "deepa", "project", "deepa")
    deepa = as_user("deepa")
    assert deepa.post(
        f"/workspaces/{ids['workspaces']['division']}/posts", json={"body": POST_TEXT}
    ).status_code in (200, 201)
    assert deepa.post(
        "/notes", json={"title": "Recognisable private note title", "body": "x"}
    ).status_code in (200, 201)
    admin = as_user("admin")
    texts = []
    for request in (
        retirement(ids, settings),
        change(ids, "promote", person_id="chitra", workspace_id="section_b", role="steward"),
        change(ids, "suspend", person_id="bharat"),
    ):
        texts.append(admin.post("/admin/changes/preview", json=request).text)
        texts.append(admin.post("/admin/changes/apply", json=reviewed(admin, request)).text)
    texts.append(admin.get(f"/admin/people/{ids['users']['deepa']}").text)
    texts.append(admin.get("/admin/people").text)
    texts.append(admin.get(f"/admin/people/{ids['users']['deepa']}/timeline").text)
    for text in texts:
        for secret in (TASK_TITLE, POST_TEXT, "Recognisable private note title"):
            assert secret not in text


KINDS = [
    ("promote", {"person_id": "chitra", "designation": "Scientific Officer D"}),
    ("change_authority", {"workspace_id": "division", "position": "head", "successor_id": "asha"}),
    ("additional_charge", {"person_id": "chitra", "workspace_id": "section_a", "role": "member"}),
    ("leave", {"person_id": "chitra", "expected_return_on": "2099-01-01"}),
    ("return", {"person_id": "chitra"}),
    ("retire", {"person_id": "chitra", "status": "retired"}),
    ("suspend", {"person_id": "chitra"}),
    ("reinstate", {"person_id": "farhan"}),
]


@pytest.mark.parametrize(("kind", "fields"), KINDS)
@pytest.mark.parametrize("username", ["asha", "bharat", "deepa", "esha"])
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
    assert grant(as_user("admin"), ids["users"]["esha"]).status_code in (200, 201)
    assert as_user("esha").post("/admin/changes/preview", json=request).status_code == 403


def test_deactivated_administrator_cannot_preview(as_user, ids, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        db.get(User, ids["users"]["admin"]).is_active = False
        db.commit()
    assert (
        admin.post("/admin/changes/preview", json=change(ids, "suspend", person_id="chitra")).status_code
        == 401
    )


def test_expired_rows_stay_as_history(as_user, ids, db_factory, settings):
    head = make_head(db_factory, ids)
    admin = as_user("admin")
    apply(admin, change(ids, "suspend", person_id="deepa"))
    with db_factory() as db:
        row = db.get(UnitPosition, head)
        assert row is not None and row.end_reason == "ended" and row.ended_at is not None


def test_a_retiring_person_cannot_be_their_own_successor(as_user, ids, db_factory):
    make_head(db_factory, ids)
    admin = as_user("admin")
    successors = [
        {"workspace_id": ids["workspaces"]["division"], "successor_id": ids["users"]["deepa"]},
        {"workspace_id": ids["workspaces"]["project"], "successor_id": ids["users"]["deepa"]},
    ]
    plan = preview(admin, change(ids, "retire", person_id="deepa", status="retired", successors=successors))
    assert codes(plan["blockers"]).count("invalid_successor") == 2
