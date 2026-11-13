"""Excel staff import: mixed-depth tree, passwords, administrators, all-or-nothing and denials."""

import logging
import time
import urllib.parse

from sqlalchemy import func, select, text

from labadda.changes import xlsx
from labadda.changes.staff_sheet import HEADERS
from labadda.models import AuditEvent, Membership, User, Workspace
from tests.test_panel import PANEL, pair

SHEET = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
PASSWORD = "Sunrise-Lab-2027"


def person(name, user, no, group, division="", section="", **more):  # noqa: PLR0917 — compact test helper
    cells = {
        "full_name": name, "division": division, "section": section, "emp": no, "email": "", "ext": "",
        "group": group, "phone": "", "username": user, "password": "", "active": "", "role": "",
    }  # fmt: skip
    cells.update(more)
    return [
        cells["full_name"], cells["division"], cells["section"], cells["emp"], cells["email"], cells["ext"],
        cells["group"], cells["phone"], cells["username"], cells["password"], cells["active"], cells["role"],
    ]  # fmt: skip


def sheet(*people):
    return xlsx.write_rows([list(HEADERS), *people])


def preview(api, data):
    return api.post("/admin/changes/import/staff/preview", headers=SHEET, content=data)


def apply(api, data, digest, reason="Pilot onboarding"):
    headers = {**SHEET, "X-Import-Digest": digest, "X-Import-Reason": urllib.parse.quote(reason)}
    return api.post("/admin/changes/import/staff/apply", headers=headers, content=data)


def reviewed(api, data):
    response = preview(api, data)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["errors"] == [] or body["errors"] == 0
    assert body["plan"]["blockers"] == [], body["plan"]["blockers"]
    return body


MIXED = (
    person(
        "Ananya Iyer",
        "ananya.iyer",
        "00123",
        "Ceramics Group",
        "Sintering Division",
        "Kiln Section",
        ext="4417",
    ),
    person(
        "Rohit Deshpande", "rohit.deshpande", "00124", "Ceramics Group", "Sintering Division", "Kiln Section"
    ),
    person("Meera Nair", "meera.nair", "00125", "Ceramics Group", "Sintering Division"),
    person("Kabir Menon", "kabir.menon", "00126", "Ceramics Group", section="Glaze Section"),
    person("Latha Pillai", "latha.pillai", "00127", "Ceramics Group"),
)


def test_mixed_depth_tree_preview_and_apply(as_user, db_factory):
    admin = as_user("admin")
    data = sheet(*MIXED)
    body = reviewed(admin, data)
    made = [(u["name"], u["level"], u["under"]) for u in body["units_to_create"]]
    assert made == [
        ("Ceramics Group", "group", []),
        ("Sintering Division", "division", ["Ceramics Group"]),
        ("Kiln Section", "section", ["Ceramics Group", "Sintering Division"]),
        ("Glaze Section", "section", ["Ceramics Group"]),
    ]
    assert any("Create the group Ceramics Group" in step["summary"] for step in body["plan"]["steps"])
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.username == "meera.nair")) == 0
    response = apply(admin, data, body["plan"]["digest"])
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 9
    with db_factory() as db:
        units = {u.name: u for u in db.scalars(select(Workspace).where(Workspace.kind == "org"))}
        group, division = units["Ceramics Group"], units["Sintering Division"]
        assert (group.level, division.level) == ("group", "division")
        assert units["Kiln Section"].parent_id == division.id and units["Kiln Section"].level == "section"
        assert units["Glaze Section"].parent_id == group.id
        homes = {u.username: u.home_workspace_id for u in db.scalars(select(User))}
        assert homes["ananya.iyer"] == units["Kiln Section"].id
        assert homes["meera.nair"] == division.id
        assert homes["kabir.menon"] == units["Glaze Section"].id
        assert homes["latha.pillai"] == group.id
        ananya = db.scalar(select(User).where(User.username == "ananya.iyer"))
        assert (ananya.contact_email, ananya.extension, ananya.employee_no) == (
            "ananya.iyer@domain.in",
            "4417",
            "00123",
        )
        assert ananya.status == "invited" and ananya.must_set_password and not ananya.is_admin
        role = db.scalar(
            select(Membership.role).where(
                Membership.user_id == ananya.id, Membership.workspace_id == homes["ananya.iyer"]
            )
        )
        assert role == "member"
        assert (
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "people.change")
            )
            >= 9
        )


