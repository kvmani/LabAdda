"""P4 chart data: shape, counts, Head and steward names, and no content or access for others."""

import pytest

from tests.test_changes_transfer import TASK_TITLE, assign_tasks
from tests.test_changes_units import apply, req
from tests.test_panel import pair


def by_id(items):
    return {item["id"]: item for item in items}


def test_tree_lists_units_with_codes_counts_and_stewards(as_user, ids):
    body = as_user("admin").get("/admin/org/tree").json()
    units = by_id(body["units"])
    thin = units[ids["workspaces"]["section_a"]]
    assert (thin["code"], thin["name"], thin["archived"]) == ("TFS", "Thin Films Section", False)
    assert thin["parent_id"] == ids["workspaces"]["division"]
    assert (thin["people"], thin["members"]) == (2, 3)  # Asha and Bharat at home; Farhan is a member only
    assert [person["name"] for person in thin["stewards"]] == ["Asha Rao"]
    assert units[ids["workspaces"]["root"]]["parent_id"] is None
    spaces = by_id(body["spaces"])
    club = spaces[ids["workspaces"]["reading_club"]]
    assert (club["kind"], club["members"], [s["name"] for s in club["stewards"]]) == (
        "group",
        2,
        ["Bharat Kulkarni"],
    )
    assert ids["workspaces"]["project"] in spaces and ids["workspaces"]["project"] not in units


def test_tree_shows_head_and_archived_units(as_user, ids):
    admin = as_user("admin")
    created = apply(
        admin, req(ids, "unit_create", parent_id="division", name="Optics Lab", code="SED-OP", head_id="esha")
    )
    unit = by_id(admin.get("/admin/org/tree").json()["units"])[created["unit_id"]]
    assert unit["head"]["name"] == "Esha Menon" and unit["acting_head"] is None
    apply(admin, req(ids, "unit_close", unit_id=created["unit_id"]))
    unit = by_id(admin.get("/admin/org/tree").json()["units"])[created["unit_id"]]
    assert unit["archived"] and unit["head"] is None


def test_tree_carries_no_content(as_user, ids, db_factory):
    assign_tasks(as_user, ids, db_factory)
    text = as_user("admin").get("/admin/org/tree").text
    assert TASK_TITLE not in text and "Recognisable" not in text


@pytest.mark.parametrize("username", ["asha", "bharat", "chitra", "deepa", "esha"])
def test_members_and_stewards_cannot_read_the_tree(username, as_user):
    assert as_user(username).get("/admin/org/tree").status_code == 403


def test_signed_out_and_panel_cannot_read_the_tree(as_user, ids, make_client):
    assert make_client().get("/admin/org/tree").status_code == 401
    assert pair(as_user, make_client, ids).get("/admin/org/tree").status_code == 401


def test_deactivated_administrator_is_refused(as_user, ids, db_factory):
    from labadda.models import User

    admin = as_user("admin")
    with db_factory() as db:
        db.get(User, ids["users"]["admin"]).is_active = False
        db.commit()
    assert admin.get("/admin/org/tree").status_code in (401, 403)
