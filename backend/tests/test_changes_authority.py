"""T56 positions and authority: promotion, change of head, acting appointments, additional charges."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from labadda import people, positions
from labadda.models import AuditEvent, Membership, UnitPosition, User
from tests.test_changes_edit import reviewed
from tests.test_changes_transfer import codes, grants, move, preview


def change(ids, kind, **fields):
    """A fictional request; ``*_id`` values that name fixture people or units are resolved."""
    resolved = {}
    for key, value in fields.items():
        named = key.endswith("_id") and isinstance(value, str)
        resolved[key] = (ids["users"].get(value) or ids["workspaces"].get(value) or value) if named else value
    return {"request": {"kind": kind, **resolved}}


def make_head(db_factory, ids, username="deepa", unit="division", **values):
    """Record a current position directly, as earlier reviewed changes would have."""
    with db_factory() as db:
        row = UnitPosition(
            workspace_id=ids["workspaces"][unit],
            user_id=ids["users"][username],
            position=values.pop("position", "head"),
            starts_on=date(2020, 1, 6),
            **values,
        )
        db.add(row)
        db.commit()
        return str(row.id)


def current_positions(db_factory, unit=None):
    with db_factory() as db:
        query = select(UnitPosition).where(UnitPosition.ended_at.is_(None))
        if unit is not None:
            query = query.where(UnitPosition.workspace_id == unit)
        return [(str(row.user_id), row.position, row.acting) for row in db.scalars(query)]


def apply(admin, request):
    response = admin.post("/admin/changes/apply", json=reviewed(admin, request))
    assert response.status_code == 200, response.text
    return response.json()


def site_today(settings):
    return people.site_date(settings)


def start_of(day: date, settings) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=ZoneInfo(settings.timezone))


def test_scenario_chitra_promoted_to_steward_of_corrosion(as_user, ids, db_factory):
    """Scenario step 3: a new designation and the steward role; the plan says moderation changes."""
    admin = as_user("admin")
    request = change(
        ids,
        "promote",
        person_id="chitra",
        designation="Scientific Officer D",
        workspace_id="section_b",
        role="steward",
    )
    plan = preview(admin, request)
    assert [step["summary"] for step in plan["steps"]] == [
        "Change the designation of Chitra Iyer to Scientific Officer D",
        "Set the role of Chitra Iyer in Corrosion Section to steward",
    ]
    assert codes(plan["warnings"]) == ["moderation_gained"]
    assert plan["blockers"] == [] and plan["affected_people"] == 1
    receipt = apply(admin, request)
    assert receipt["kind"] == "promote"
    assert grants(db_factory, ids["users"]["chitra"])[ids["workspaces"]["section_b"]] == "steward"
    profile = admin.get(f"/admin/people/{ids['users']['chitra']}").json()
    assert profile["designation"] == "Scientific Officer D"
    assert profile["revision"] == receipt["revision"]


def test_promote_blockers(as_user, ids, db_factory):
    admin = as_user("admin")
    outside = preview(
        admin, change(ids, "promote", person_id="chitra", workspace_id="section_a", role="steward")
    )
    assert codes(outside["blockers"]) == ["not_a_member"]
    same = preview(admin, change(ids, "promote", person_id="asha", workspace_id="section_a", role="steward"))
    assert codes(same["blockers"]) == ["no_changes"]
    last = preview(admin, change(ids, "promote", person_id="asha", workspace_id="section_a", role="member"))
    assert "unit_without_steward" in codes(last["blockers"])
    make_head(db_factory, ids)
    held = preview(admin, change(ids, "promote", person_id="deepa", workspace_id="division", role="member"))
    assert "holds_position" in codes(held["blockers"])
    head = preview(
        admin,
        change(ids, "promote", person_id="asha", workspace_id="division", role="steward", position="head"),
    )
    assert "not_a_member" in codes(head["blockers"]) and "unit_has_head" in codes(head["blockers"])


def test_promote_to_vacant_deputy_records_position(as_user, ids, db_factory):
    admin = as_user("admin")
    request = change(
        ids, "promote", person_id="bharat", workspace_id="section_a", role="steward", position="deputy"
    )
    plan = preview(admin, request)
    assert plan["steps"][-1]["summary"] == "Appoint Bharat Kulkarni as Deputy of Thin Films Section"
    apply(admin, request)
    assert current_positions(db_factory) == [(ids["users"]["bharat"], "deputy", False)]
    profile = admin.get(f"/admin/people/{ids['users']['bharat']}").json()
    assert [(item["workspace"]["name"], item["position"]) for item in profile["positions"]] == [
        ("Thin Films Section", "deputy")
    ]
    listed = admin.get("/admin/people?q=bharat").json()["people"][0]
    assert listed["positions"][0]["position"] == "deputy"


@pytest.mark.parametrize(
    "fields",
    [
        {"designation": "x" * 121},
        {"role": "steward"},
        {"workspace_id": "section_a", "role": "steward", "position": "deputy", "extra": True},
        {"workspace_id": "section_a", "role": "member", "position": "head"},
    ],
)
def test_promote_bounds(fields, as_user, ids):
    request = change(ids, "promote", person_id="bharat", **fields)
    assert as_user("admin").post("/admin/changes/preview", json=request).status_code == 422


def test_change_of_head_replaces_head_and_successor_becomes_steward(as_user, ids, db_factory):
    make_head(db_factory, ids)
    admin = as_user("admin")
    request = change(
        ids,
        "change_authority",
        workspace_id="division",
        position="head",
        successor_id="asha",
        outgoing_role="member",
    )
    plan = preview(admin, request)
    assert [step["summary"] for step in plan["steps"]] == [
        "End the position of Deepa Nair as Head of Surface Engineering Division",
        "Set the role of Deepa Nair in Surface Engineering Division to member",
        "Add Asha Rao to Surface Engineering Division as steward",
        "Appoint Asha Rao as Head of Surface Engineering Division",
    ]
    assert plan["affected_people"] == 2 and plan["revisions"] == {ids["users"]["asha"]: 1}
    apply(admin, request)
    division = ids["workspaces"]["division"]
    assert current_positions(db_factory, division) == [(ids["users"]["asha"], "head", False)]
    assert grants(db_factory, ids["users"]["deepa"])[division] == "member"
    assert grants(db_factory, ids["users"]["asha"])[division] == "steward"
    with db_factory() as db:
        actions = db.scalars(select(AuditEvent.action).where(AuditEvent.action.like("position.%"))).all()
        assert sorted(actions) == ["position.appoint", "position.end"]


def test_one_current_head_per_unit_is_enforced_by_the_database(db_factory, ids):
    make_head(db_factory, ids)
    with pytest.raises(IntegrityError):
        make_head(db_factory, ids, username="asha")
    make_head(db_factory, ids, username="asha", acting=True, ends_on=date(2020, 3, 1), revert_role="none")
    with pytest.raises(IntegrityError):
        make_head(
            db_factory, ids, username="bharat", acting=True, ends_on=date(2020, 3, 1), revert_role="none"
        )


def test_change_authority_blockers(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    make_head(db_factory, ids)
    cases = {
        "holder_outside_unit": change(
            ids, "change_authority", workspace_id="section_a", position="head", successor_id="chitra"
        ),
        "holder_inactive": change(
            ids, "change_authority", workspace_id="section_a", position="head", successor_id="farhan"
        ),
        "already_holds": change(
            ids, "change_authority", workspace_id="division", position="head", successor_id="deepa"
        ),
        "unit_unavailable": change(
            ids, "change_authority", workspace_id="project", position="head", successor_id="esha"
        ),
        "invalid_date": change(
            ids,
            "change_authority",
            workspace_id="division",
            position="head",
            successor_id="asha",
            acting=True,
            ends_on=site_today(settings).isoformat(),
        ),
        "not_a_deputy": change(
            ids,
            "change_authority",
            workspace_id="section_a",
            position="deputy",
            successor_id="bharat",
            replace_person_id="asha",
        ),
    }
    for code, request in cases.items():
        assert code in codes(preview(admin, request)["blockers"]), code
        assert admin.post("/admin/changes/apply", json=reviewed(admin, request)).status_code == 422


def test_acting_head_expires_on_its_date_and_role_reverts(as_user, ids, db_factory, settings):
    """T56: the acting appointment ends at the start of its end date under an injected clock."""
    admin = as_user("admin")
    ends = site_today(settings) + timedelta(days=30)
    request = change(
        ids,
        "change_authority",
        workspace_id="section_a",
        position="head",
        successor_id="bharat",
        acting=True,
        ends_on=ends.isoformat(),
    )
    plan = preview(admin, request)
    assert plan["steps"][-1]["after"] == {
        "position": "acting Head",
        "unit": "Thin Films Section",
        "ends_on": ends.isoformat(),
        "returns_to": "member",
    }
    apply(admin, request)
    section = ids["workspaces"]["section_a"]
    assert grants(db_factory, ids["users"]["bharat"])[section] == "steward"
    with db_factory() as db:
        assert positions.expire_due(db, settings, now=start_of(ends, settings) - timedelta(seconds=1)) == 0
        assert positions.expire_due(db, settings, now=start_of(ends, settings)) == 1
        assert positions.expire_due(db, settings, now=start_of(ends, settings)) == 0
    assert current_positions(db_factory, section) == []
    assert grants(db_factory, ids["users"]["bharat"])[section] == "member"
    with db_factory() as db:
        row = db.scalar(select(UnitPosition))
        assert (row.end_reason, row.acting) == ("expired", True)
        expired = db.scalar(select(AuditEvent).where(AuditEvent.action == "position.expire"))
        assert expired.actor_id is None and expired.target_id == ids["users"]["bharat"]


def test_expiry_job_runs_from_the_scheduler(ids, db_factory, settings):
    with db_factory() as db:
        db.add(
            UnitPosition(
                workspace_id=ids["workspaces"]["section_b"],
                user_id=ids["users"]["chitra"],
                position="charge",
                starts_on=date(2020, 1, 6),
                ends_on=date(2020, 2, 6),
                revert_role="none",
            )
        )
        db.commit()
    job = positions.expiry_job(db_factory, settings)
    assert job.__name__ == "expire_positions"
    job()
    assert ids["workspaces"]["section_b"] not in grants(db_factory, ids["users"]["chitra"])
    job()


def test_additional_charge_with_end_date_is_removed_automatically(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    ends = site_today(settings) + timedelta(days=10)
    request = change(
        ids,
        "additional_charge",
        person_id="chitra",
        workspace_id="section_a",
        role="member",
        ends_on=ends.isoformat(),
    )
    plan = preview(admin, request)
    assert [step["summary"] for step in plan["steps"]] == [
        "Add Chitra Iyer to Thin Films Section as member",
        f"Appoint Chitra Iyer as Additional charge of Thin Films Section until {ends.isoformat()}",
    ]
    assert codes(plan["warnings"]) == ["access_gained", "ends_automatically"]
    apply(admin, request)
    chitra = as_user("chitra")
    section = ids["workspaces"]["section_a"]
    assert chitra.get(f"/workspaces/{section}").status_code == 200
    with db_factory() as db:
        assert positions.expire_due(db, settings, now=start_of(ends, settings)) == 1
    assert chitra.get(f"/workspaces/{section}").status_code == 404
    assert grants(db_factory, ids["users"]["chitra"]) == {
        ids["workspaces"]["section_b"]: "member",
        ids["workspaces"]["reading_club"]: "member",
    }


def test_additional_charge_blockers(as_user, ids, db_factory):
    admin = as_user("admin")
    make_head(db_factory, ids, username="asha", unit="section_a")
    cases = [
        ("same_unit", {"person_id": "bharat", "workspace_id": "section_a", "role": "member"}),
        ("already_member", {"person_id": "chitra", "workspace_id": "reading_club", "role": "member"}),
        ("unit_unavailable", {"person_id": "chitra", "workspace_id": "project", "role": "member"}),
        ("person_inactive", {"person_id": "farhan", "workspace_id": "section_b", "role": "member"}),
        (
            "unit_has_head",
            {"person_id": "chitra", "workspace_id": "section_a", "role": "steward", "position": "head"},
        ),
    ]
    for code, fields in cases:
        assert code in codes(preview(admin, change(ids, "additional_charge", **fields))["blockers"]), code


def test_transfer_ends_positions_in_the_unit_left(as_user, ids, db_factory):
    """PO-12: a Head who transfers out stops being Head; the plan says so before apply."""
    make_head(db_factory, ids, username="asha", unit="section_a")
    admin = as_user("admin")
    request = move(ids, person="asha", acknowledge_no_steward=True)
    plan = preview(admin, request)
    summaries = [step["summary"] for step in plan["steps"]]
    assert summaries[1] == "End the position of Asha Rao as Head of Thin Films Section"
    assert "unit_without_head" in codes(plan["warnings"])
    apply(admin, request)
    assert current_positions(db_factory) == []
    with db_factory() as db:
        assert db.scalar(select(func.count()).where(AuditEvent.action == "position.end")) == 1


def test_transfer_keeping_steward_role_keeps_the_position(as_user, ids, db_factory):
    make_head(db_factory, ids, username="asha", unit="section_a")
    admin = as_user("admin")
    request = move(ids, person="asha", keep_previous=True)
    plan = preview(admin, request)
    assert "unit_without_head" not in codes(plan["warnings"])
    apply(admin, request)
    assert current_positions(db_factory) == [(ids["users"]["asha"], "head", False)]


def test_legacy_demotion_ends_the_position(as_user, ids, db_factory):
    """A Head is always a steward: any membership write that demotes or removes ends the position."""
    make_head(db_factory, ids)
    admin = as_user("admin")
    body = {"user_id": ids["users"]["deepa"], "role": "member"}
    assert (
        admin.put(f"/admin/workspaces/{ids['workspaces']['division']}/memberships", json=body).status_code
        == 200
    )
    assert current_positions(db_factory) == []
    with db_factory() as db:
        assert (
            db.scalar(select(Membership.role).where(Membership.user_id == ids["users"]["deepa"])) is not None
        )
        assert db.get(User, ids["users"]["deepa"]).is_active


def test_candidates_are_active_people_of_the_unit_or_group_members(as_user, ids, make_client):
    admin = as_user("admin")
    division = admin.get(f"/admin/changes/candidates?workspace_id={ids['workspaces']['division']}").json()
    assert [(item["display_name"], item["role"]) for item in division["people"]] == [
        ("Asha Rao", None),
        ("Bharat Kulkarni", None),
        ("Chitra Iyer", None),
        ("Deepa Nair", "steward"),
    ]
    assert set(division["people"][0]) == {"id", "display_name", "username", "role"}
    club = admin.get(f"/admin/changes/candidates?workspace_id={ids['workspaces']['reading_club']}").json()
    assert [(item["username"], item["role"]) for item in club["people"]] == [
        ("bharat", "steward"),
        ("chitra", "member"),
    ]
    path = f"/admin/changes/candidates?workspace_id={ids['workspaces']['project']}"
    assert as_user("deepa").get(path).status_code == 403
    assert make_client().get(path).status_code == 401
    assert admin.get(f"/admin/changes/candidates?workspace_id={ids['users']['bharat']}").status_code == 404


def test_transfer_into_a_unit_with_a_dated_charge_is_not_undone_by_expiry(as_user, ids, db_factory, settings):
    """A charge that became the home unit must not remove the home membership on its end date."""
    admin = as_user("admin")
    ends = site_today(settings) + timedelta(days=10)
    charge = change(
        ids,
        "additional_charge",
        person_id="chitra",
        workspace_id="section_a",
        role="member",
        ends_on=ends.isoformat(),
    )
    apply(admin, charge)
    apply(admin, move(ids, person="chitra", unit="section_a"))
    with db_factory() as db:
        positions.expire_due(db, settings, now=start_of(ends, settings))
    assert grants(db_factory, ids["users"]["chitra"]).get(ids["workspaces"]["section_a"]) == "member"
    with db_factory() as db:
        assert str(db.get(User, ids["users"]["chitra"]).home_workspace_id) == ids["workspaces"]["section_a"]
