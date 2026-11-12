"""P4 reviewed unit changes: create, rename, move, merge, split, close, reopen and their guards."""

import pytest
from sqlalchemy import select

from labadda.models import AuditEvent, Membership, UnitPosition, User, Workspace
from tests.test_changes_edit import reviewed
from tests.test_changes_transfer import TASK_TITLE, assign_tasks, codes, preview
from tests.test_panel import pair

SPLIT = {"name": "Sensors Section", "code": "SSD-SE", "acknowledge_no_steward": True}


def req(ids, kind, **fields):
    """Replace unit keys by their fixture ids; anything else stays as written."""
    keyed = {
        key: ids["workspaces"].get(value, value) if isinstance(value, str) else value
        for key, value in fields.items()
    }
    for key in ("person_ids",):
        if key in fields:
            keyed[key] = [ids["users"][name] for name in fields[key]]
    if fields.get("head_id"):
        keyed["head_id"] = ids["users"][fields["head_id"]]
    return {"request": {"kind": kind, **keyed}}


def apply(admin, request):
    response = admin.post("/admin/changes/apply", json=reviewed(admin, request))
    assert response.status_code == 200, response.text
    return response.json()


def split_sensors(admin, ids, people=("ben",)):
    request = req(ids, "unit_split", unit_id="section_a", person_ids=list(people), **SPLIT)
    receipt = apply(admin, request)
    ids["workspaces"]["sensors"] = receipt["unit_id"]
    return receipt


def readable(client, ids):
    return {
        key
        for key, space in ids["workspaces"].items()
        if client.get(f"/workspaces/{space}").status_code == 200
    }


def test_scenario_split_moves_chosen_people_into_a_new_sibling(as_user, ids, db_factory):
    admin = as_user("admin")
    plan = preview(admin, req(ids, "unit_split", unit_id="section_a", person_ids=["ben"], **SPLIT))
    assert plan["blockers"] == []
    assert plan["steps"][0]["summary"].startswith("Create the unit Sensors Section (SSD-SE) under")
    assert "access_lost" in codes(plan["warnings"])
    assert db_factory().scalar(select(Workspace).where(Workspace.code == "SSD-SE")) is None
    split_sensors(admin, ids)
    with db_factory() as db:
        unit = db.get(Workspace, ids["workspaces"]["sensors"])
        assert (unit.kind, unit.code, str(unit.parent_id)) == ("org", "SSD-SE", ids["workspaces"]["division"])
        ben = db.get(User, ids["users"]["ben"])
        assert ben.home_workspace_id == unit.id
        roles = {
            m.workspace_id: m.role for m in db.scalars(select(Membership).where(Membership.user_id == ben.id))
        }
        assert roles[unit.id] == "member" and ids["workspaces"]["section_a"] not in map(str, roles)
        records = db.scalars(select(AuditEvent).where(AuditEvent.action.like("people.change%"))).all()
        parent = next(row for row in records if row.action == "people.change")
        assert (parent.scope_type, parent.scope_id) == ("workspace", str(unit.id))
        assert parent.detail["kind"] == "unit_split" and parent.reason == "Annual staff review"
        assert len(records) > 3
    ben = as_user("ben")
    assert ben.get(f"/workspaces/{unit.id}").status_code == 200
    assert ben.get(f"/workspaces/{ids['workspaces']['section_a']}").status_code == 404
    assert as_user("asha").get(f"/workspaces/{unit.id}").status_code == 404
    assert admin.get(f"/workspaces/{unit.id}").status_code == 404


