"""Staff-list import and bulk changes: report, atomic apply, denials and stale plans."""

import uuid

import pytest
from sqlalchemy import func, select, update

from labadda.models import AuditEvent, Membership, User
from tests.test_panel import PANEL, pair

HEAD = "employee_no,username,display_name,designation,unit_code,role,status,effective_on\n"
CSV = {"Content-Type": "text/csv"}


def upload(api, text, headers=CSV):
    return api.post("/admin/changes/import/preview", headers=headers, content=text.encode())


def report(api, text):
    response = upload(api, text)
    assert response.status_code == 200, response.text
    return response.json()


def selected(data, *lines):
    return [item for row in data["rows"] if row["line"] in lines for item in row["requests"]]


def bulk(api, requests, reason="Autumn joiners"):
    plan = api.post("/admin/changes/bulk/preview", json={"requests": requests})
    assert plan.status_code == 200, plan.text
    body = plan.json()
    return {"requests": requests, "digest": body["digest"], "revisions": body["revisions"], "reason": reason}


FILE = (
    HEAD
    + "NW-501,gita.sen,Gita Sen,Scientific Officer,CS,steward,,2026-12-01\n"
    + ",hari.rao,Hari Rao,,TFS,,,\n"
    + ",ben,Ben Okafor,Senior Research Officer,CS,member,,\n"
    + ",chen,Chen Li,,,,suspended,\n"
    + ",eli,Eli Novak,,,,,\n"
    + ",bad user,Nobody,,,,,\n"
    + ",ghost,Ghost Person,,ZZZ,,,\n"
)


def test_report_groups_rows_and_lists_absent_people_without_changing_them(as_user, db_factory):
    admin = as_user("admin")
    data = report(admin, FILE)
    by_line = {row["line"]: row for row in data["rows"]}
    assert data["counts"] == {"add": 2, "change": 1, "transfer": 1, "errors": 2, "unchanged": 1}
    assert by_line[2]["group"] == "add" and by_line[3]["group"] == "add"
    assert by_line[4]["group"] == "transfer" and len(by_line[4]["requests"]) == 2
    assert by_line[5]["group"] == "change" and by_line[5]["requests"][0]["kind"] == "suspend"
    assert by_line[7]["group"] == "errors" and by_line[7]["requests"] == []
    assert "No open unit has the code ZZZ" in by_line[8]["errors"][0]
    assert {a["username"] for a in data["absent"]} == {"admin", "asha", "dana"}
    assert data["absent_total"] == 3
    assert data["digest"] == report(admin, FILE)["digest"]
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 7


def test_apply_commits_every_selected_row_once_and_audits_each_step(as_user, ids, db_factory):
    admin = as_user("admin")
    data = report(admin, FILE)
    request = bulk(admin, selected(data, 2, 3, 4, 5))
    response = admin.post("/admin/changes/bulk/apply", json=request)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["count"] == 5 and {a["username"] for a in receipt["added"]} == {"gita.sen", "hari.rao"}
    assert all(len(a["activation"]["code"]) >= 10 for a in receipt["added"])
    with db_factory() as db:
        gita = db.scalar(select(User).where(User.username == "gita.sen"))
        assert gita.status == "invited" and gita.employee_no == "NW-501"
        assert gita.joined_on.isoformat() == "2026-12-01"
        role = db.scalar(select(Membership.role).where(Membership.user_id == gita.id))
        assert role == "steward"
        ben = db.scalar(select(User).where(User.username == "ben"))
        assert str(ben.home_workspace_id) == ids["workspaces"]["section_b"]
        assert ben.designation == "Senior Research Officer"
        assert db.scalar(select(User.status).where(User.username == "chen")) == "suspended"
        assert db.scalar(select(User.status).where(User.username == "asha")) == "active"
        changes = db.scalars(select(AuditEvent).where(AuditEvent.action == "people.change")).all()
        assert len(changes) == 5
    again = admin.post("/admin/changes/bulk/apply", json=request)
    assert again.status_code == 409 and again.json()["error"]["code"] == "plan_stale"


