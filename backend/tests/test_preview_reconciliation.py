"""Metadata repair requires verified originals, exact legacy bytes and reviewed plans."""

import hashlib

import pytest
from sqlalchemy import func, select

from labadda.models import Asset, StorageInspection
from labadda.preview_reconciliation import reconcile_previews
from tests.test_preview_integrity import image_upload


def legacy(as_user, db_factory, settings):
    uploaded = image_upload(as_user("ben"))
    from labadda.storage import AssetStore

    store = AssetStore(settings.asset_dir)
    with db_factory() as db:
        row = db.get(Asset, uploaded["id"])
        key = row.storage_key
        row.preview_size = row.preview_sha256 = None
        db.commit()
    return uploaded["id"], store.path(key), store.path(key, preview=True)


def run(db_factory, settings, **kw):
    return reconcile_previews(db_factory, settings.asset_dir, **kw)


def test_dry_run_and_reviewed_application_only_fill_verified_metadata(as_user, db_factory, settings):
    asset_id, original, preview = legacy(as_user, db_factory, settings)
    before = {path: path.read_bytes() for path in (original, preview)}
    planned = run(db_factory, settings)
    assert planned["status"] == "completed" and planned["summary"]["mode"] == "dry_run"
    assert planned["summary"]["candidate_count"] == 1 and planned["summary"]["applied_count"] == 0
    assert not planned["summary"]["complete_for_enforcement"]
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is None
    applied = run(
        db_factory,
        settings,
        apply=True,
        writers_quiesced=True,
        expected_plan=planned["summary"]["plan_digest"],
    )
    assert applied["status"] == "completed" and applied["summary"]["applied_count"] == 1
    with db_factory() as db:
        row = db.get(Asset, asset_id)
        assert row.preview_size == len(before[preview])
        assert row.preview_sha256 == hashlib.sha256(before[preview]).hexdigest()
    assert {path: path.read_bytes() for path in before} == before
    receipt = as_user("admin").get("/admin/storage-inspections").json()
    assert "private-preview" not in str(receipt)
    assert hashlib.sha256(before[preview]).hexdigest() not in str(receipt)
    assert as_user("chen").get("/admin/storage-inspections").status_code == 403


@pytest.mark.parametrize(
    "options",
    [
        {"apply": True},
        {"apply": True, "expected_plan": "a" * 64},
        {"apply": True, "writers_quiesced": True, "expected_plan": "invalid"},
        {"expected_plan": "a" * 64},
    ],
)
def test_application_confirmation_is_required_before_any_work(db_factory, settings, ids, options):
    with pytest.raises(ValueError):
        run(db_factory, settings, **options)
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(StorageInspection)) == 0


def test_changed_plan_fails_without_metadata_or_file_mutation(as_user, db_factory, settings):
    asset_id, _, preview = legacy(as_user, db_factory, settings)
    planned = run(db_factory, settings)
    corrupted = b"x" * preview.stat().st_size
    preview.write_bytes(corrupted)
    applied = run(
        db_factory,
        settings,
        apply=True,
        writers_quiesced=True,
        expected_plan=planned["summary"]["plan_digest"],
    )
    assert applied["status"] == "failed" and applied["summary"]["stop_reason"] == "plan_changed"
    assert applied["summary"]["applied_count"] == 0
    assert "plan_digest" not in applied["summary"]
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is None
    assert preview.read_bytes() == corrupted


def test_original_corruption_cannot_bless_an_existing_preview(as_user, db_factory, settings):
    asset_id, original, _ = legacy(as_user, db_factory, settings)
    original.write_bytes(b"x" * original.stat().st_size)
    result = run(db_factory, settings)
    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["issues"][0]["code"] == "original_hash_mismatch"
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is None


def test_budget_exhaustion_stops_before_any_application(as_user, db_factory, settings):
    asset_id, _, _ = legacy(as_user, db_factory, settings)
    result = run(db_factory, settings, max_bytes=1)
    assert result["status"] == "failed" and result["summary"]["stop_reason"] == "byte_budget_exhausted"
    assert "plan_digest" not in result["summary"]
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is None


def test_bounded_batches_are_explicit_and_completed_plan_cannot_repeat(as_user, db_factory, settings):
    legacy(as_user, db_factory, settings)
    legacy(as_user, db_factory, settings)
    planned = run(db_factory, settings, max_assets=1)
    assert planned["summary"]["more_unknown_assets"] is True
    assert planned["summary"]["checked_assets"] == 1
    args = {
        "max_assets": 1,
        "apply": True,
        "writers_quiesced": True,
        "expected_plan": planned["summary"]["plan_digest"],
    }
    assert run(db_factory, settings, **args)["summary"]["applied_count"] == 1
    assert run(db_factory, settings, **args)["summary"]["stop_reason"] == "plan_changed"
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Asset).where(Asset.preview_size.is_(None))) == 1


def test_symlinked_preview_is_never_trusted(as_user, db_factory, settings):
    _, original, preview = legacy(as_user, db_factory, settings)
    preview.unlink()
    preview.symlink_to(original)
    result = run(db_factory, settings)
    assert result["summary"]["candidate_count"] == 0
    assert result["summary"]["issues"][0]["code"] == "unsafe_path"
    assert preview.is_symlink()