def test_scenario_merge_archives_source_and_keeps_history_readable(as_user, ids, db_factory):
    admin = as_user("admin")
    split_sensors(admin, ids)
    plan = preview(admin, req(ids, "unit_merge", unit_id="section_a", into_unit_id="sensors"))
    assert plan["blockers"] == [] and plan["affected_people"] == 1
    assert "history_kept" in codes(plan["warnings"])
    apply(admin, req(ids, "unit_merge", unit_id="section_a", into_unit_id="sensors"))
    with db_factory() as db:
        source = db.get(Workspace, ids["workspaces"]["section_a"])
        assert source.archived and source.code == "TFS"
        asha = db.get(User, ids["users"]["asha"])
        assert str(asha.home_workspace_id) == ids["workspaces"]["sensors"]
        assert (
            db.scalar(
                select(Membership.role).where(
                    Membership.user_id == asha.id, Membership.workspace_id == ids["workspaces"]["sensors"]
                )
            )
            == "member"
        )
    asha = as_user("asha")
    assert asha.get(f"/workspaces/{ids['workspaces']['section_a']}").status_code == 200  # history stays
    assert asha.get(f"/workspaces/{ids['workspaces']['sensors']}").status_code == 200


def test_merge_ends_positions_and_reparents_sub_units(as_user, ids, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        child = Workspace(
            kind="org", name="Coatings Lab", code="TFS-CL", parent_id=ids["workspaces"]["section_a"]
        )
        db.add(child)
        db.flush()
        db.add(
            UnitPosition(
                workspace_id=ids["workspaces"]["section_a"],
                user_id=ids["users"]["asha"],
                position="deputy",
                starts_on="2026-01-05",
            )
        )
        db.commit()
        child_id = str(child.id)
    request = req(ids, "unit_merge", unit_id="section_a", into_unit_id="section_b")
    apply(admin, request)
    with db_factory() as db:
        assert str(db.get(Workspace, child_id).parent_id) == ids["workspaces"]["section_b"]
        assert (
            db.scalar(
                select(UnitPosition).where(
                    UnitPosition.ended_at.is_(None),
                    UnitPosition.workspace_id == ids["workspaces"]["section_a"],
                )
            )
            is None
        )


def test_move_counts_match_real_reads_for_the_moved_branch(as_user, ids, db_factory):
    with db_factory() as db:
        optics = Workspace(
            kind="org", name="Optics Division", code="OPT", parent_id=ids["workspaces"]["root"]
        )
        db.add(optics)
        db.flush()
        lasers = Workspace(kind="org", name="Lasers Section", code="OPT-LA", parent_id=optics.id)
        db.add(lasers)
        db.flush()
        db.add(Membership(user_id=ids["users"]["chen"], workspace_id=lasers.id, role="member"))
        db.commit()
        ids["workspaces"].update(optics=str(optics.id), lasers=str(lasers.id))
    admin, chen = as_user("admin"), as_user("chen")
    request = req(ids, "unit_move", unit_id="lasers", new_parent_id="section_a")
    plan = preview(admin, request)
    gained = {
        item["target_id"]: item["count"] for item in plan["warnings"] if item["code"] == "access_gained"
    }
    lost = {item["target_id"]: item["count"] for item in plan["warnings"] if item["code"] == "access_lost"}
    assert lost == {ids["workspaces"]["optics"]: 1} and gained == {ids["workspaces"]["section_a"]: 1}
    before = readable(chen, ids)
    apply(admin, request)
    after = readable(chen, ids)
    assert after - before == {"section_a"} and before - after == {"optics"}


@pytest.mark.parametrize(
    ("kind", "fields", "code"),
    [
        ("unit_move", {"unit_id": "division", "new_parent_id": "section_a"}, "cycle"),
        ("unit_move", {"unit_id": "division", "new_parent_id": "division"}, "cycle"),
        ("unit_move", {"unit_id": "root", "new_parent_id": "section_a"}, "root_fixed"),
        ("unit_move", {"unit_id": "section_a", "new_parent_id": "division"}, "same_parent"),
        ("unit_move", {"unit_id": "section_a", "new_parent_id": "project"}, "unit_unavailable"),
        ("unit_merge", {"unit_id": "root", "into_unit_id": "division"}, "root_fixed"),
        ("unit_merge", {"unit_id": "division", "into_unit_id": "section_a"}, "cycle"),
        ("unit_merge", {"unit_id": "section_a", "into_unit_id": "section_a"}, "same_unit"),
        ("unit_close", {"unit_id": "root"}, "root_fixed"),
        ("unit_close", {"unit_id": "section_a"}, "unit_has_people"),
        ("unit_close", {"unit_id": "division"}, "unit_has_subunits"),
        ("unit_reopen", {"unit_id": "section_a"}, "no_change"),
        ("unit_rename", {"unit_id": "section_a", "code": "CS"}, "duplicate_code"),
        ("unit_rename", {"unit_id": "section_a", "code": "TFS"}, "no_change"),
        ("unit_split", {"unit_id": "root", "name": "X", "code": "XX", "person_ids": ["ben"]}, "root_fixed"),
        (
            "unit_split",
            {"unit_id": "section_a", "name": "X", "code": "SSD", "person_ids": ["ben"]},
            "duplicate_code",
        ),
        (
            "unit_split",
            {"unit_id": "section_a", "name": "X", "code": "XX", "person_ids": ["chen"]},
            "person_not_in_unit",
        ),
        ("unit_create", {"parent_id": "project", "name": "X", "code": "XX"}, "unit_unavailable"),
        ("unit_create", {"parent_id": "division", "name": "X", "code": "SSD"}, "duplicate_code"),
    ],
)
def test_blockers(kind, fields, code, as_user, ids):
    plan = preview(as_user("admin"), req(ids, kind, **fields))
    assert code in codes(plan["blockers"])
    response = as_user("admin").post(
        "/admin/changes/apply",
        json={
            **req(ids, kind, **fields),
            "digest": plan["digest"],
            "revisions": plan["revisions"],
            "reason": "Trying it",
        },
    )
    assert response.status_code == 422


def test_splitting_off_the_last_steward_needs_acknowledgement(as_user, ids):
    request = req(ids, "unit_split", unit_id="section_a", person_ids=["asha"], name="Sensors", code="SSD-SE")
    plan = preview(as_user("admin"), request)
    assert "unit_without_steward" in codes(plan["blockers"])
    acknowledged = {"request": {**request["request"], "acknowledge_no_steward": True}}
    assert preview(as_user("admin"), acknowledged)["blockers"] == []


def test_close_and_reopen_an_empty_unit_with_positions_ended(as_user, ids, db_factory):
    admin = as_user("admin")
    created = apply(
        admin, req(ids, "unit_create", parent_id="division", name="Optics Lab", code="SSD-OP", head_id="eli")
    )
    ids["workspaces"]["optics"] = created["unit_id"]
    request = req(ids, "unit_close", unit_id="optics")
    plan = preview(admin, request)
    assert plan["blockers"] == [] and "history_kept" in codes(plan["warnings"])
    apply(admin, request)
    with db_factory() as db:
        assert db.get(Workspace, created["unit_id"]).archived
        assert db.scalar(select(UnitPosition).where(UnitPosition.ended_at.is_(None))) is None
    assert as_user("eli").get(f"/workspaces/{created['unit_id']}").status_code == 200
    apply(admin, req(ids, "unit_reopen", unit_id="optics"))
    with db_factory() as db:
        assert not db.get(Workspace, created["unit_id"]).archived


def test_rename_and_recode_keep_the_unit_identity(as_user, ids, db_factory):
    admin = as_user("admin")
    apply(
        admin, req(ids, "unit_rename", unit_id="section_b", name="  Catalysis and Surfaces  ", code="ssd-cs")
    )
    with db_factory() as db:
        unit = db.get(Workspace, ids["workspaces"]["section_b"])
        assert (unit.name, unit.code) == ("Catalysis and Surfaces", "SSD-CS")
    assert as_user("chen").get(f"/workspaces/{unit.id}").json()["code"] == "SSD-CS"


def test_create_unit_with_head_makes_a_steward_and_a_head_position(as_user, ids, db_factory):
    admin = as_user("admin")
    request = req(ids, "unit_create", parent_id="division", name="Optics Lab", code="ssd-op", head_id="eli")
    plan = preview(admin, request)
    assert next(step["target_id"] for step in plan["steps"]) == "new:unit"
    receipt = apply(admin, request)
    with db_factory() as db:
        unit = db.get(Workspace, receipt["unit_id"])
        assert unit.code == "SSD-OP" and str(unit.parent_id) == ids["workspaces"]["division"]
        assert db.scalar(select(Membership.role).where(Membership.workspace_id == unit.id)) == "steward"
        head = db.scalar(select(UnitPosition).where(UnitPosition.workspace_id == unit.id))
        assert (head.position, str(head.user_id)) == ("head", ids["users"]["eli"])
    assert as_user("eli").get(f"/workspaces/{receipt['unit_id']}").status_code == 200
    assert admin.get(f"/workspaces/{receipt['unit_id']}").status_code == 404


def test_create_without_head_warns_and_inactive_head_is_blocked(as_user, ids):
    admin = as_user("admin")
    plain = preview(admin, req(ids, "unit_create", parent_id="division", name="Optics Lab", code="SSD-OP"))
    assert "unit_without_steward" in codes(plain["warnings"])
    gone = preview(
        admin, req(ids, "unit_create", parent_id="division", name="Optics Lab", code="SSD-OP", head_id="fay")
    )
    assert "holder_inactive" in codes(gone["blockers"])


def test_unit_plans_carry_no_content(as_user, ids, db_factory):
    assign_tasks(as_user, ids, db_factory)
    request = req(ids, "unit_split", unit_id="section_a", person_ids=["ben"], **SPLIT)
    text = as_user("admin").post("/admin/changes/preview", json=request).text
    assert TASK_TITLE not in text and "open_tasks" in text


def test_stale_review_after_a_concurrent_change_writes_nothing(as_user, ids, db_factory):
    admin = as_user("admin")
    confirmation = reviewed(admin, req(ids, "unit_rename", unit_id="section_b", name="Catalysis Lab"))
    with db_factory() as db:
        db.get(Workspace, ids["workspaces"]["section_b"]).name = "Catalysis Team"
        db.commit()
    assert admin.post("/admin/changes/apply", json=confirmation).status_code == 409
    with db_factory() as db:
        assert db.get(Workspace, ids["workspaces"]["section_b"]).name == "Catalysis Team"


KINDS = [
    ("unit_create", {"parent_id": "division", "name": "Optics Lab", "code": "SSD-OP"}),
    ("unit_rename", {"unit_id": "section_b", "name": "Other"}),
    ("unit_move", {"unit_id": "section_b", "new_parent_id": "group"}),
    ("unit_merge", {"unit_id": "section_b", "into_unit_id": "section_a"}),
    ("unit_split", {"unit_id": "section_a", "name": "X", "code": "XX", "person_ids": ["ben"]}),
    ("unit_close", {"unit_id": "section_b"}),
    ("unit_reopen", {"unit_id": "section_b"}),
]


@pytest.mark.parametrize(("kind", "fields"), KINDS)
@pytest.mark.parametrize("username", ["asha", "ben", "chen", "dana", "eli"])
def test_members_and_stewards_cannot_change_units(kind, fields, username, as_user, ids):
    request = req(ids, kind, **fields)
    assert as_user(username).post("/admin/changes/preview", json=request).status_code == 403
    assert as_user(username).post("/admin/changes/apply", json=request).status_code == 403


def test_deactivated_signed_out_and_panel_callers_are_refused(as_user, ids, make_client, db_factory):
    request = req(ids, "unit_rename", unit_id="section_b", name="Other")
    assert make_client().post("/admin/changes/preview", json=request).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/preview", json=request).status_code == 401
    admin = as_user("admin")
    with db_factory() as db:
        db.get(User, ids["users"]["admin"]).is_active = False
        db.commit()
    assert admin.post("/admin/changes/preview", json=request).status_code in (401, 403)


def test_unknown_unit_is_a_uniform_404(as_user, ids):
    request = req(ids, "unit_rename", unit_id=ids["users"]["ben"], name="Other")
    assert as_user("admin").post("/admin/changes/preview", json=request).status_code == 404
