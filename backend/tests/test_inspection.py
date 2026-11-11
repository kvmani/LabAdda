"""P5.1 bounded referenced-file inspection must not repair or expose content."""

import pytest

from labadda.inspection import inspect_storage


def upload(api):
    response = api.post(
        "/uploads", files={"file": ("sensitive-label.pdf", b"%PDF-1.4\nfixture\n%%EOF", "application/pdf")}
    )
    assert response.status_code == 201
    return response.json()


def test_referenced_original_hash_and_admin_receipt(as_user, settings, db_factory):
    asset = upload(as_user("ben"))
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["status"] == "completed"
    assert result["summary"]["verified_original_bytes"] == asset["size"]
    assert not result["summary"]["complete_for_enforcement"]
    assert result["summary"]["issue_count"] == 0
    assert as_user("ben").get("/admin/storage-inspections").status_code == 403
    receipt = as_user("admin").get("/admin/storage-inspections").json()["inspections"][0]
    assert receipt["id"] == result["id"]
    assert "sensitive-label" not in str(receipt)
    assert not as_user("admin").get("/admin/storage-inspections").json()["enforcement_authority"]


@pytest.mark.parametrize(
    "mutation,code", [("missing", "file_unavailable"), ("bytes", "hash_mismatch"), ("link", "unsafe_path")]
)
def test_mismatches_are_reported_never_repaired(as_user, settings, db_factory, mutation, code):
    upload(as_user("ben"))
    path = next(settings.asset_dir.rglob("*.bin"))
    if mutation == "missing":
        path.unlink()
    elif mutation == "bytes":
        data = path.read_bytes()
        path.write_bytes(b"x" * len(data))
    else:
        path.unlink()
        path.symlink_to("/etc/passwd")
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["summary"]["issue_count"] == 1
    assert result["summary"]["issues"][0]["code"] == code
    assert result["summary"]["state"] == "partial"
    if mutation == "bytes":
        assert path.read_bytes() == b"x" * len(data)
    if mutation == "link":
        assert path.is_symlink()


def test_byte_budget_stops_without_false_completion(as_user, settings, db_factory):
    upload(as_user("ben"))
    result = inspect_storage(db_factory, settings.asset_dir, max_bytes=1)
    assert result["status"] == "partial"
    assert result["summary"]["stop_reason"] == "budget_exhausted"
    assert result["summary"]["bytes_read"] == 0


def test_missing_asset_root_persists_failed_result(settings, db_factory):
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["status"] == "failed"
    assert result["summary"]["stop_reason"] == "inspection_unavailable"


def test_preview_bytes_are_distinct_from_original_bytes(as_user, settings, db_factory):
    from io import BytesIO
    from PIL import Image

    stream = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(stream, format="PNG")
    response = as_user("ben").post(
        "/uploads", files={"file": ("fixture.png", stream.getvalue(), "image/png")}
    )
    assert response.status_code == 201
    result = inspect_storage(db_factory, settings.asset_dir)
    assert result["summary"]["verified_original_bytes"] == len(stream.getvalue())
    assert result["summary"]["readable_preview_bytes"] > 0
    assert result["summary"]["checked_files"] == 2
    assert result["summary"]["preview_integrity"] == "verified_selected"
    assert result["summary"]["verified_preview_bytes"] == result["summary"]["readable_preview_bytes"]
    assert result["summary"]["state"] == "partial"


def test_file_budget_includes_previews(as_user, settings, db_factory):
    from io import BytesIO
    from PIL import Image

    stream = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(stream, format="PNG")
    assert (
        as_user("ben")
        .post("/uploads", files={"file": ("fixture.png", stream.getvalue(), "image/png")})
        .status_code
        == 201
    )
    result = inspect_storage(db_factory, settings.asset_dir, max_files=1)
    assert result["status"] == "partial"
    assert result["summary"]["stop_reason"] == "budget_exhausted"
