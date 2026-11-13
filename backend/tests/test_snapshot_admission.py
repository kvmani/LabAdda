"""Generated original assets share pilot admission and uncertain-commit safety."""

from dataclasses import replace
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from labadda.app import create_app
from labadda.models import Asset, Post, UploadReservation
from labadda.security import utcnow
from tests.conftest import Api
from tests.test_board_p3 import publish
from tests.test_chat_board import stroke


def test_snapshot_cannot_bypass_a_tiny_original_quota(settings, ids, db_factory):
    with TestClient(create_app(replace(settings, user_quota_bytes=1))) as client:
        bharat = Api(client, settings.api_prefix)
        assert bharat.login("bharat").status_code == 200
        w = ids["workspaces"]["section_a"]
        assert (
            bharat.post(
                f"/workspaces/{w}/board/ops", json=stroke("snapshot-quota-stroke", "fixture-line")
            ).status_code
            == 200
        )
        refused = publish(bharat, w, w, 1)
        assert refused.status_code == 422 and refused.json()["error"]["code"] == "quota_exceeded"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
        assert db.scalar(select(func.count()).select_from(Post)) == 0


def test_pending_upload_capacity_is_respected_by_snapshot(as_user, settings, ids, db_factory):
    bharat = as_user("bharat")
    w = ids["workspaces"]["section_a"]
    assert (
        bharat.post(
            f"/workspaces/{w}/board/ops", json=stroke("snapshot-pending-stroke", "fixture-line")
        ).status_code
        == 200
    )
    with db_factory() as db:
        db.add(
            UploadReservation(
                user_id=ids["users"]["bharat"],
                bytes=settings.user_quota_bytes,
                created_at=utcnow(),
                expires_at=utcnow() + timedelta(minutes=10),
            )
        )
        db.commit()
    refused = publish(bharat, w, w, 1)
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "quota_exceeded"


def test_snapshot_lost_commit_reply_preserves_published_bytes(as_user, ids, app, db_factory, monkeypatch):
    from sqlalchemy.orm import Session

    bharat = as_user("bharat")
    w = ids["workspaces"]["section_a"]
    assert (
        bharat.post(
            f"/workspaces/{w}/board/ops", json=stroke("snapshot-commit-stroke", "fixture-line")
        ).status_code
        == 200
    )
    original = Session.commit

    def commit_then_fail(db):
        publishing = any(isinstance(row, Post) for row in db.identity_map.values())
        original(db)
        if publishing:
            raise RuntimeError("synthetic lost snapshot commit reply")

    monkeypatch.setattr(Session, "commit", commit_then_fail)
    response = publish(bharat, w, w, 1)
    assert response.status_code == 201
    with db_factory() as db:
        asset = db.scalar(select(Asset).where(Asset.post_id == response.json()["post_id"]))
        assert asset is not None
        assert app.state.assets.path(asset.storage_key).is_file()
    assert publish(bharat, w, w, 1).json()["duplicate"]


def test_snapshot_unknown_commit_retains_unconfirmed_files(as_user, ids, app, db_factory, monkeypatch):
    from sqlalchemy.orm import Session

    bharat = as_user("bharat")
    w = ids["workspaces"]["section_a"]
    assert (
        bharat.post(
            f"/workspaces/{w}/board/ops", json=stroke("snapshot-unknown-stroke", "fixture-line")
        ).status_code
        == 200
    )
    original = Session.commit

    def fail(db):
        if any(isinstance(row, Post) for row in db.identity_map.values()):
            raise RuntimeError("synthetic unknown snapshot commit")
        original(db)

    monkeypatch.setattr(Session, "commit", fail)
    response = publish(bharat, w, w, 1)
    assert response.status_code == 503 and response.json()["error"]["code"] == "snapshot_commit_unknown"
    assert list(app.state.settings.asset_dir.rglob("*.bin"))
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 0


def test_expiry_during_snapshot_storage_prevents_publish(as_user, ids, app, db_factory, monkeypatch):
    from datetime import timedelta

    from labadda import security

    bharat = as_user("bharat")
    w = ids["workspaces"]["section_a"]
    assert (
        bharat.post(
            f"/workspaces/{w}/board/ops", json=stroke("snapshot-expiry-stroke", "fixture-line")
        ).status_code
        == 200
    )
    original = app.state.assets.save

    def expire(*args):
        stored = original(*args)
        future = security.utcnow() + timedelta(days=1)
        monkeypatch.setattr(security, "utcnow", lambda: future)
        return stored

    monkeypatch.setattr(app.state.assets, "save", expire)
    assert publish(bharat, w, w, 1).status_code == 401
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 0
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
    assert not list(app.state.settings.asset_dir.rglob("*.bin"))


def test_asset_publication_syncs_new_directory_ancestry(tmp_path, monkeypatch):
    import os
    import stat
    from pathlib import Path

    from labadda.storage import AssetStore

    root = tmp_path / "new-assets"
    store = AssetStore(root)
    synced = set()
    original = os.fsync

    def track(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            synced.add(Path(os.readlink(f"/proc/self/fd/{fd}")).resolve())
        return original(fd)

    monkeypatch.setattr(os, "fsync", track)
    stored = store.save(b"%PDF-1.4\nfixture\n%%EOF", "application/pdf")
    assert store.path(stored.storage_key).parent.resolve() in synced
    assert root.resolve() in synced
    assert tmp_path.resolve() in synced
    assert store.path(stored.storage_key).stat().st_mode & 0o777 == 0o600
