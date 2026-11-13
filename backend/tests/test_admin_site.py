"""A7 Backups page and read-only settings (broadcasts: test_broadcast.py)."""

from dataclasses import replace
from datetime import timedelta

import pytest

from labadda import backup_status as bs
from labadda.security import utcnow
from tests.test_capabilities import grant


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
