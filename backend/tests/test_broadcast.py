"""AD-11 site broadcasts: admin CRUD, order, time windows, escaping, audit and denied cases."""

from datetime import timedelta

import pytest
from alembic import command
from sqlalchemy import create_engine, select, text

from labadda import audit_catalog, broadcast
from labadda.cli import alembic_config
from labadda.models import AuditEvent, SiteBroadcast, User
from labadda.security import utcnow
from tests.conftest import recreate_schema
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair

HOUR = timedelta(hours=1)


def body(**changes):
    values = {"message": "Planned maintenance on Friday evening.", "level": "warning"}
    values.update(changes)
    return values


def add(admin, **changes):
    response = admin.post("/admin/broadcasts", body(**changes))
    assert response.status_code == 201, response.text
    return response.json()["broadcast"]


def shown(client):
    response = client.get("/site/broadcasts")
    assert response.status_code == 200
    return response.json()["broadcasts"]


def test_add_edit_deactivate_delete_with_audit(as_user, db_factory):
    admin, bharat = as_user("admin"), as_user("bharat")
    assert shown(bharat) == []
    first = add(admin, message="Server restart at six")
    second = add(admin, message="Library closed Monday", level="info")
    assert [b["position"] for b in (first, second)] == [1, 2]
    assert [m["message"] for m in shown(bharat)] == ["Server restart at six", "Library closed Monday"]
    assert set(shown(bharat)[0]) == {"id", "message", "level"}

    edited = admin.patch(
        f"/admin/broadcasts/{first['id']}", {"message": "Server restart at seven", "expected_revision": 1}
    )
    assert edited.status_code == 200 and edited.json()["broadcast"]["revision"] == 2
    off = admin.patch(f"/admin/broadcasts/{second['id']}", {"active": False, "expected_revision": 1})
    assert off.json()["broadcast"]["status"] == "off"
    assert [m["message"] for m in shown(bharat)] == ["Server restart at seven"]
    assert admin.delete(f"/admin/broadcasts/{first['id']}").status_code == 200
    assert shown(bharat) == []
    assert admin.delete(f"/admin/broadcasts/{first['id']}").status_code == 404
    listing = admin.get("/admin/broadcasts").json()
    assert [b["id"] for b in listing["broadcasts"]] == [second["id"]]
    assert listing["max_length"] == 300

    with db_factory() as db:
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.action.like("site.broadcast_%"))))
        assert sorted(e.action for e in events) == ["site.broadcast_add"] * 2 + [
            "site.broadcast_delete",
            "site.broadcast_edit",
            "site.broadcast_edit",
        ]
        assert all(e.actor_id is not None for e in events)
        # Same transaction as the write: the text is never in the trail, its length is.
        assert not any("restart" in str(e.detail) or "Library" in str(e.detail) for e in events)
        deleted = next(e for e in events if e.action == "site.broadcast_delete")
        assert deleted.detail["message_length"] == str(len("Server restart at seven"))
        assert deleted.target_id == str(first["id"])
        assert all(audit_catalog.entry(e.action) is not audit_catalog.UNKNOWN for e in events)


def test_time_windows_and_scheduled_status(as_user, db_factory):
    admin, bharat = as_user("admin"), as_user("bharat")
    now = utcnow()
    soon = add(admin, message="Later", starts_at=(now + HOUR).isoformat())
    assert soon["status"] == "scheduled" and shown(bharat) == []
    live = add(admin, message="Now", ends_at=(now + HOUR).isoformat())
    assert live["status"] == "showing" and [m["message"] for m in shown(bharat)] == ["Now"]
    with db_factory() as db:
        row = db.get(SiteBroadcast, soon["id"])
        row.starts_at = now - HOUR
        other = db.get(SiteBroadcast, live["id"])
        other.starts_at, other.ends_at = now - 2 * HOUR, now - HOUR
        db.commit()
    assert [m["message"] for m in shown(bharat)] == ["Later"]
    states = {b["id"]: b["status"] for b in admin.get("/admin/broadcasts").json()["broadcasts"]}
    assert states == {soon["id"]: "showing", live["id"]: "ended"}


def test_pure_window_rules():
    now = utcnow()
    row = SiteBroadcast(active=True, starts_at=None, ends_at=None)
    assert broadcast.status_of(row, now) == "showing"
    row.ends_at = now  # the end moment itself is already over
    assert broadcast.status_of(row, now) == "ended"
    row.ends_at, row.starts_at = now + HOUR, now
    assert broadcast.status_of(row, now) == "showing"


