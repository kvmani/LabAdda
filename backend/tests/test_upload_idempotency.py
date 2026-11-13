"""T16: owner-scoped upload receipts across replay, revocation and interruption."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from labadda.app import create_app
from labadda.cli import alembic_config
from labadda.models import Asset, AuthSession, Membership, UploadReceipt, UploadReservation
from labadda.reservations import release_upload, reserve_upload
from labadda.security import utcnow
from tests.conftest import Api
from tests.migration_helpers import downgrade_legacy
from tests.test_panel import pair

PDF = b"%PDF-1.4\nreceipt fixture\n%%EOF"
KEY = "upload-fixture-01"


def upload(api, key=KEY, data=PDF, name="fixture.pdf", media="application/pdf"):
    return api.post("/uploads", headers={"Idempotency-Key": key}, files={"file": (name, data, media)})


def receipt(api, key=KEY):
    return api.get(f"/uploads/requests/{key}")


def test_replay_returns_one_asset_without_charging_again(settings, ids, db_factory):
    with TestClient(create_app(replace(settings, user_quota_bytes=len(PDF)))) as client:
        bharat = Api(client, settings.api_prefix)
        assert bharat.login("bharat").status_code == 200
        first, again = upload(bharat), upload(bharat)
        assert first.status_code == again.status_code == 201
        assert first.json() == again.json()
        result = receipt(bharat)
        assert result.status_code == 200
        assert result.json()["state"] == "complete"
        assert result.json()["asset"] == first.json()
        assert "no-store" in result.headers["cache-control"]
        assert "fingerprint" not in result.json()
        assert bharat.get("/usage").json()["measurement"]["tracked_original_bytes"] == len(PDF)
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 1
        assert db.scalar(select(func.count()).select_from(UploadReceipt)) == 1
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0
    assert len(list(settings.asset_dir.rglob("*.bin"))) == 1


@pytest.mark.parametrize(
    "changes", [{"data": PDF + b"\nchanged"}, {"name": "renamed.pdf"}, {"media": "image/png"}]
)
def test_key_rejects_changed_intent(as_user, changes):
    bharat = as_user("bharat")
    original = upload(bharat)
    assert original.status_code == 201
    conflict = upload(bharat, **changes)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "upload_key_reused"
    assert receipt(bharat).json()["asset"] == original.json()


def test_receipts_are_owner_scoped_not_admin_or_sibling_discoverable(as_user):
    original = upload(as_user("bharat")).json()
    for name in ["chitra", "admin", "deepa"]:
        assert receipt(as_user(name)).status_code == 404
    own = upload(as_user("chitra"))
    assert own.status_code == 201 and own.json()["id"] != original["id"]
    assert receipt(as_user("chitra")).json()["asset"] == own.json()


def test_pending_same_key_does_not_write_twice(settings, ids, db_factory, monkeypatch):
    app = create_app(settings)
    entered, release = threading.Event(), threading.Event()
    original = app.state.assets.save

    def slow_save(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(app.state.assets, "save", slow_save)
    with TestClient(app) as first, TestClient(app) as second:
        a, b = Api(first, settings.api_prefix), Api(second, settings.api_prefix)
        assert a.login("bharat").status_code == b.login("bharat").status_code == 200
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(upload, a)
            try:
                assert entered.wait(5)
                assert receipt(b).json()["state"] == "pending"
                retry = pool.submit(upload, b).result(timeout=5)
                assert retry.status_code == 409 and retry.json()["error"]["code"] == "upload_in_progress"
            finally:
                release.set()
            assert pending.result(timeout=5).status_code == 201
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 1
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_replay_and_status_require_current_content_access(as_user, ids, db_factory):
    bharat = as_user("bharat")
    asset = upload(bharat).json()
    w = ids["workspaces"]["section_a"]
    assert (
        bharat.post(
            f"/workspaces/{w}/posts", json={"body": "receipt fixture", "attachment_ids": [asset["id"]]}
        ).status_code
        == 201
    )
    with db_factory() as db:
        db.execute(delete(Membership).where(Membership.user_id == ids["users"]["bharat"]))
        db.commit()
    assert upload(bharat).status_code == 404
    assert receipt(bharat).status_code == 404
    assert bharat.get(f"/files/{asset['id']}").status_code == 404


def test_discarded_result_cannot_be_resurrected(as_user, db_factory):
    bharat = as_user("bharat")
    asset = upload(bharat).json()
    assert bharat.delete(f"/uploads/{asset['id']}").status_code == 200
    assert upload(bharat).status_code == receipt(bharat).status_code == 410
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset)) == 0


def test_failed_attempt_remains_inspectable_and_requires_new_key(as_user, db_factory):
    bharat = as_user("bharat")
    assert upload(bharat, data=b"<svg/>", media="image/svg+xml").status_code == 422
    assert receipt(bharat).json()["state"] == "failed"
    failed = upload(bharat, data=b"<svg/>", media="image/svg+xml")
    assert failed.status_code == 409 and failed.json()["error"]["code"] == "upload_request_incomplete"
    assert upload(bharat, key="fresh-request-02").status_code == 201
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(UploadReservation)) == 0


def test_expired_pending_attempt_is_not_automatically_retried(as_user, app, db_factory, monkeypatch):
    original = Session.commit

    def uncertain(db):
        if any(isinstance(item, Asset) for item in db.identity_map.values()):
            raise RuntimeError("synthetic unknown commit")
        return original(db)

    bharat = as_user("bharat")
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", uncertain)
        assert upload(bharat).status_code == 503
    assert receipt(bharat).json()["state"] == "pending"
    with db_factory() as db:
        row = db.scalar(select(UploadReservation))
        row.created_at = utcnow() - timedelta(hours=2)
        row.expires_at = utcnow() - timedelta(hours=1)
        db.commit()
    assert receipt(bharat).json()["state"] == "expired"
    retry = upload(bharat)
    assert retry.status_code == 409 and retry.json()["error"]["code"] == "upload_request_incomplete"
    assert len(list(app.state.settings.asset_dir.rglob("*.bin"))) == 1


def test_expired_receipt_allows_key_reuse_only_after_identity_window(as_user, db_factory):
    bharat = as_user("bharat")
    first = upload(bharat).json()
    with db_factory() as db:
        row = db.scalar(select(UploadReceipt))
        row.created_at = utcnow() - timedelta(days=2)
        row.expires_at = utcnow() - timedelta(days=1)
        db.commit()
    assert receipt(bharat).status_code == 404
    second = upload(bharat, data=PDF + b"\nnew intent")
    assert second.status_code == 201 and second.json()["id"] != first["id"]


def test_lost_commit_reply_recovers_complete_receipt(as_user, app, monkeypatch):
    original = Session.commit

    def lost_reply(db):
        inserting = any(isinstance(item, Asset) for item in db.identity_map.values())
        original(db)
        if inserting:
            raise RuntimeError("synthetic lost reply")

    bharat = as_user("bharat")
    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", lost_reply)
        first = upload(bharat)
    assert first.status_code == 201
    assert receipt(bharat).json()["asset"] == upload(bharat).json() == first.json()
    assert len(list(app.state.settings.asset_dir.rglob("*.bin"))) == 1


@pytest.mark.parametrize("key", ["short", "x" * 65, "spaces are invalid", "unicode-λ"])
def test_invalid_keys_rejected(as_user, key):
    # httpx rejects non-ASCII headers itself; paths still exercise server syntax.
    if key.isascii():
        assert upload(as_user("bharat"), key=key).status_code == 422
    assert receipt(as_user("bharat"), key).status_code == 422


def test_receipts_do_not_bypass_csrf_or_signed_out_auth(as_user, make_client):
    bharat = as_user("bharat")
    assert (
        bharat.client.post(
            bharat.url("/uploads"),
            headers={"Idempotency-Key": KEY},
            files={"file": ("fixture.pdf", PDF, "application/pdf")},
        ).status_code
        == 403
    )
    assert receipt(make_client()).status_code == 401


def test_panel_cookie_cannot_read_or_replay_receipts(as_user, make_client, ids):
    assert upload(as_user("bharat")).status_code == 201
    panel = pair(as_user, make_client, ids)
    assert panel.get(f"/uploads/requests/{KEY}").status_code == 401
    assert (
        panel.api.client.post(
            panel.api.url("/uploads"),
            headers={"X-LabAdda-Panel": "1", "X-CSRF-Token": panel.csrf, "Idempotency-Key": KEY},
            files={"file": ("fixture.pdf", PDF, "application/pdf")},
        ).status_code
        == 401
    )


def test_populated_receipt_history_blocks_downgrade(as_user, settings):
    # A failed request still has identity history, independently of later
    # integrity migrations that protect populated Asset measurements.
    assert upload(as_user("bharat"), data=b"<svg/>", media="image/svg+xml").status_code == 422
    with pytest.raises(RuntimeError, match="request identity history"):
        downgrade_legacy(alembic_config(settings.database_url), "0011")


def test_expired_lease_failure_release_cannot_deadlock_new_admission(as_user, settings, ids, db_factory):  # noqa: PLR0915 — one end-to-end scenario; steps depend on the previous ones
    from types import SimpleNamespace

    as_user("bharat")
    with db_factory() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == ids["users"]["bharat"]))
        identity = SimpleNamespace(id=session.user_id, session=SimpleNamespace(id=session.id))
        first = reserve_upload(db, identity, settings, len(PDF), request_key=KEY, fingerprint="a" * 64)
        lease = db.get(UploadReservation, first.reservation_id)
        lease.created_at = utcnow() - timedelta(hours=2)
        lease.expires_at = utcnow() - timedelta(hours=1)
        db.commit()

    receipt_locked, admission_started, resume = threading.Event(), threading.Event(), threading.Event()
    release_thread = []
    admission_pid = []
    engine = db_factory.kw["bind"]

    def pause_release(conn, cursor, statement, parameters, context, executemany):  # noqa: PLR0917 — SQLAlchemy event signature
        if (
            threading.get_ident() in release_thread
            and statement.startswith("SELECT upload_receipts.")
            and "FOR UPDATE" in statement
        ):
            receipt_locked.set()
            assert resume.wait(10)

    def observe_admission(conn, cursor, statement, parameters, context, executemany):  # noqa: PLR0917 — SQLAlchemy event signature
        if (
            threading.get_ident() not in release_thread
            and statement.startswith("SELECT users.")
            and "FOR NO KEY UPDATE" in statement
        ):
            admission_pid.append(conn.connection.driver_connection.info.backend_pid)
            admission_started.set()

    def fail_old_attempt():
        release_thread.append(threading.get_ident())
        with db_factory() as db:
            release_upload(db, identity.id, first.reservation_id, first.receipt_id)

    def admit_new_attempt():
        with db_factory() as db:
            return reserve_upload(db, identity, settings, len(PDF))

    event.listen(engine, "after_cursor_execute", pause_release)
    event.listen(engine, "before_cursor_execute", observe_admission)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            releasing = pool.submit(fail_old_attempt)
            try:
                assert receipt_locked.wait(5)
                admitting = pool.submit(admit_new_attempt)
                assert admission_started.wait(5)
                # Wait for actual PostgreSQL blocking, not just a dispatched
                # query. Old receipt→lease cleanup then deadlocks; corrected
                # user→lease→receipt cleanup safely holds admission at user.
                deadline = time.monotonic() + 5
                with db_factory() as observer:
                    while not observer.scalar(
                        text("select cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": admission_pid[0]}
                    ):
                        assert time.monotonic() < deadline, "admission never blocked on cleanup"
                        time.sleep(0.01)
            finally:
                resume.set()
            releasing.result(timeout=10)
            assert admitting.result(timeout=10).reservation_id is not None
    finally:
        event.remove(engine, "after_cursor_execute", pause_release)
        event.remove(engine, "before_cursor_execute", observe_admission)
