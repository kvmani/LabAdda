"""T17: expected derivative bytes are distinct from observations and legacy unknowns."""

import hashlib
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from labadda.cli import alembic_config
from labadda.inspection import inspect_storage
from labadda.models import Asset
from labadda.recovery import RecoveryError, _verify_asset_reference
from tests.migration_helpers import downgrade_legacy
from tests.test_board_p3 import publish
from tests.test_chat_board import stroke


def image_upload(api):
    stream = BytesIO()
    Image.new("RGB", (22, 17), "blue").save(stream, format="PNG")
    response = api.post("/uploads", files={"file": ("private-preview.png", stream.getvalue(), "image/png")})
    assert response.status_code == 201
    return response.json()


def test_upload_records_actual_preview_bytes_and_scoped_usage(as_user, db_factory, settings):
    uploaded = image_upload(as_user("ben"))
    with db_factory() as db:
        row = db.get(Asset, uploaded["id"])
        from labadda.storage import AssetStore

        preview = AssetStore(settings.asset_dir).path(row.storage_key, preview=True).read_bytes()
        assert row.preview_size == len(preview) > 0
        assert row.preview_sha256 == hashlib.sha256(preview).hexdigest()
    own = as_user("ben").get("/usage").json()["measurement"]
    assert own["tracked_preview_bytes"] == len(preview)
    assert own["unknown_preview_files"] == 0
    assert own["complete_for_enforcement"] is False
    assert "private-preview" not in str(own)
    assert as_user("chen").get("/usage").json()["measurement"]["tracked_preview_bytes"] == 0
    site = as_user("admin").get("/admin/usage").json()["assets"]
    assert site["tracked_preview_bytes"] == len(preview)


def test_generated_snapshot_also_records_expected_preview(as_user, ids, db_factory, settings):
    ben = as_user("ben")
    w = ids["workspaces"]["section_a"]
    assert (
        ben.post(f"/workspaces/{w}/board/ops", json=stroke("preview-stroke-01", "fixture-line")).status_code
        == 200
    )
    assert publish(ben, w, w, 1).status_code == 201
    with db_factory() as db:
        row = db.scalar(select(Asset))
        assert row.preview_size > 0 and len(row.preview_sha256) == 64
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["summary"]["verified_previews"] == 1
    assert result["summary"]["preview_integrity"] == "verified_selected"


def test_legacy_preview_is_not_blessed_or_counted_as_known(as_user, db_factory, settings):
    image_upload(as_user("ben"))
    with db_factory() as db:
        row = db.scalar(select(Asset))
        row.preview_size = row.preview_sha256 = None
        db.commit()
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["summary"]["unknown_previews"] == 1
    assert result["summary"]["verified_previews"] == 0
    assert result["summary"]["readable_preview_bytes"] > 0
    assert result["summary"]["preview_integrity"] == "unverified"
    measured = as_user("ben").get("/usage").json()["measurement"]
    assert measured["tracked_preview_bytes"] == 0 and measured["unknown_preview_files"] == 1
    with db_factory() as db:
        row = db.scalar(select(Asset))
        assert row.preview_size is None and row.preview_sha256 is None


@pytest.mark.parametrize(
    "mutation,code", [("bytes", "hash_mismatch"), ("size", "size_mismatch"), ("missing", "file_unavailable")]
)
def test_corrupt_previews_report_class_and_fail_restore_validation(
    as_user, db_factory, settings, mutation, code
):
    image_upload(as_user("ben"))
    from labadda.storage import AssetStore

    store = AssetStore(settings.asset_dir)
    with db_factory() as db:
        row = db.scalar(select(Asset))
        reference = SimpleNamespace(
            storage_key=row.storage_key,
            size=row.size,
            sha256=row.sha256,
            has_preview=row.has_preview,
            preview_size=row.preview_size,
            preview_sha256=row.preview_sha256,
        )
    path = store.path(reference.storage_key, preview=True)
    if mutation == "bytes":
        path.write_bytes(b"x" * path.stat().st_size)
    elif mutation == "size":
        path.write_bytes(b"x")
    else:
        path.unlink()
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["summary"]["issues"] == [{"asset_id": str(row.id), "code": code, "file_class": "preview"}]
    assert result["summary"]["preview_integrity"] == "unverified"
    assert result["summary"]["verified_preview_bytes"] == 0
    with pytest.raises(RecoveryError, match="preview"):
        _verify_asset_reference(store, reference)
    if mutation == "bytes":
        assert path.read_bytes() == b"x" * reference.preview_size


def test_inspection_budget_cannot_claim_preview_verification(as_user, db_factory, settings):
    image_upload(as_user("ben"))
    result = inspect_storage(db_factory, settings.asset_dir, max_files=1)
    assert result["status"] == "partial"
    assert result["summary"]["preview_integrity"] == "unverified"
    assert result["summary"]["verified_previews"] == 0


@pytest.mark.parametrize(
    "size,digest", [(None, "a" * 64), (1, None), (-1, "a" * 64), (0, "a" * 64), (10, "short")]
)
def test_expected_preview_metadata_cannot_be_half_known_or_invalid(as_user, db_factory, size, digest):
    image_upload(as_user("ben"))
    with db_factory() as db:
        row = db.scalar(select(Asset))
        row.preview_size, row.preview_sha256 = size, digest
        with pytest.raises(IntegrityError):
            db.commit()


def test_known_measurements_block_destructive_downgrade(as_user, settings):
    image_upload(as_user("ben"))
    with pytest.raises(RuntimeError, match="discard integrity evidence"):
        downgrade_legacy(alembic_config(settings.database_url), "0012")
