"""T17: bounded physical inventory, no file mutation or metadata disclosure."""

import json
import os

import pytest
from sqlalchemy import select

from labadda.inventory import inventory_storage
from labadda.models import Asset, StorageInspection


def test_inventory_classification_and_private_receipt(as_user, settings, db_factory):
    api = as_user("bharat")
    payload = b"%PDF-1.4\nfixture\n%%EOF"
    assert (
        api.post("/uploads", files={"file": ("private-title.pdf", payload, "application/pdf")}).status_code
        == 201
    )
    with db_factory() as db:
        key = db.scalar(select(Asset.storage_key))
    shard = settings.asset_dir / "zz"
    shard.mkdir()
    (shard / ("z" * 24 + ".bin")).write_bytes(b"orphan")
    (shard / ("z" * 24 + ".tmp")).write_bytes(b"temp")
    (shard / "private-unexpected-name").write_bytes(b"other")
    result = inventory_storage(db_factory, settings.asset_dir)
    summary = result["summary"]
    assert result["status"] == "completed"
    assert summary["selected_pass_complete"]
    assert summary["apparent_bytes"] == len(payload) + 6 + 4 + 5
    assert summary["classes"]["referenced_original"]["apparent_bytes"] == len(payload)
    assert summary["classes"]["unreferenced_candidate"]["entries"] == 1
    assert summary["classes"]["temporary"]["entries"] == 1
    assert summary["classes"]["unexpected"]["entries"] == 1
    assert not summary["deletion_authorized"] and not summary["complete_for_enforcement"]
    receipt = as_user("admin").get("/admin/storage-inspections").json()["inspections"][0]
    assert receipt["id"] == result["id"]
    assert key not in json.dumps(receipt) and "private" not in json.dumps(receipt)
    assert api.get("/admin/storage-inspections").status_code == 403
    assert (shard / ("z" * 24 + ".bin")).read_bytes() == b"orphan"


def test_hardlinks_count_once_in_physical_total(settings, db_factory, ids):
    settings.asset_dir.mkdir()
    first = settings.asset_dir / "one"
    first.write_bytes(b"1234567")
    os.link(first, settings.asset_dir / "two")
    s = inventory_storage(db_factory, settings.asset_dir)["summary"]
    assert s["unique_files"] == 1 and s["hardlink_aliases"] == 1
    assert s["apparent_bytes"] == 7
    assert s["allocated_bytes"] == first.stat().st_blocks * 512
    assert s["classes"]["unexpected"] == {"entries": 2, "apparent_bytes": 14}


def test_symlinks_special_and_nested_directories_are_not_followed(settings, db_factory, ids, tmp_path):
    root = settings.asset_dir
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"x" * 123)
    (root / "aa").symlink_to(outside, target_is_directory=True)
    (root / "link").symlink_to(outside / "secret")
    os.mkfifo(root / "pipe")
    (root / "bb").mkdir()
    (root / "bb" / "cc").mkdir()
    (root / "bb" / "cc" / "hidden").write_bytes(b"x")
    s = inventory_storage(db_factory, root)["summary"]
    assert not s["selected_pass_complete"]
    assert s["apparent_bytes"] == 0
    assert s["issues_by_code"] == {"symlink_or_special_file": 3, "unsupported_directory": 1}


def test_root_symlink_and_missing_root_fail(settings, db_factory, ids, tmp_path):
    assert inventory_storage(db_factory, settings.asset_dir)["status"] == "failed"
    settings.asset_dir.symlink_to(tmp_path, target_is_directory=True)
    assert inventory_storage(db_factory, settings.asset_dir)["status"] == "failed"


def test_entry_budget_counts_directories_and_never_claims_completion(settings, db_factory, ids):
    settings.asset_dir.mkdir()
    for name in ("aa", "bb", "cc"):
        (settings.asset_dir / name).mkdir()
    result = inventory_storage(db_factory, settings.asset_dir, max_entries=2)
    assert result["status"] == "partial"
    assert result["summary"]["checked_entries"] == 2
    assert result["summary"]["stop_reason"] == "scan_budget_exhausted"


def test_reference_budget_stops_before_classifying_files(as_user, settings, db_factory):
    api = as_user("bharat")
    for _ in range(2):
        assert (
            api.post("/uploads", files={"file": ("a.pdf", b"%PDF-1.4\na", "application/pdf")}).status_code
            == 201
        )
    result = inventory_storage(db_factory, settings.asset_dir, max_assets=1)
    assert result["status"] == "partial"
    assert result["summary"]["stop_reason"] == "reference_budget_exhausted"
    assert result["summary"]["checked_entries"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_seconds": float("nan")},
        {"max_seconds": float("inf")},
        {"max_entries": True},
        {"max_assets": 0},
        {"max_entries": 100001},
    ],
)
def test_invalid_budgets_do_not_create_receipts(settings, db_factory, ids, kwargs):
    with pytest.raises(ValueError):
        inventory_storage(db_factory, settings.asset_dir, **kwargs)
    with db_factory() as db:
        assert db.scalar(select(StorageInspection)) is None


def test_cli_receipt_and_nonzero_for_incomplete(settings, db_factory, ids, monkeypatch, capsys):
    from labadda import cli

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    assert cli.main(["inventory-storage"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    settings.asset_dir.mkdir()
    assert cli.main(["inventory-storage"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["selected_pass_complete"]


def test_shard_replacement_during_open_is_not_traversed(settings, db_factory, ids, tmp_path, monkeypatch):
    from labadda import inventory

    root = settings.asset_dir
    root.mkdir()
    (root / "aa").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"secret")
    real_open = inventory.os.open

    def replace_shard(path, flags, **kwargs):
        if path == "aa":
            (root / "aa").rmdir()
            (root / "aa").symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, **kwargs)

    monkeypatch.setattr(inventory.os, "open", replace_shard)
    s = inventory_storage(db_factory, root)["summary"]
    assert s["issues_by_code"] == {"entry_unavailable": 1}
    assert not s["selected_pass_complete"] and s["apparent_bytes"] == 0


def test_elapsed_budget_records_partial_receipt(settings, db_factory, ids, monkeypatch):
    from labadda import inventory

    ticks = iter([0, 2, 2])
    monkeypatch.setattr(inventory.time, "monotonic", lambda: next(ticks))
    result = inventory_storage(db_factory, settings.asset_dir, max_seconds=1)
    assert result["status"] == "partial"
    assert result["summary"]["stop_reason"] == "scan_budget_exhausted"