def test_one_bad_request_applies_nothing(as_user, db_factory):
    admin = as_user("admin")
    data = report(admin, FILE)
    good = selected(data, 2)
    request = bulk(admin, good)
    clash = {
        "kind": "add_person",
        "username": "ben",
        "display_name": "Second Ben",
        "role": "member",
        "home_unit_id": good[0]["home_unit_id"],
    }
    plan = admin.post("/admin/changes/bulk/preview", json={"requests": [*good, clash]}).json()
    assert [b["code"] for b in plan["blockers"]] == ["username_taken"]
    assert plan["blockers"][0]["message"].startswith("Second Ben: ")
    blocked = {
        "requests": [*good, clash],
        "digest": plan["digest"],
        "revisions": plan["revisions"],
        "reason": "Autumn joiners",
    }
    response = admin.post("/admin/changes/bulk/apply", json=blocked)
    assert response.status_code == 422 and response.json()["error"]["code"] == "plan_blocked"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 7
        assert (
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.action.like("people.change%"))
            )
            == 0
        )
    assert admin.post("/admin/changes/bulk/apply", json=request).status_code == 200


def test_a_change_made_after_review_makes_the_plan_stale(as_user, ids):
    admin = as_user("admin")
    request = bulk(admin, selected(report(admin, FILE), 4))
    edit = {
        "request": {
            "kind": "edit_person",
            "person_id": ids["users"]["ben"],
            "fields": {"designation": "Someone else"},
        }
    }
    from tests.test_changes_edit import reviewed

    assert admin.post("/admin/changes/apply", json=reviewed(admin, edit)).status_code == 200
    response = admin.post("/admin/changes/bulk/apply", json=request)
    assert response.status_code == 409 and response.json()["error"]["code"] == "plan_stale"


def test_report_flags_formula_text_and_does_not_interpret_it(as_user):
    data = report(as_user("admin"), HEAD + ",gita.sen,=cmd|calc,,CS,,,\n")
    row = data["rows"][0]
    assert row["requests"][0]["display_name"] == "=cmd|calc"
    assert "plain text" in row["warnings"][0]


def test_upload_rejections_happen_before_parsing(as_user):
    admin = as_user("admin")
    assert upload(admin, FILE, {"Content-Type": "application/json"}).status_code == 422
    assert (
        upload(admin, FILE, {"Content-Type": "application/pdf"}).json()["error"]["code"] == "import_not_csv"
    )
    huge = upload(admin, "username\n" + "x" * (1024 * 1024))
    assert huge.status_code == 413 and huge.json()["error"]["code"] == "import_too_large"
    assert upload(admin, "").json()["error"]["code"] == "import_empty"


def test_template_downloads(as_user):
    response = as_user("admin").get("/admin/changes/import/template")
    assert response.status_code == 200 and response.text.startswith("﻿employee_no,username")


@pytest.mark.parametrize("who", ["ben", "asha", "dana"])
def test_non_administrators_are_forbidden_everywhere(as_user, ids, who):
    api = as_user(who)
    assert upload(api, FILE).status_code == 403
    assert api.get("/admin/changes/import/template").status_code == 403
    one = {"kind": "suspend", "person_id": ids["users"]["eli"]}
    assert api.post("/admin/changes/bulk/preview", json={"requests": [one]}).status_code == 403
    body = {"requests": [one], "digest": "0" * 64, "revisions": {}, "reason": "Because"}
    assert api.post("/admin/changes/bulk/apply", json=body).status_code == 403


def test_signed_out_and_board_only_sessions_are_refused(as_user, make_client, ids):
    anonymous = make_client()
    assert upload(anonymous, FILE).status_code == 401
    assert anonymous.get("/admin/changes/import/template").status_code == 401
    assert anonymous.post("/admin/changes/bulk/preview", json={"requests": []}).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/bulk/preview", json={"requests": []}).status_code == 401
    assert upload(as_user("admin"), FILE, {**CSV, **PANEL}).status_code == 401


def test_requests_cannot_name_other_kinds_or_repeat_a_person(as_user, ids):
    admin = as_user("admin")
    eli = ids["users"]["eli"]
    retire = {"kind": "retire", "person_id": eli, "status": "retired"}
    assert admin.post("/admin/changes/bulk/preview", json={"requests": [retire]}).status_code == 422
    twice = [{"kind": "suspend", "person_id": eli}] * 2
    assert admin.post("/admin/changes/bulk/preview", json={"requests": twice}).status_code == 422
    assert admin.post("/admin/changes/bulk/preview", json={"requests": []}).status_code == 422


