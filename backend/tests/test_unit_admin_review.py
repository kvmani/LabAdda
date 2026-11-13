"""P7 review: what a unit administrator's reviews, lists and candidates must not reveal or grant."""

from datetime import timedelta

import pytest

from labadda.models import Membership
from tests.test_changes_authority import change, site_today
from tests.test_changes_edit import reviewed
from tests.test_changes_scheduled import reviewed_for
from tests.unit_admin_support import appoint, preview


def codes(plan):
    return [item["code"] for item in plan["blockers"]]


def test_similar_name_warning_never_names_people_outside_the_branch(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    request = change(
        ids,
        "add_person",
        username="newcomer",
        display_name="Esha Menon",
        role="member",
        home_unit_id="section_a",
    )
    shown = preview(as_user("asha"), request)
    assert shown.status_code == 200
    assert shown.json()["warnings"] == []
    # A site administrator still gets the duplicate warning.
    assert "Esha Menon (esha)" in preview(as_user("admin"), request).text


def test_reinstate_review_does_not_list_places_outside_the_branch(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    with db_factory() as db:
        project = ids["workspaces"]["project"]
        db.add(Membership(user_id=ids["users"]["bharat"], workspace_id=project, role="member"))
        db.commit()
    admin = as_user("admin")
    suspend = reviewed(admin, change(ids, "suspend", person_id="bharat"))
    assert admin.post("/admin/changes/apply", json=suspend).status_code == 200
    shown = preview(as_user("asha"), change(ids, "reinstate", person_id="bharat"))
    assert shown.status_code == 200
    for text in ("Reading Club", "Tejas"):
        assert text not in shown.text


def test_scheduled_list_hides_changes_whose_text_reaches_outside_the_branch(
    as_user, ids, db_factory, settings
):
    appoint(db_factory, ids, "deepa", "division")
    admin = as_user("admin")
    day = (site_today(settings) + timedelta(days=1)).isoformat()
    body = {**change(ids, "retire", person_id="chitra", status="left"), "effective_on": day}
    assert admin.post("/admin/changes/apply", json=reviewed_for(admin, body)).status_code == 200
    shown = as_user("deepa").get("/admin/changes/scheduled")
    assert shown.status_code == 200
    assert "Reading Club" not in shown.text


def test_candidates_leave_out_site_administrators_and_people_homed_elsewhere(as_user, ids, db_factory):
    appoint(db_factory, ids, "asha", "section_a")
    with db_factory() as db:
        for name in ("admin", "esha"):
            unit = ids["workspaces"]["section_a"]
            db.add(Membership(user_id=ids["users"][name], workspace_id=unit, role="member"))
        db.commit()
    path = f"/admin/changes/candidates?workspace_id={ids['workspaces']['section_a']}"
    listed = [row["username"] for row in as_user("asha").get(path).json()["people"]]
    assert "admin" not in listed and "esha" not in listed and "bharat" in listed
    assert "admin" in [row["username"] for row in as_user("admin").get(path).json()["people"]]


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("additional_charge", {"workspace_id": "section_a", "role": "member"}),
        ("transfer", {"to_unit_id": "section_a", "role": "member"}),
        ("promote", {"workspace_id": "section_a", "role": "steward"}),
    ],
)
def test_unit_administrator_cannot_give_themselves_access_to_a_unit(as_user, ids, db_factory, kind, fields):
    appoint(db_factory, ids, "deepa", "division")
    plan = preview(as_user("deepa"), change(ids, kind, person_id="deepa", **fields)).json()
    assert "self_access" in codes(plan)
