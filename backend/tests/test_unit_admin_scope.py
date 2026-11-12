"""P7 T60: a unit administrator acts only inside their branch, from grants as they are now."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from labadda import policy
from labadda.changes.plan import Plan, Snapshot, Step, Warning
from labadda.changes.unit_scope import Reach
from labadda.models import AuditEvent, ScheduledChange, UnitPosition, User
from tests.test_changes_authority import change, site_today
from tests.test_changes_edit import edit, reviewed
from tests.test_changes_scheduled import reviewed_for, run
from tests.test_changes_transfer import grants, move
from tests.test_panel import PANEL
from tests.unit_admin_support import apply_reviewed, appoint, preview, withdraw


@pytest.fixture
def division_admin(as_user, ids, db_factory):
    """Dana administers the Surface Science Division: Thin Films and Catalysis lie below it."""
    appoint(db_factory, ids, "dana", "division")
    return as_user("dana")


def names(response, key="people"):
    return sorted(item["username"] for item in response.json()[key])


def home(db_factory, ids, username):
    with db_factory() as db:
        return str(db.get(User, ids["users"][username]).home_workspace_id)


# --- navigation and the legacy console stay closed -------------------------------------------


def test_unit_administrator_navigation_is_people_and_organisation_only(division_admin):
    response = division_admin.get("/admin/console")
    assert response.json() == {
        "sections": ["people", "org"],
        "read_only": False,
        "unit_admin": True,
    }


@pytest.mark.parametrize(
    "path",
    [
        "/admin/users",
        "/admin/workspaces",
        "/admin/audit",
        "/admin/usage",
        "/admin/usage-readers",
        "/admin/policy-drafts",
        "/admin/org/attention",
        "/admin/changes/import/template",
    ],
)
def test_unit_administrator_cannot_reach_site_wide_screens(division_admin, path):
    assert division_admin.get(path).status_code == 403


def test_legacy_account_tools_cannot_create_administrators(division_admin, ids):
    body = {"username": "mallory", "display_name": "Mallory", "is_admin": True}
    assert division_admin.post("/admin/users", json=body).status_code == 403
    assert (
        division_admin.patch(f"/admin/users/{ids['users']['ben']}", json={"is_admin": True}).status_code
        == 403
    )


def test_import_and_unit_admin_kinds_are_for_site_administrators(division_admin, ids):
    upload = division_admin.client.post(
        division_admin.url("/admin/changes/import/preview"),
        content=b"x",
        headers={"Content-Type": "text/csv", "X-CSRF-Token": division_admin.csrf},
    )
    assert upload.status_code == 403
    request = change(ids, "unit_admin_grant", person_id="ben", unit_id="section_a")
    assert preview(division_admin, request).status_code == 403
    assert (
        division_admin.post(
            "/admin/changes/apply", json={**request, "digest": "0" * 64, "revisions": {}, "reason": "Try it"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("name", ["ben", "eli"])
def test_ordinary_members_have_no_console(as_user, ids, name):
    api = as_user(name)
    assert api.get("/admin/console").status_code == 403
    assert api.get("/admin/people").status_code == 403
    assert preview(api, move(ids, "ben", "section_b")).status_code == 403


def test_former_unit_administrator_loses_every_screen(division_admin, ids, db_factory):
    assert division_admin.get("/admin/people").status_code == 200
    withdraw(db_factory, ids, "dana", "division")
    for path in ("/admin/console", "/admin/people", "/admin/org/tree", "/admin/changes/scheduled"):
        assert division_admin.get(path).status_code == 403, path
    request = move(ids, "ben", "section_b")
    assert preview(division_admin, request).status_code == 403


def test_deactivated_unit_administrator_is_signed_out(division_admin, ids, db_factory):
    with db_factory() as db:
        db.get(User, ids["users"]["dana"]).is_active = False
        db.commit()
    assert division_admin.get("/admin/people").status_code == 401


def test_board_only_session_is_refused(division_admin, as_user, make_client, ids):
    assert division_admin.get("/admin/people", headers=PANEL).status_code == 401
    assert division_admin.post("/admin/changes/preview", json=move(ids), headers=PANEL).status_code == 401


# --- reading: the branch only -----------------------------------------------------------------


def test_directory_lists_only_people_whose_home_is_in_the_branch(division_admin, as_user, ids, db_factory):
    assert names(division_admin.get("/admin/people")) == ["asha", "ben", "chen", "dana"]
    appoint(db_factory, ids, "chen", "section_b")
    assert names(as_user("chen").get("/admin/people")) == ["chen"]
    response = as_user("chen").get(f"/admin/people?unit_id={ids['workspaces']['section_a']}")
    assert response.status_code == 404
    assert as_user("chen").get("/admin/people?role=admin").json()["people"] == []


def test_parent_of_the_branch_and_siblings_are_invisible_to_a_child_administrator(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    asha = as_user("asha")
    assert names(asha.get("/admin/people")) == ["asha", "ben"]
    for username in ("dana", "chen", "eli", "admin"):
        for tail in ("", "/access", "/timeline"):
            assert asha.get(f"/admin/people/{ids['users'][username]}{tail}").status_code == 404
    export = asha.get("/admin/people/export.csv")
    assert export.status_code == 200
    assert "Chen" not in export.text and "Dana" not in export.text and "Asha" in export.text


def test_profile_access_and_positions_show_only_the_branch(division_admin, ids, db_factory):
    ben = ids["users"]["ben"]
    assert division_admin.get(f"/admin/people/{ben}").status_code == 200
    access = division_admin.get(f"/admin/people/{ben}/access")
    assert sorted(row["workspace"]["name"] for row in access.json()["memberships"]) == [
        "Surface Science Division",
        "Thin Films Section",
    ]
    for text in (access.text, division_admin.get(f"/admin/people/{ben}").text):
        assert "Reading Club" not in text and "Northwind" not in text and "Materials Group" not in text


def test_organisation_chart_is_the_branch_as_its_own_tree(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    tree = as_user("asha").get("/admin/org/tree").json()
    assert [unit["name"] for unit in tree["units"]] == ["Thin Films Section"]
    assert tree["units"][0]["parent_id"] is None
    assert tree["spaces"] == []


def test_candidates_only_for_units_of_the_branch(division_admin, ids):
    for key in ("division", "section_a"):
        assert (
            division_admin.get(f"/admin/changes/candidates?workspace_id={ids['workspaces'][key]}").status_code
            == 200
        )
    for key in ("group", "root", "project", "reading_club"):
        path = f"/admin/changes/candidates?workspace_id={ids['workspaces'][key]}"
        assert division_admin.get(path).status_code == 404


# --- changing: inside the branch, never across it ----------------------------------------------


def test_unit_administrator_transfers_inside_the_branch(division_admin, ids, db_factory):
    apply_reviewed(division_admin, move(ids, "ben", "section_b"))
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_b"]
    with db_factory() as db:
        applied = db.scalars(select(AuditEvent).where(AuditEvent.action == "people.change")).one()
        assert str(applied.actor_id) == ids["users"]["dana"]


def test_cannot_transfer_across_branches_alone(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    asha = as_user("asha")
    # Out of Thin Films into Catalysis, which only a second appointment would cover.
    assert preview(asha, move(ids, "ben", "section_b")).status_code == 404
    assert preview(asha, move(ids, "ben", "division")).status_code == 404
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_a"]
    appoint(db_factory, ids, "asha", "section_b")
    apply_reviewed(asha, move(ids, "ben", "section_b"))
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_b"]


def test_sibling_and_parent_only_administrators_cannot_touch_the_others_people(as_user, ids, db_factory):
    appoint(db_factory, ids, "chen", "section_b")
    appoint(db_factory, ids, "asha", "section_a")
    assert preview(as_user("chen"), move(ids, "ben", "section_b")).status_code == 404  # sibling
    assert preview(as_user("chen"), edit(ids, designation="Lead")).status_code == 404
    request = change(ids, "edit_person", person_id="dana", fields={"designation": "Head"})
    assert preview(as_user("asha"), request).status_code == 404  # parent's person, child-only admin
    request = change(ids, "suspend", person_id="admin")
    assert preview(as_user("asha"), request).status_code == 404  # a site administrator


def test_person_with_larger_authority_cannot_be_changed_by_a_smaller_one(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    appoint(db_factory, ids, "ben", "division")  # Ben lives in Thin Films but administers more
    response = preview(as_user("asha"), edit(ids, designation="Lead"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "outside_your_units"


def test_units_below_the_administered_unit_can_be_managed_but_not_the_unit_itself(division_admin, ids):
    create = change(ids, "unit_create", parent_id="section_a", name="Sensors", code="SEN")
    apply_reviewed(division_admin, create)
    rename = change(ids, "unit_rename", unit_id="section_a", name="Thin Films Lab")
    apply_reviewed(division_admin, rename)
    above = change(ids, "unit_create", parent_id="group", name="Sideways", code="SIDE")
    assert preview(division_admin, above).status_code == 404
    for kind, fields in (
        ("unit_rename", {"unit_id": "division", "name": "Renamed"}),
        ("unit_close", {"unit_id": "division"}),
        ("unit_move", {"unit_id": "section_a", "new_parent_id": "group"}),
        ("unit_merge", {"unit_id": "section_a", "into_unit_id": "group"}),
    ):
        assert preview(division_admin, change(ids, kind, **fields)).status_code == 404, kind


def test_adding_a_person_needs_a_unit_of_the_branch(division_admin, ids):
    body = {"kind": "add_person", "username": "newcomer", "display_name": "New Comer", "role": "member"}
    inside = {"request": {**body, "home_unit_id": ids["workspaces"]["section_a"]}}
    apply_reviewed(division_admin, inside)
    outside = {"request": {**body, "username": "other", "home_unit_id": ids["workspaces"]["group"]}}
    assert preview(division_admin, outside).status_code == 404


def test_projects_and_groups_beyond_the_branch_block_the_plan_and_stay_unnamed(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    request = change(ids, "retire", person_id="ben", status="left")
    response = preview(as_user("asha"), request)
    assert response.status_code == 200
    plan = response.json()
    assert "outside_your_units" in [blocker["code"] for blocker in plan["blockers"]]
    assert "Reading Club" not in response.text
    confirmation = reviewed(as_user("asha"), request)
    assert as_user("asha").post("/admin/changes/apply", json=confirmation).status_code == 422
    assert grants(db_factory, ids["users"]["ben"])


def test_positions_held_outside_the_branch_block_ending_them(as_user, ids, db_factory, settings):
    appoint(db_factory, ids, "asha", "section_a")
    with db_factory() as db:
        db.add(
            UnitPosition(
                workspace_id=ids["workspaces"]["section_b"],
                user_id=ids["users"]["ben"],
                position="deputy",
                starts_on=site_today(settings) - timedelta(days=1),
            )
        )
        db.commit()
    plan = preview(as_user("asha"), change(ids, "suspend", person_id="ben")).json()
    assert "outside_your_units" in [blocker["code"] for blocker in plan["blockers"]]
    assert "Catalysis" not in str(plan["steps"])


def test_review_text_never_names_what_the_actor_cannot_see(ids, db_factory):
    division, section = (uuid.UUID(ids["workspaces"][key]) for key in ("division", "section_a"))
    plan = Plan(
        kind="transfer",
        actor_id="x",
        request=Snapshot({}),
        revisions=Snapshot({}),
        steps=(
            Step(
                "workspace",
                str(division),
                "Remove Ben from Surface Science Division",
                Snapshot({"role": "member"}),
                Snapshot({"role": None}),
            ),
        ),
        warnings=(Warning("access_lost", "Ben cannot read Surface Science Division.", str(division)),),
    )
    with db_factory() as db:
        actor = db.get(User, ids["users"]["asha"])
        reach = Reach(actor, frozenset({section}), {section: division, division: None})
        request = type("Req", (), {"kind": "transfer", "person_id": None})()
        shown = reach.restrict(db, request, plan)
    assert "Surface Science" not in str(shown.to_dict())
    assert [blocker.code for blocker in shown.blockers] == ["outside_your_units"]


# --- scope read at apply and at the scheduled run ----------------------------------------------


def test_plan_previewed_in_scope_is_refused_after_the_role_is_withdrawn(division_admin, ids, db_factory):
    confirmation = reviewed(division_admin, move(ids, "ben", "section_b"))
    withdraw(db_factory, ids, "dana", "division")
    assert division_admin.post("/admin/changes/apply", json=confirmation).status_code == 403
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_a"]


def test_plan_previewed_in_scope_is_refused_after_the_scope_narrows(division_admin, ids, db_factory):
    confirmation = reviewed(division_admin, move(ids, "ben", "section_b"))
    appoint(db_factory, ids, "dana", "section_b")
    withdraw(db_factory, ids, "dana", "division")
    response = division_admin.post("/admin/changes/apply", json=confirmation)
    assert response.status_code == 404
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_a"]


def test_bulk_changes_are_held_to_the_branch(division_admin, ids):
    inside = {
        "kind": "transfer",
        "person_id": ids["users"]["ben"],
        "to_unit_id": ids["workspaces"]["section_b"],
        "role": "member",
    }
    outside = {"kind": "suspend", "person_id": ids["users"]["eli"]}
    assert division_admin.post("/admin/changes/bulk/preview", json={"requests": [inside]}).status_code == 200
    assert (
        division_admin.post("/admin/changes/bulk/preview", json={"requests": [inside, outside]}).status_code
        == 404
    )


def test_activation_codes_only_for_people_of_the_branch(division_admin, as_user, ids, db_factory):
    body = {
        "kind": "add_person",
        "username": "newcomer",
        "display_name": "New Comer",
        "role": "member",
        "home_unit_id": ids["workspaces"]["section_a"],
    }
    receipt = apply_reviewed(division_admin, {"request": body}).json()
    path = "/admin/changes/activation-code"
    ok = division_admin.post(path, json={"person_id": receipt["person_id"], "reason": "Lost the slip"})
    assert ok.status_code == 200
    out = division_admin.post(path, json={"person_id": ids["users"]["eli"], "reason": "Lost the slip"})
    assert out.status_code == 404


def test_scheduled_changes_list_cancel_and_run_within_current_reach(
    division_admin, as_user, ids, db_factory, settings
):
    appoint(db_factory, ids, "chen", "section_b")
    day = site_today(settings) + timedelta(days=1)
    body = {**move(ids, "ben", "section_b"), "effective_on": day.isoformat()}
    scheduled_id = division_admin.post(
        "/admin/changes/apply", json=reviewed_for(division_admin, body)
    ).json()["id"]
    assert len(division_admin.get("/admin/changes/scheduled").json()["items"]) == 1
    chen = as_user("chen")
    assert chen.get("/admin/changes/scheduled").json()["items"] == []
    assert chen.delete(f"/admin/changes/scheduled/{scheduled_id}?reason=Not%20mine").status_code == 404
    # The scope is judged again on the day: with the appointment withdrawn nothing is applied.
    withdraw(db_factory, ids, "dana", "division")
    assert run(db_factory, settings, day) == 0
    with db_factory() as db:
        row = db.get(ScheduledChange, scheduled_id)
        assert row.state == "needs_review" and row.applied_at is None
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_a"]


def test_scheduled_change_runs_when_scope_still_holds(division_admin, ids, db_factory, settings):
    day = site_today(settings) + timedelta(days=1)
    body = {**move(ids, "ben", "section_b"), "effective_on": day.isoformat()}
    assert (
        division_admin.post("/admin/changes/apply", json=reviewed_for(division_admin, body)).status_code
        == 200
    )
    assert run(db_factory, settings, day) == 1
    assert home(db_factory, ids, "ben") == ids["workspaces"]["section_b"]


# --- no content access from the role ------------------------------------------------------------


def test_the_role_gives_no_content_access(as_user, ids, db_factory):
    appoint(db_factory, ids, "chen", "section_a")  # Chen is a member of Catalysis only
    chen = as_user("chen")
    section = ids["workspaces"]["section_a"]
    for path in ("posts", "chat", "board", "members"):
        assert chen.get(f"/workspaces/{section}/{path}").status_code == 404, path
    assert chen.get(f"/workspaces/{section}").status_code == 404
    # Review text and lists carry people and unit names, never message or post text.
    assert "Reading Club" not in chen.get("/admin/people").text


def test_every_request_field_that_names_something_is_checked_or_deliberately_skipped():
    from labadda.changes.requests import PreviewRequest
    from labadda.changes.unit_scope import INSIDE_FIELDS, PERSON_FIELDS, STEP_CHECKED, UNIT_FIELDS

    known = {*PERSON_FIELDS, *UNIT_FIELDS, *INSIDE_FIELDS, *STEP_CHECKED, "person_ids"}
    union = PreviewRequest.model_fields["request"].annotation
    models = union.__args__[0].__args__ if hasattr(union.__args__[0], "__args__") else union.__args__
    for model in models:
        for field in model.model_fields:
            if field.endswith(("_id", "_ids")):
                assert field in known, f"{model.__name__}.{field} is not scope-checked"


def test_policy_scope_matches_the_appointment_now(ids, db_factory):
    appoint(db_factory, ids, "dana", "division")
    with db_factory() as db:
        dana = db.get(User, ids["users"]["dana"])
        assert len(policy.people_scope(db, dana)) == 3


def test_appointments_are_listed_for_site_administrators_only(division_admin, as_user, ids):
    listing = as_user("admin").get("/admin/org/unit-admins")
    assert listing.status_code == 200
    (item,) = listing.json()["items"]
    assert item["person"]["name"] == "Dana Whitfield" and item["unit"]["name"] == "Surface Science Division"
    assert division_admin.get("/admin/org/unit-admins").status_code == 403
    assert as_user("ben").get("/admin/org/unit-admins").status_code == 403