def test_ordinary_staff_edits_do_not_change_and_unselected_rows_stay_untouched(as_user, db_factory):
    admin = as_user("admin")
    data = report(admin, FILE)
    assert admin.post("/admin/changes/bulk/apply", json=bulk(admin, selected(data, 3))).status_code == 200
    with db_factory() as db:
        assert db.scalar(select(User.status).where(User.username == "chen")) == "active"
        assert db.scalar(select(User.id).where(User.username == "gita.sen")) is None
        assert db.scalar(select(User.id).where(User.username == "hari.rao")) is not None


def test_changes_that_together_leave_a_unit_without_a_steward_are_blocked(as_user, ids, db_factory):
    """Each plan alone leaves one steward, but applied together they leave none."""
    with db_factory() as db:
        db.execute(
            update(Membership)
            .where(Membership.user_id == uuid.UUID(ids["users"]["ben"]))
            .where(Membership.workspace_id == uuid.UUID(ids["workspaces"]["section_a"]))
            .values(role="steward")
        )
        db.commit()
    admin = as_user("admin")
    section_b = ids["workspaces"]["section_b"]
    requests = [
        {"kind": "transfer", "person_id": ids["users"][who], "to_unit_id": section_b, "role": "member"}
        for who in ("asha", "ben")
    ]
    plan = admin.post("/admin/changes/bulk/preview", json={"requests": requests}).json()
    body = {"requests": requests, "digest": plan["digest"], "revisions": plan["revisions"], "reason": "Move"}
    response = admin.post("/admin/changes/bulk/apply", json=body)
    assert response.status_code == 422 and response.json()["error"]["code"] == "plan_blocked"
    with db_factory() as db:
        homes = set(db.scalars(select(User.home_workspace_id).where(User.username.in_(["asha", "ben"]))))
        assert homes == {uuid.UUID(ids["workspaces"]["section_a"])}


def _two_stewards(ids, db_factory):
    with db_factory() as db:
        db.execute(
            update(Membership)
            .where(Membership.user_id == uuid.UUID(ids["users"]["ben"]))
            .where(Membership.workspace_id == uuid.UUID(ids["workspaces"]["section_a"]))
            .values(role="steward")
        )
        db.commit()
    section_b = ids["workspaces"]["section_b"]
    return [
        {"kind": "transfer", "person_id": ids["users"][who], "to_unit_id": section_b, "role": "member"}
        for who in ("asha", "ben")
    ]


def _counts(db_factory):
    from labadda import models

    tables = (User, Membership, AuditEvent, models.CredentialToken)
    with db_factory() as db:
        return [db.scalar(select(func.count()).select_from(t)) for t in tables]


def test_preview_shows_the_joint_blocker_and_leaves_the_database_unchanged(as_user, ids, db_factory):
    requests = _two_stewards(ids, db_factory)
    admin = as_user("admin")
    added = {
        "kind": "add_person",
        "username": "newbie",
        "display_name": "New Bie",
        "role": "member",
        "home_unit_id": ids["workspaces"]["section_b"],
    }
    before = _counts(db_factory)
    plan = admin.post("/admin/changes/bulk/preview", json={"requests": [*requests, added]}).json()
    assert plan["blockers"]
    assert any(b["message"].startswith("Ben") for b in plan["blockers"])
    assert _counts(db_factory) == before
    # The apply-time digest is unchanged by the sequential look-ahead.
    single = admin.post("/admin/changes/bulk/preview", json={"requests": requests[:1]}).json()
    assert single["blockers"] == [] and _counts(db_factory) == before


def test_a_bulk_run_over_its_time_limit_is_refused_and_rolls_back(as_user, app, ids, db_factory):
    from dataclasses import replace

    admin = as_user("admin")
    data = report(admin, FILE)
    request = bulk(admin, selected(data, 2, 3, 4, 5))
    before = _counts(db_factory)
    app.state.settings = replace(app.state.settings, bulk_change_seconds=0.000001)
    for path, body in (
        ("/admin/changes/bulk/apply", request),
        ("/admin/changes/bulk/preview", {"requests": request["requests"]}),
    ):
        response = admin.post(path, json=body)
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "changes_unavailable"
        assert "too long" in response.json()["error"]["message"]
    assert upload(admin, FILE).status_code == 503
    assert _counts(db_factory) == before
