"""A7 Backups page, read-only settings and the site notice banner."""

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select

from labadda import audit_catalog
from labadda import backup_status as bs
from labadda.models import AuditEvent, SiteBanner
from labadda.security import utcnow
from tests.test_capabilities import grant
from tests.test_panel import PANEL, pair


@pytest.fixture
def status_dir(app, tmp_path):
    folder = tmp_path / "status-secret-folder"
    folder.mkdir()
    app.state.settings = replace(app.state.settings, status_dir=folder)
    return folder


def receipt(hours_ago=1, **changes):
    values = {
        "finished_at": utcnow().replace(microsecond=0) - timedelta(hours=hours_ago),
        "result": "success",
        "size_bytes": 4096,
        "verification": "passed",
        "destination": "nas-room",
        "schema": "0029",
        "release": "r1",
    }
    values.update(changes)
    return bs.BackupStatus(**values)


@pytest.mark.parametrize(
    ("hours", "word"), [(1, "healthy"), (30, "degraded"), (60, "stale")], ids=["fresh", "late", "old"]
)
def test_backup_status_words_follow_the_thresholds(as_user, status_dir, hours, word):
    bs.write_status(status_dir, receipt(hours))
    body = as_user("admin").get("/admin/backups/status").json()
    assert body["status"] == word
    assert body["last_backup"]["destination"] == "nas-room"
    assert body["last_backup"]["size_bytes"] == 4096
    assert body["last_backup"]["verification"] == "passed"
    assert body["next_run"] is None
    assert str(status_dir) not in str(body)


def test_failed_backup_is_unavailable(as_user, status_dir):
    bs.write_status(
        status_dir,
        receipt(result="failure", size_bytes=None, verification="not_run", schema=None, release=None),
    )
    assert as_user("admin").get("/admin/backups/status").json()["status"] == "unavailable"


def test_future_dated_backup_is_unknown(as_user, status_dir):
    bs.write_status(status_dir, receipt(hours_ago=-5))
    assert as_user("admin").get("/admin/backups/status").json()["status"] == "unknown"


@pytest.mark.parametrize("content", [b"not json", b"{}", b" " * 5000, b'{"format": 1}'])
def test_bad_status_file_is_unknown_with_guidance(as_user, status_dir, content):
    (status_dir / bs.STATUS_FILENAME).write_bytes(content)
    response = as_user("admin").get("/admin/backups/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unknown"
    assert body["last_backup"] is None
    assert body["guidance"]
    assert str(status_dir) not in response.text


def test_missing_file_or_folder_is_unknown(as_user, status_dir, app):
    admin = as_user("admin")
    assert admin.get("/admin/backups/status").json()["status"] == "unknown"
    app.state.settings = replace(app.state.settings, status_dir=None)
    body = admin.get("/admin/backups/status").json()
    assert body["status"] == "unknown" and "never" not in body["headline"]


def test_backups_visible_to_usage_readers_but_not_members(as_user, ids):
    assert as_user("bharat").get("/admin/backups/status").status_code == 403
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    assert as_user("bharat").get("/admin/backups/status").status_code == 200
    assert as_user("bharat").get("/admin/settings").status_code == 403


def test_settings_show_no_secret_path_or_host(as_user, app, tmp_path):
    app.state.settings = replace(
        app.state.settings,
        database_url="postgresql+psycopg://svc:hunter2-secret@db-host.example:5432/labadda",
        asset_dir=tmp_path / "assets-secret-folder",
        status_dir=tmp_path / "status-secret-folder",
        cookie_name="cookie-secret-name",
        trusted_origins=("https://intranet-secret.example",),
        extra={"token": "token-secret-value"},
    )
    response = as_user("admin").get("/admin/settings")
    assert response.status_code == 200
    for text in ("hunter2", "db-host", "assets-secret", "status-secret", "cookie-secret", "intranet-secret"):
        assert text not in response.text
    assert "token-secret" not in response.text
    body = response.json()
    assert body["groups"]
    for group in body["groups"]:
        for item in group["items"]:
            assert item["changed_by"] == "Changed by the operator in the site configuration file."
            assert item["explanation"] and item["label"]
    items = {item["key"]: item for group in body["groups"] for item in group["items"]}
    assert items["bulk_change_seconds"]["value"] == 60
    assert items["bulk_change_seconds"]["unit"] == "seconds"


def banner_body(**changes):
    now = utcnow()
    body = {
        "message": "Planned maintenance on Friday evening.",
        "level": "warning",
        "starts_at": (now - timedelta(minutes=1)).isoformat(),
        "ends_at": (now + timedelta(hours=2)).isoformat(),
        "expected_revision": 0,
    }
    body.update(changes)
    return body


def test_banner_is_audited_escaped_and_time_bounded(as_user, db_factory):
    admin, bharat = as_user("admin"), as_user("bharat")
    assert bharat.get("/site/banner").json() == {"banner": None}
    markup = "<script>alert(1)</script> back at 6"
    saved = admin.put("/admin/settings/banner", banner_body(message=markup))
    assert saved.status_code == 200
    assert saved.json()["banner"]["revision"] == 1
    shown = bharat.get("/site/banner").json()["banner"]
    assert shown["message"] == markup and shown["level"] == "warning" and "revision" not in shown
    assert admin.get("/admin/settings").json()["banner"]["message"] == markup
    with db_factory() as db:
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.action == "site.banner_set")))
        assert len(events) == 1 and events[0].detail["message_length"] == str(len(markup))
        assert markup not in str(events[0].detail)
        assert events[0].actor_id is not None
        assert audit_catalog.entry("site.banner_set") is not audit_catalog.UNKNOWN
        row = db.get(SiteBanner, 1)
        row.starts_at = utcnow() + timedelta(hours=1)
        row.ends_at = utcnow() + timedelta(hours=3)
        db.commit()
    assert bharat.get("/site/banner").json() == {"banner": None}
    with db_factory() as db:
        row = db.get(SiteBanner, 1)
        row.starts_at = utcnow() - timedelta(hours=3)
        row.ends_at = utcnow() - timedelta(hours=1)
        db.commit()
    assert bharat.get("/site/banner").json() == {"banner": None}


