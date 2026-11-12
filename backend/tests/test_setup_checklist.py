"""H3: GET /admin/setup-checklist. Every item follows real state; none is ever ticked by hand."""

import uuid
from dataclasses import replace

import pytest
from sqlalchemy import select, update

from labadda import backup_status as bs
from labadda import setup_checklist
from labadda.models import Membership, User, Workspace
from tests.test_admin_site import receipt
from tests.test_capabilities import grant
from tests.test_overview import staff_every_unit
from tests.test_panel import pair

CHECKLIST = "/admin/setup-checklist"
KEYS = ["second_admin", "units", "people", "stewards", "backups", "time_zone", "test_restore"]


@pytest.fixture
def status_dir(app, tmp_path):
    folder = tmp_path / "status-secret-folder"
    folder.mkdir()
    app.state.settings = replace(app.state.settings, status_dir=folder)
    return folder


def states(client):
    body = client.get(CHECKLIST).json()
    return {item["key"]: item["state"] for item in body["items"]}


def test_items_come_in_order_with_screen_and_help(as_user):
    body = as_user("admin").get(CHECKLIST).json()
    assert [item["key"] for item in body["items"]] == KEYS
    assert body["total"] == len(KEYS)
    assert body["done"] == sum(item["state"] == "done" for item in body["items"])
    for item in body["items"]:
        assert item["screen"].startswith("/admin/") and item["help"].startswith("admin/")
        assert item["state"] in {"done", "not_done", "unknown"}


def test_second_administrator_follows_active_administrators(as_user, db_factory):
    admin = as_user("admin")
    assert states(admin)["second_admin"] == "not_done"
    with db_factory() as db:
        db.execute(update(User).where(User.username == "ben").values(is_admin=True))
        db.commit()
    assert states(admin)["second_admin"] == "done"
    with db_factory() as db:
        db.execute(update(User).where(User.username == "ben").values(is_active=False))
        db.commit()
    assert states(admin)["second_admin"] == "not_done"


def test_units_follow_open_units_below_the_top(as_user, db_factory):
    admin = as_user("admin")
    assert states(admin)["units"] == "done"
    with db_factory() as db:
        db.execute(
            update(Workspace)
            .where(Workspace.kind == "org", Workspace.parent_id.is_not(None))
            .values(archived=True)
        )
        db.commit()
    assert states(admin)["units"] == "not_done"


def test_people_follow_active_staff_besides_administrators(as_user, db_factory):
    admin = as_user("admin")
    assert states(admin)["people"] == "done"
    with db_factory() as db:
        db.execute(update(User).where(User.is_admin.is_(False)).values(status="retired"))
        db.commit()
    assert states(admin)["people"] == "not_done"


def test_stewards_follow_every_open_unit(as_user, db_factory):
    admin = as_user("admin")
    staff_every_unit(db_factory)
    assert states(admin)["stewards"] == "done"
    with db_factory() as db:
        steward = db.scalar(select(Membership).where(Membership.role == "steward"))
        db.delete(steward)
        db.commit()
    assert states(admin)["stewards"] == "not_done"


def test_backups_are_unknown_until_a_report_exists_then_follow_its_age(as_user, status_dir):
    admin = as_user("admin")
    assert states(admin)["backups"] == "unknown"
    bs.write_status(status_dir, receipt(1))
    assert states(admin)["backups"] == "done"
    bs.write_status(status_dir, receipt(60))
    assert states(admin)["backups"] == "not_done"
    bs.write_status(status_dir, receipt(1, result="failure", verification="failed"))
    assert states(admin)["backups"] == "not_done"


def test_time_zone_is_done_only_when_the_operator_chose_one(as_user, app):
    admin = as_user("admin")
    app.state.settings = replace(app.state.settings, timezone_configured=False)
    assert states(admin)["time_zone"] == "not_done"
    app.state.settings = replace(app.state.settings, timezone="Asia/Kolkata", timezone_configured=True)
    item = next(i for i in admin.get(CHECKLIST).json()["items"] if i["key"] == "time_zone")
    assert item["state"] == "done" and "Asia/Kolkata" in item["detail"]


def test_test_restore_is_unknown_until_one_is_recorded(as_user, monkeypatch):
    admin = as_user("admin")
    assert states(admin)["test_restore"] == "unknown"
    real = setup_checklist.backup_report
    monkeypatch.setattr(
        setup_checklist, "backup_report", lambda *args: {**real(*args), "restore_rehearsal": {"ok": True}}
    )
    assert states(admin)["test_restore"] == "done"


def test_access_follows_the_console_rules(as_user, make_client, ids):
    assert as_user("admin").get(CHECKLIST).status_code == 200
    for username in ("asha", "chen", "ben"):
        assert as_user(username).get(CHECKLIST).status_code == 403
    assert grant(as_user("admin"), ids["users"]["ben"]).status_code == 201
    assert as_user("ben").get(CHECKLIST).status_code == 403
    assert make_client().get(CHECKLIST).status_code == 401
    assert pair(as_user, make_client, ids).get(CHECKLIST).status_code == 401


def test_deactivated_administrator_is_refused(as_user, db_factory):
    admin = as_user("admin")
    with db_factory() as db:
        db.execute(update(User).where(User.username == "admin").values(is_active=False))
        db.commit()
    assert admin.get(CHECKLIST).status_code in {401, 403}


def test_checklist_contains_no_user_content(as_user, ids, status_dir):
    member = as_user("ben")
    secrets = (
        "Synthetic checklist post body",
        "Synthetic checklist chat text",
        "synthetic-checklist-note",
        "checklist-file.pdf",
    )
    workspace = ids["workspaces"]["section_a"]
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": secrets[0]}).status_code == 201
    chat = {"body": secrets[1], "client_id": str(uuid.uuid4())}
    assert member.post(f"/workspaces/{workspace}/chat", json=chat).status_code == 201
    assert member.post("/notes", json={"title": secrets[2], "body": secrets[2]}).status_code == 201
    upload = {"file": (secrets[3], b"%PDF-1.4\nS\n%%EOF", "application/pdf")}
    assert member.post("/uploads", files=upload).status_code == 201
    bs.write_status(status_dir, receipt(60))
    text = as_user("admin").get(CHECKLIST).text
    for secret in secrets:
        assert secret not in text
    assert str(status_dir) not in text


def test_settings_know_whether_the_operator_chose_the_time_zone():
    from labadda.config import load_settings

    assert load_settings({}).timezone_configured is False
    chosen = load_settings({"LABADDA_TIMEZONE": "Asia/Kolkata"})
    assert chosen.timezone_configured is True and chosen.timezone == "Asia/Kolkata"