def test_activation_slips_come_back_for_people_without_a_password(as_user):
    admin = as_user("admin")
    data = sheet(MIXED[0], person("Dev Kapoor", "dev.kapoor", "9", "Ceramics Group", password=PASSWORD))
    digest = reviewed(admin, data)["plan"]["digest"]
    added = apply(admin, data, digest).json()["added"]
    by_name = {item["username"]: item for item in added}
    assert by_name["ananya.iyer"]["activation"]["code"]
    assert "activation" not in by_name["dev.kapoor"]


def test_existing_units_are_matched_by_name_ignoring_case_and_never_across_parents(as_user, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        root = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None)))
        old = db.scalar(select(Workspace).where(Workspace.parent_id == root.id, Workspace.kind == "org"))
        old_name = old.name
    data = sheet(
        person("Isha Rao", "isha.rao", "31", old_name.upper(), "Plasma Division"),
        person("Om Bhatt", "om.bhatt", "32", "Alloys Group", "Plasma Division"),
    )
    body = reviewed(admin, data)
    created = [(u["name"], u["under"]) for u in body["units_to_create"]]
    assert (old_name, []) not in created
    assert created.count(("Plasma Division", [old_name.upper()])) == 1
    assert ("Plasma Division", ["Alloys Group"]) in created
    assert apply(admin, data, body["plan"]["digest"]).status_code == 200
    with db_factory() as db:
        divisions = db.scalars(select(Workspace).where(Workspace.name == "Plasma Division")).all()
        assert len(divisions) == 2 and len({d.parent_id for d in divisions}) == 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(func.lower(Workspace.name) == old_name.lower())
            )
            == 1
        )


def test_same_name_siblings_and_conflicting_levels_are_row_errors(as_user, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        root = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None)))
        db.add_all(
            Workspace(kind="org", name=name, code=code, parent_id=root.id)
            for name, code in (("Twin Group", "TW1"), ("TWIN GROUP", "TW2"))
        )
        db.commit()
    body = preview(admin, sheet(person("Zoya Khan", "zoya.khan", "41", "Twin Group"))).json()
    assert body["errors"] == 1 and "More than one unit" in body["rows"][0]["errors"][0]
    assert body["plan"] is None
    clash = sheet(
        person("Esha Roy", "esha.roy", "42", "Fresh Group", "Mixed Unit"),
        person("Farhan Ali", "farhan.ali", "43", "Fresh Group", section="Mixed Unit"),
    )
    body = preview(admin, clash).json()
    assert body["errors"] == 1 and "both a division and a section" in body["rows"][1]["errors"][0]


def test_password_is_hashed_once_and_found_nowhere_else(as_user, db_factory, make_client, caplog):
    admin = as_user("admin")
    row = person("Tara Joshi", "tara.joshi", "51", "Ceramics Group", password=PASSWORD)
    data = sheet(row)
    with caplog.at_level(logging.DEBUG):
        first = preview(admin, data)
        assert PASSWORD not in first.text
        body = first.json()
        done = apply(admin, data, body["plan"]["digest"])
    assert done.status_code == 200 and PASSWORD not in done.text
    assert PASSWORD not in caplog.text
    with db_factory() as db:
        tara = db.scalar(select(User).where(User.username == "tara.joshi"))
        assert tara.password_hash.startswith("$argon2") and PASSWORD not in tara.password_hash
        assert (tara.status, tara.is_active, tara.must_set_password, tara.must_change_password) == (
            "active",
            True,
            False,
            True,
        )
        tables = (
            db.execute(text("select table_name from information_schema.tables where table_schema='public'"))
            .scalars()
            .all()
        )
        for table in tables:
            query = text(f'select t::text from "{table}" t')  # noqa: S608
            dump = db.execute(query).scalars().all()
            assert not any(PASSWORD in line for line in dump), table
        audit = db.scalars(select(AuditEvent)).all()
        assert audit and not any(PASSWORD in str(event.detail) for event in audit)