def test_validation(as_user):
    admin = as_user("admin")
    now = utcnow()
    post = admin.post
    assert post("/admin/broadcasts", body(message="x" * 301)).status_code == 422
    assert post("/admin/broadcasts", body(message="x" * 301)).json()["error"]["code"] == "broadcast_too_long"
    assert post("/admin/broadcasts", body(message="   ")).status_code == 422
    assert post("/admin/broadcasts", body(message="two\x00lines")).status_code == 422
    assert post("/admin/broadcasts", body(level="alert")).status_code == 422
    assert post("/admin/broadcasts", body(unknown=1)).status_code == 422
    assert post("/admin/broadcasts", body(ends_at="2030-01-01T00:00:00")).status_code == 422
    past = (now - HOUR).isoformat()
    assert post("/admin/broadcasts", body(ends_at=past)).json()["error"]["code"] == "invalid_broadcast_times"
    backwards = body(starts_at=(now + 3 * HOUR).isoformat(), ends_at=(now + HOUR).isoformat())
    assert post("/admin/broadcasts", backwards).status_code == 422
    assert post("/admin/broadcasts", body(message="x" * 300)).status_code == 201
    made = add(admin)
    url = f"/admin/broadcasts/{made['id']}"
    assert admin.patch(url, {"message": None, "expected_revision": 1}).status_code == 422
    assert admin.patch(url, {"ends_at": past, "expected_revision": 1}).status_code == 422
    assert admin.patch(url, {"expected_revision": 1, "bogus": 1}).status_code == 422
    assert (
        admin.patch("/admin/broadcasts/999999", {"active": False, "expected_revision": 1}).status_code == 404
    )


def test_stale_edit_is_a_conflict_not_an_overwrite(as_user):
    admin = as_user("admin")
    made = add(admin, message="Original")
    url = f"/admin/broadcasts/{made['id']}"
    assert admin.patch(url, {"message": "Mine", "expected_revision": 1}).status_code == 200
    stale = admin.patch(url, {"message": "Theirs", "expected_revision": 1})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "broadcast_changed"
    assert admin.get("/admin/broadcasts").json()["broadcasts"][0]["message"] == "Mine"


def test_markup_is_stored_and_served_as_typed(as_user):
    admin = as_user("admin")
    markup = "<script>alert(1)</script> back at 6"
    add(admin, message=markup)
    assert shown(as_user("chitra"))[0]["message"] == markup


def test_order_can_be_changed(as_user):
    admin, bharat = as_user("admin"), as_user("bharat")
    ids = [add(admin, message=name)["id"] for name in ("One", "Two", "Three")]
    admin.post(f"/admin/broadcasts/{ids[2]}/move", {"direction": "up"})
    done = admin.post(f"/admin/broadcasts/{ids[0]}/move", {"direction": "up"})  # already first: no change
    assert [b["message"] for b in done.json()["broadcasts"]] == ["One", "Three", "Two"]
    assert [m["message"] for m in shown(bharat)] == ["One", "Three", "Two"]
    assert admin.post("/admin/broadcasts/999999/move", {"direction": "up"}).status_code == 404
    assert admin.post(f"/admin/broadcasts/{ids[0]}/move", {"direction": "sideways"}).status_code == 422


def test_the_list_is_bounded(as_user):
    admin = as_user("admin")
    for number in range(broadcast.MAX_BROADCASTS):
        add(admin, message=f"Message {number}")
    full = admin.post("/admin/broadcasts", body())
    assert full.status_code == 409 and full.json()["error"]["code"] == "too_many_broadcasts"


def test_only_administrators_manage_broadcasts(as_user, ids):
    made = add(as_user("admin"))
    url = f"/admin/broadcasts/{made['id']}"
    reader = as_user("bharat")
    for check in (
        lambda who: who.get("/admin/broadcasts"),
        lambda who: who.post("/admin/broadcasts", body()),
        lambda who: who.patch(url, {"active": False, "expected_revision": 1}),
        lambda who: who.post(f"{url}/move", {"direction": "down"}),
        lambda who: who.delete(url),
    ):
        assert check(reader).status_code == 403
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    for check in (
        lambda who: who.get("/admin/broadcasts"),
        lambda who: who.post("/admin/broadcasts", body()),
        lambda who: who.delete(url),
    ):
        assert check(reader).status_code == 403  # an operational reader has no broadcast access
    assert shown(reader)[0]["message"] == made["message"]  # but reads the strip like everyone else
    assert as_user("admin").get("/admin/broadcasts").json()["broadcasts"][0]["id"] == made["id"]