def test_cursor_can_continue_past_an_unrepairable_batch(as_user, db_factory, settings):
    first = legacy(as_user, db_factory, settings)
    second = legacy(as_user, db_factory, settings)
    ordered = sorted([first, second], key=lambda item: item[0])
    ordered[0][2].write_bytes(b"invalid legacy preview")
    planned = run(db_factory, settings, max_assets=1)
    assert planned["summary"]["candidate_count"] == 0
    assert planned["summary"]["more_unknown_assets"]
    cursor = planned["summary"]["next_after_asset"]
    next_plan = run(db_factory, settings, max_assets=1, after_asset=cursor)
    assert next_plan["summary"]["candidate_count"] == 1
    assert next_plan["summary"]["more_unknown_assets"] is False
    applied = run(
        db_factory,
        settings,
        max_assets=1,
        after_asset=cursor,
        apply=True,
        writers_quiesced=True,
        expected_plan=next_plan["summary"]["plan_digest"],
    )
    assert applied["summary"]["applied_count"] == 1
    with db_factory() as db:
        assert db.get(Asset, ordered[0][0]).preview_size is None
        assert db.get(Asset, ordered[1][0]).preview_size is not None


def test_growing_file_cannot_exceed_per_file_read_bound(as_user, db_factory, settings, monkeypatch):
    _, original, _ = legacy(as_user, db_factory, settings)
    import os

    from labadda import preview_reconciliation

    cap = original.stat().st_size + 10
    monkeypatch.setattr(preview_reconciliation, "MAX_FILE_BYTES", cap)
    fstat = os.fstat
    grown = False

    def grow_after_first_stat(fd):
        nonlocal grown
        before = fstat(fd)
        if not grown and os.readlink(f"/proc/self/fd/{fd}") == str(original):
            grown = True
            with original.open("ab") as stream:
                stream.write(b"x" * (cap + 10))
        return before

    monkeypatch.setattr(preview_reconciliation.os, "fstat", grow_after_first_stat)
    result = run(db_factory, settings)
    assert grown and result["summary"]["issues"][0]["code"] == "file_size_limit"
    assert result["summary"]["bytes_read"] <= cap + 1
    assert result["summary"]["candidate_count"] == 0


def test_audit_failure_rolls_back_metadata_application(as_user, db_factory, settings, monkeypatch):
    asset_id, _, _ = legacy(as_user, db_factory, settings)
    planned = run(db_factory, settings)
    from labadda import preview_reconciliation

    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic audit unavailable")

    monkeypatch.setattr(preview_reconciliation.audit, "record", unavailable)
    with pytest.raises(RuntimeError, match="synthetic audit unavailable"):
        run(
            db_factory,
            settings,
            apply=True,
            writers_quiesced=True,
            expected_plan=planned["summary"]["plan_digest"],
        )
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is None


def test_lost_commit_reply_recovers_atomic_application_receipt(as_user, db_factory, settings, monkeypatch):
    asset_id, _, _ = legacy(as_user, db_factory, settings)
    planned = run(db_factory, settings)
    from sqlalchemy.orm import Session

    original = Session.commit

    def commit_then_lose(db):
        applying = any(isinstance(row, Asset) for row in db.dirty)
        original(db)
        if applying:
            raise RuntimeError("synthetic lost commit reply")

    monkeypatch.setattr(Session, "commit", commit_then_lose)
    result = run(
        db_factory,
        settings,
        apply=True,
        writers_quiesced=True,
        expected_plan=planned["summary"]["plan_digest"],
    )
    assert result["status"] == "completed" and result["summary"]["applied_count"] == 1
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is not None


def test_operator_cli_dry_run_and_explicit_apply(as_user, db_factory, settings, monkeypatch, capsys):
    import json

    from labadda import cli

    asset_id, _, _ = legacy(as_user, db_factory, settings)
    # No scheduler or server process writes to this disposable test database.
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    assert cli.main(["reconcile-previews"]) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["summary"]["applied_count"] == 0
    assert (
        cli.main(
            [
                "reconcile-previews",
                "--apply",
                "--writers-quiesced",
                "--expected-plan",
                planned["summary"]["plan_digest"],
            ]
        )
        == 0
    )
    applied = json.loads(capsys.readouterr().out)
    assert applied["summary"]["applied_count"] == 1
    with db_factory() as db:
        assert db.get(Asset, asset_id).preview_size is not None


def test_operator_cli_refuses_unconfirmed_apply(db_factory, settings, ids, monkeypatch, capsys):
    from labadda import cli

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    assert cli.main(["reconcile-previews", "--apply"]) == 2
    assert "unconfirmed" in capsys.readouterr().err
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(StorageInspection)) == 0


def test_regeneration_enforces_pixel_ceiling_before_decode(as_user, app, monkeypatch):
    from labadda import storage

    monkeypatch.setattr(storage.Image, "MAX_IMAGE_PIXELS", 400)
    from io import BytesIO

    stream = BytesIO()
    storage.Image.new("RGB", (21, 20), "blue").save(stream, format="PNG")
    with pytest.warns(storage.Image.DecompressionBombWarning):
        result = as_user("ben").post(
            "/uploads", files={"file": ("oversized.png", stream.getvalue(), "image/png")}
        )
    assert result.status_code == 422 and result.json()["error"]["code"] == "image_too_large"
    assert not list(app.state.settings.asset_dir.rglob("*.bin"))