def test_a_first_password_must_be_changed_before_anything_else(make_client, as_user):
    admin = as_user("admin")
    data = sheet(person("Uma Reddy", "uma.reddy", "61", "Ceramics Group", password=PASSWORD))
    apply(admin, data, reviewed(admin, data)["plan"]["digest"])
    uma = make_client()
    login = uma.login("uma.reddy", PASSWORD)
    assert login.status_code == 200 and login.json()["must_change_password"] is True
    assert uma.get("/auth/session").status_code == 200
    blocked = uma.get("/workspaces")
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "password_change_required"
    assert (
        uma.post("/me/password", json={"current_password": PASSWORD, "new_password": "short"}).status_code
        == 422
    )
    changed = uma.post(
        "/me/password", json={"current_password": PASSWORD, "new_password": "Fresh-Start-9876"}
    )
    assert changed.status_code == 200
    assert uma.get("/workspaces").status_code == 200
    assert uma.get("/auth/session").json()["must_change_password"] is False


def test_weak_and_clashing_rows_stop_the_whole_file(as_user, db_factory):
    admin = as_user("admin")
    data = sheet(MIXED[0], person("Vikram Sethi", "vikram.sethi", "71", "Ceramics Group", password="short"))
    body = preview(admin, data).json()
    assert body["errors"] == 1 and "too short" in body["rows"][1]["errors"][0] and body["plan"] is None
    refused = apply(admin, data, "0" * 64)
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "import_has_errors"
    with db_factory() as db:
        assert (
            db.scalar(select(func.count()).select_from(Workspace).where(Workspace.name == "Ceramics Group"))
            == 0
        )
        assert db.scalar(select(func.count()).select_from(User).where(User.username == "ananya.iyer")) == 0
    taken = sheet(person("Another Asha", "asha", "72", "Ceramics Group"))
    assert "already has an account" in preview(admin, taken).json()["rows"][0]["errors"][0]


def test_a_change_after_review_makes_apply_start_over_and_save_nothing(as_user, db_factory):
    admin = as_user("admin")
    data = sheet(*MIXED)
    digest = reviewed(admin, data)["plan"]["digest"]
    with db_factory() as db:
        root = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_(None)))
        db.add(Workspace(kind="org", name="Ceramics Group", code="CG", parent_id=root.id))
        db.commit()
    stale = apply(admin, data, digest)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "plan_stale"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(User).where(User.username == "meera.nair")) == 0


def test_administrator_rows_are_flagged_audited_and_never_lose_the_guard(as_user, db_factory):
    admin = as_user("admin")
    data = sheet(
        person("Priya Kulkarni", "priya.kulkarni", "81", "Ceramics Group", role="admin", password=PASSWORD)
    )
    body = preview(admin, data).json()
    assert body["administrators"] == ["Priya Kulkarni"]
    assert "Will become an administrator." in body["rows"][0]["warnings"]
    assert apply(admin, data, body["plan"]["digest"]).status_code == 200
    with db_factory() as db:
        priya = db.scalar(select(User).where(User.username == "priya.kulkarni"))
        assert priya.is_admin
        steps = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "people.change_step", AuditEvent.target_id == str(priya.id)
            )
        ).all()
        assert any(step.detail["after"].get("is_admin") is True for step in steps)
    inactive = sheet(
        person("Quiet Admin", "quiet.admin", "82", "Ceramics Group", role="admin", active="FALSE")
    )
    plan = preview(admin, inactive).json()["plan"]
    assert any(b["code"] == "admin_inactive" for b in plan["blockers"])


def test_inactive_rows_get_no_sign_in_and_no_code(as_user, db_factory):
    admin = as_user("admin")
    data = sheet(person("Rest Person", "rest.person", "91", "Ceramics Group", active="false"))
    done = apply(admin, data, reviewed(admin, data)["plan"]["digest"])
    assert done.json()["added"][0].get("activation") is None
    with db_factory() as db:
        who = db.scalar(select(User).where(User.username == "rest.person"))
        assert (who.is_active, who.status) == (False, "suspended")


def test_nine_divisions_of_five_sections_of_six_people_fit_the_time_limit(as_user, db_factory):
    admin = as_user("admin")
    people = [
        person(
            f"Staff {d}{s}{n}",
            f"staff.{d}.{s}.{n}",
            f"E{d}{s}{n}",
            "Scale Group",
            f"Division {d}",
            f"Section {d}-{s}",
        )
        for d in range(9)
        for s in range(5)
        for n in range(6)
    ]
    assert len(people) == 270
    data = sheet(*people)
    started = time.monotonic()
    body = reviewed(admin, data)
    assert len(body["units_to_create"]) == 1 + 9 + 45
    assert apply(admin, data, body["plan"]["digest"]).status_code == 200
    assert time.monotonic() - started < 60
    with db_factory() as db:
        group = db.scalar(select(Workspace).where(Workspace.name == "Scale Group"))
        divisions = db.scalars(select(Workspace).where(Workspace.parent_id == group.id)).all()
        assert len(divisions) == 9
        for division in divisions:
            sections = db.scalars(select(Workspace).where(Workspace.parent_id == division.id)).all()
            assert len(sections) == 5
            for section in sections:
                assert (
                    db.scalar(
                        select(func.count()).select_from(User).where(User.home_workspace_id == section.id)
                    )
                    == 6
                )