def test_banner_validation_and_concurrency(as_user, db_factory):
    admin = as_user("admin")
    assert admin.put("/admin/settings/banner", banner_body(message="x" * 281)).status_code == 422
    assert admin.put("/admin/settings/banner", banner_body(message="two\x00lines")).status_code == 422
    assert admin.put("/admin/settings/banner", banner_body(level="alert")).status_code == 422
    assert admin.put("/admin/settings/banner", banner_body(level=None)).status_code == 422
    past = (utcnow() - timedelta(hours=1)).isoformat()
    assert admin.put("/admin/settings/banner", banner_body(ends_at=past)).status_code == 422
    naive = "2030-01-01T00:00:00"
    assert admin.put("/admin/settings/banner", banner_body(ends_at=naive)).status_code == 422
    assert admin.put("/admin/settings/banner", banner_body(message="x" * 280)).status_code == 200
    stale = admin.put("/admin/settings/banner", banner_body(expected_revision=0))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "banner_changed"
    cleared = admin.put("/admin/settings/banner", banner_body(message="", expected_revision=1))
    assert cleared.status_code == 200 and cleared.json() == {"banner": None}
    with db_factory() as db:
        assert db.get(SiteBanner, 1) is None
        actions = set(db.scalars(select(AuditEvent.action).where(AuditEvent.action.like("site.%"))))
    assert actions == {"site.banner_set", "site.banner_clear"}


def test_banner_writes_need_an_administrator(as_user, ids):
    assert as_user("bharat").put("/admin/settings/banner", banner_body()).status_code == 403
    assert grant(as_user("admin"), ids["users"]["bharat"]).status_code == 201
    assert as_user("bharat").put("/admin/settings/banner", banner_body()).status_code == 403


def test_banner_needs_a_person_session(as_user, make_client, ids):
    anonymous = make_client()
    assert anonymous.get("/site/banner").status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.api.client.get(panel.api.url("/site/banner"), headers=PANEL).status_code == 401


def test_banner_downgrade_refuses_to_discard_a_notice(as_user, settings):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine

    import labadda

    path = Path(labadda.__file__).parents[1] / "migrations" / "versions" / "0029_site_banner.py"
    spec = importlib.util.spec_from_file_location("banner_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert as_user("admin").put("/admin/settings/banner", banner_body()).status_code == 200
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context), pytest.raises(RuntimeError, match="discard"):
            module.downgrade()
    engine.dispose()