def test_signed_out_and_board_only_sessions_get_401(as_user, make_client, ids):
    anonymous = make_client()
    assert anonymous.get("/site/broadcasts").status_code == 401
    assert anonymous.get("/admin/broadcasts").status_code == 401
    assert anonymous.post("/admin/broadcasts", body()).status_code == 401
    panel = pair(as_user, make_client, ids)
    for path in ("/site/broadcasts", "/admin/broadcasts"):
        assert panel.api.client.get(panel.api.url(path), headers=PANEL).status_code == 401


def test_deactivated_person_cannot_read_or_manage(as_user, db_factory):
    admin = as_user("admin")
    add(admin)
    chitra = as_user("chitra")
    with db_factory() as db:
        user = db.scalar(select(User).where(User.username == "chitra"))
        user.is_active = False
        db.commit()
    assert chitra.get("/site/broadcasts").status_code == 401


def test_pilot_notice_is_seeded_once_and_can_be_removed(db_factory, as_user):
    with db_factory() as db:
        broadcast.seed_pilot_notice(db)
    first = as_user("bharat").get("/site/broadcasts").json()["broadcasts"]
    assert first[0]["message"] == (
        "The software is under pilot testing. Exercise caution in usage! Don't put any sensitive information."
    )
    assert first[0]["level"] == "warning"
    admin = as_user("admin")
    row = admin.get("/admin/broadcasts").json()["broadcasts"][0]
    assert row["ends_at"] is None and row["active"] is True
    assert admin.delete(f"/admin/broadcasts/{row['id']}").status_code == 200
    with db_factory() as db:
        actions = list(
            db.scalars(select(AuditEvent.action).where(AuditEvent.action.like("site.broadcast_%")))
        )
        assert sorted(actions) == ["site.broadcast_delete", "site.broadcast_seed"]


def test_create_admin_seeds_the_notice_on_a_fresh_pilot_install_only(
    settings, db_factory, monkeypatch, capsys
):
    from dataclasses import replace

    from labadda import cli
    from labadda.fixtures import reset_database

    monkeypatch.setattr(cli, "load_settings", lambda: replace(settings, environment="pilot"))
    with db_factory() as db:
        reset_database(db)
        db.commit()
    assert cli.main(["create-admin", "first.owner"]) == 0
    assert cli.main(["create-admin", "second.owner"]) == 0
    with db_factory() as db:
        assert db.scalar(select(text("count(*)")).select_from(SiteBroadcast)) == 1


def test_migration_moves_the_old_banner_and_refuses_lossy_downgrade(migrated):
    config = alembic_config(migrated)
    engine = create_engine(migrated)
    try:
        recreate_schema(migrated)
        command.upgrade(config, "0038")
        now = utcnow()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into site_banner (id, message, level, starts_at, ends_at, revision, updated_at)"
                    " values (1, 'Old notice', 'info', :s, :e, 3, :s)"
                ),
                {"s": now - HOUR, "e": now + HOUR},
            )
        command.upgrade(config, "head")
        with engine.connect() as conn:
            row = conn.execute(text("select message, level, active, position from site_broadcasts")).one()
            assert tuple(row) == ("Old notice", "info", True, 1)
            assert conn.execute(text("select to_regclass('site_banner')")).scalar() is None
        with engine.begin() as conn:
            conn.execute(
                text(
                    "insert into site_broadcasts (message, level, active, position, revision, created_at,"
                    " updated_at) values ('Second', 'info', true, 2, 1, now(), now())"
                )
            )
        with pytest.raises(Exception, match="discard"):
            command.downgrade(config, "0038")
        with engine.begin() as conn:
            conn.execute(text("delete from site_broadcasts where message = 'Second'"))
        command.downgrade(config, "0038")
        with engine.connect() as conn:
            assert conn.execute(text("select message from site_banner")).scalar() == "Old notice"
    finally:
        engine.dispose()
        recreate_schema(migrated)
        command.upgrade(config, "head")
