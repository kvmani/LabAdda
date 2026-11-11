"""T16 foundation: measured original bytes cannot over-admit concurrent uploads."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

from fastapi.testclient import TestClient
from labadda.app import create_app
from labadda.models import Asset, UploadReservation
from labadda.security import utcnow
from sqlalchemy import func, select

from tests.conftest import Api

PDF = b"%PDF-1.4\nfixture\n%%EOF"


def upload(api):
    return api.post("/uploads", files={"file": ("fixture.pdf", PDF, "application/pdf")})


def test_parallel_uploads_reserve_before_filesystem_write(settings, ids, db_factory, monkeypatch):
    app = create_app(replace(settings, user_quota_bytes=len(PDF) + 1))
    entered, release = threading.Event(), threading.Event()
    original = app.state.assets.save

    def slow_save(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(app.state.assets, "save", slow_save)
    with TestClient(app) as first, TestClient(app) as second:
        a, b = Api(first, settings.api_prefix), Api(second, settings.api_prefix)
        assert a.login("ben").status_code == 200 and b.login("ben").status_code == 200
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(upload, a)
            try:
                assert entered.wait(5)
                measured = b.get("/usage").json()["measurement"]
                assert measured["pending_upload_original_bytes"] == len(PDF)
                assert measured["tracked_original_bytes"] == 0
                refused = pool.submit(upload, b).result(timeout=5)
                assert refused.status_code == 422 and refused.json()["error"]["code"] == "quota_exceeded"
            finally:
                release.set()
            assert pending.result(timeout=5).status_code == 201
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 1
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_invalid_content_releases_reserved_capacity(as_user, db_factory):
    ben = as_user("ben")
    bad = ben.post("/uploads", files={"file": ("fixture.svg", b"<svg/>", "image/svg+xml")})
    assert bad.status_code == 422
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0
    assert upload(ben).status_code == 201


def test_expired_reservation_does_not_block_admission(as_user, ids, db_factory):
    with db_factory() as db:
        db.add(
            UploadReservation(
                user_id=ids["users"]["ben"],
                bytes=1024**3,
                created_at=utcnow() - timedelta(hours=2),
                expires_at=utcnow() - timedelta(hours=1),
            )
        )
        db.commit()
    assert upload(as_user("ben")).status_code == 201
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_lost_session_cannot_commit_after_reserving(as_user, app, db_factory, monkeypatch):
    ben = as_user("ben")
    original = app.state.assets.save

    def revoke_while_writing(*args):
        from sqlalchemy import text

        with db_factory() as db:
            db.execute(
                text(
                    "update auth_sessions set revoked_at=now() where user_id=(select id from users where username='ben')"
                )
            )
            db.commit()
        return original(*args)

    monkeypatch.setattr(app.state.assets, "save", revoke_while_writing)
    assert upload(ben).status_code == 401
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0
    assert not list(app.state.settings.asset_dir.rglob("*.bin"))


def test_expiry_during_storage_prevents_commit(as_user, app, db_factory, monkeypatch):
    ben = as_user("ben")
    original = app.state.assets.save

    def expire(*args):
        from sqlalchemy import text

        with db_factory() as db:
            db.execute(
                text(
                    "update upload_reservations set created_at=now()-interval '2 hours', expires_at=now()-interval '1 hour'"
                )
            )
            db.commit()
        return original(*args)

    monkeypatch.setattr(app.state.assets, "save", expire)
    result = upload(ben)
    assert result.status_code == 422 and result.json()["error"]["code"] == "upload_reservation_expired"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
    assert not list(app.state.settings.asset_dir.rglob("*.bin"))


def test_precommit_failure_releases_reservation_and_removes_unpublished_file(
    as_user, app, db_factory, monkeypatch
):
    import pytest
    from sqlalchemy.orm import Session

    original = Session.flush

    def fail_asset_commit(db, *args, **kwargs):
        if any(isinstance(item, Asset) for item in db.new):
            raise RuntimeError("synthetic asset persistence failure")
        return original(db, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_asset_commit)
    with pytest.raises(RuntimeError, match="synthetic asset persistence failure"):
        upload(as_user("ben"))
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0
    assert not list(app.state.settings.asset_dir.rglob("*.bin"))


def test_lost_commit_reply_never_deletes_a_durable_asset(as_user, app, db_factory, monkeypatch):
    from sqlalchemy.orm import Session

    original = Session.commit

    def commit_then_raise(db):
        inserted = any(isinstance(item, Asset) for item in db.identity_map.values())
        original(db)
        if inserted:
            raise RuntimeError("synthetic lost commit reply")

    monkeypatch.setattr(Session, "commit", commit_then_raise)
    response = upload(as_user("ben"))
    assert response.status_code == 201
    assert response.json()["status"] == "provisional"
    with db_factory() as db:
        asset = db.get(Asset, response.json()["id"])
        assert asset is not None
        assert app.state.assets.path(asset.storage_key).read_bytes() == PDF
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_preview_write_failure_removes_only_this_attempt_files(as_user, app, db_factory, monkeypatch):
    import os
    from io import BytesIO

    import pytest
    from PIL import Image

    original = os.open

    def fail_preview(path, *args, **kwargs):
        if str(path).endswith(".preview.png"):
            raise OSError("synthetic preview disk-full")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail_preview)
    stream = BytesIO()
    Image.new("RGB", (4, 4), "blue").save(stream, format="PNG")
    with pytest.raises(OSError, match="synthetic preview disk-full"):
        as_user("ben").post("/uploads", files={"file": ("fixture.png", stream.getvalue(), "image/png")})
    assert not list(app.state.settings.asset_dir.rglob("*.bin"))
    assert not list(app.state.settings.asset_dir.rglob("*.tmp"))
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_storage_key_collision_never_overwrites_existing_bytes(as_user, app, db_factory, monkeypatch):
    import pytest
    from labadda import storage

    key = "a" * 24
    monkeypatch.setattr(storage.secrets, "token_urlsafe", lambda _: key)
    existing = app.state.assets.path(key)
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"previously stored fixture")
    with pytest.raises(FileExistsError):
        upload(as_user("ben"))
    assert existing.read_bytes() == b"previously stored fixture"
    assert not list(app.state.settings.asset_dir.rglob("*.tmp"))
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_unknown_commit_outcome_retains_bytes_and_pending_capacity(as_user, app, db_factory, monkeypatch):
    from sqlalchemy.orm import Session

    original = Session.commit

    def uncertain(db):
        if any(isinstance(item, Asset) for item in db.identity_map.values()):
            raise RuntimeError("synthetic unavailable commit outcome")
        return original(db)

    monkeypatch.setattr(Session, "commit", uncertain)
    ben = as_user("ben")
    result = upload(ben)
    assert result.status_code == 503 and result.json()["error"]["code"] == "upload_commit_unknown"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 1
    assert len(list(app.state.settings.asset_dir.rglob("*.bin"))) == 1
    assert ben.get("/usage").json()["measurement"]["pending_upload_original_bytes"] == len(PDF)