def test_template_has_exact_headers_and_one_example(as_user):
    admin = as_user("admin")
    response = admin.get("/admin/changes/import/staff/template")
    assert response.status_code == 200 and "spreadsheetml" in response.headers["content-type"]
    rows = xlsx.read_rows(response.content)
    assert rows[0] == list(HEADERS) and rows[1][0] == "Ananya Iyer" and rows[1][3] == "00123"
    assert rows[1][4] == "ananya.iyer@domain.in"


def test_only_signed_in_administrators_may_use_it(as_user, make_client, ids):
    data = sheet(MIXED[0])
    for name in ("bharat", "asha", "deepa"):
        member = as_user(name)
        assert preview(member, data).status_code == 403
        assert member.get("/admin/changes/import/staff/template").status_code == 403
        assert apply(member, data, "0" * 64).status_code == 403
    anonymous = make_client()
    assert preview(anonymous, data).status_code == 401
    assert anonymous.get("/admin/changes/import/staff/template").status_code == 401
    assert apply(anonymous, data, "0" * 64).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.post("/admin/changes/import/staff/preview", json={}).status_code == 401
    assert panel.post("/admin/changes/import/staff/apply", json={}).status_code == 401
    assert preview(as_user("admin"), data).status_code == 200
    headers = {**SHEET, **PANEL}
    assert (
        as_user("admin")
        .post("/admin/changes/import/staff/preview", headers=headers, content=data)
        .status_code
        == 401
    )


def test_a_wrong_file_type_and_unit_administrators_are_refused(as_user):
    admin = as_user("admin")
    wrong = admin.post(
        "/admin/changes/import/staff/preview", headers={"Content-Type": "text/html"}, content=b"x"
    )
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "import_not_xlsx"
    junk = preview(admin, b"PK\x03\x04not a workbook")
    assert junk.status_code == 422
    bulk = admin.post(
        "/admin/changes/bulk/preview",
        json={
            "requests": [
                {"kind": "import_unit", "path": [{"name": "Hidden", "level": "group", "code": "HID"}]}
            ]
        },
    )
    assert bulk.status_code == 200


def test_levels_and_contact_fields_appear_only_where_the_record_may_be_seen(as_user, db_factory):
    admin = as_user("admin")
    row = person("Ananya Iyer", "ananya.iyer", "00123", "Ceramics Group", "Sintering Division", ext="4417")
    data = sheet(row)
    assert apply(admin, data, reviewed(admin, data)["plan"]["digest"]).status_code == 200
    units = {u["name"]: u for u in admin.get("/admin/org/tree").json()["units"]}
    assert (units["Ceramics Group"]["level"], units["Sintering Division"]["level"]) == ("group", "division")
    listing = admin.get("/admin/people?q=ananya")
    assert listing.status_code == 200
    assert "4417" not in listing.text and "ananya.iyer@domain.in" not in listing.text
    assert listing.json()["people"][0]["home_unit"]["level"] == "division"
    person_id = listing.json()["people"][0]["id"]
    record = admin.get(f"/admin/people/{person_id}").json()
    assert (record["extension"], record["contact_email"]) == ("4417", "ananya.iyer@domain.in")
    assert record["residence_phone"] is None


def test_the_migration_refuses_to_discard_new_fields(as_user, settings):
    import importlib.util
    from pathlib import Path

    import pytest
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine

    import labadda

    path = Path(labadda.__file__).parents[1] / "migrations" / "versions" / "0038_staff_import_fields.py"
    spec = importlib.util.spec_from_file_location("staff_import_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    admin = as_user("admin")
    data = sheet(person("Ananya Iyer", "ananya.iyer", "00123", "Ceramics Group", ext="4417"))
    assert apply(admin, data, reviewed(admin, data)["plan"]["digest"]).status_code == 200
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context), pytest.raises(RuntimeError, match="discard"):
            module.downgrade()
    engine.dispose()
