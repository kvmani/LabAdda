"""Bounded host-operator reconciliation of unknown historical preview metadata.

Never rewrites bytes. A legacy derivative is eligible only if it exactly matches
a sanitized preview regenerated from an original matching its stored hash.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID

from sqlalchemy import select, text

from . import audit
from .models import Asset, StorageInspection
from .security import utcnow
from .storage import AssetStore


class ReconciliationStopped(Exception):
    pass


class UnsafeFile(Exception):
    pass


MAX_FILE_BYTES = 32 * 1024**2


def reconcile_previews(
    factory,
    root: Path,
    *,
    max_assets=100,
    max_bytes=100 * 1024**2,
    max_seconds=30,
    after_asset=None,
    apply=False,
    expected_plan=None,
    writers_quiesced=False,
):
    after_asset = UUID(str(after_asset)) if after_asset is not None else None
    if not 1 <= max_assets <= 1000 or not 1 <= max_bytes <= 1024**3 or not 0 < max_seconds <= 300:
        raise ValueError("Reconciliation budget is outside supported bounds")
    if apply and (not writers_quiesced or not re.fullmatch(r"[0-9a-f]{64}", expected_plan or "")):
        raise ValueError("Apply requires stopped writers and the reviewed dry-run plan digest")
    if not apply and (expected_plan is not None or writers_quiesced):
        raise ValueError("Application confirmation is only valid with apply")
    began = time.monotonic()
    summary = {
        "source": "operator_cli",
        "scope": "preview_metadata_reconciliation",
        "mode": "apply" if apply else "dry_run",
        "complete_for_enforcement": False,
        "checked_assets": 0,
        "candidate_count": 0,
        "applied_count": 0,
        "issue_count": 0,
        "issues": [],
        "issues_truncated": False,
        "bytes_read": 0,
        "budget": {"assets": max_assets, "bytes": max_bytes, "seconds": float(max_seconds)},
        "time_budget_kind": "cooperative_scan_only",
        "concurrent_changes_possible": not apply,
    }
    summary["after_asset"] = str(after_asset) if after_asset is not None else None
    with factory() as db:
        receipt = StorageInspection(status="running", summary=summary.copy(), created_at=utcnow())
        db.add(receipt)
        db.commit()
        receipt_id = receipt.id
    store = AssetStore(root)
    commit_started = False

    def budget():
        if time.monotonic() - began >= max_seconds:
            raise ReconciliationStopped("time_budget_exhausted")

    def read_file(path, size=None, digest=None):
        budget()
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise UnsafeFile("unsafe_path")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise UnsafeFile("not_regular")
            if before.st_size > MAX_FILE_BYTES:
                raise UnsafeFile("file_size_limit")
            if size is not None and before.st_size != size:
                raise UnsafeFile("original_size_mismatch")
            if before.st_size + summary["bytes_read"] > max_bytes:
                raise ReconciliationStopped("byte_budget_exhausted")
            chunks = []
            file_bytes = 0
            while True:
                budget()
                chunk = stream.read(
                    min(256 * 1024, max_bytes - summary["bytes_read"] + 1, MAX_FILE_BYTES - file_bytes + 1)
                )
                if not chunk:
                    break
                summary["bytes_read"] += len(chunk)
                file_bytes += len(chunk)
                if file_bytes > MAX_FILE_BYTES:
                    raise UnsafeFile("file_size_limit")
                if summary["bytes_read"] > max_bytes:
                    raise ReconciliationStopped("byte_budget_exhausted")
                chunks.append(chunk)
            after = os.fstat(stream.fileno())
            fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            if any(getattr(before, f) != getattr(after, f) for f in fields):
                raise UnsafeFile("changed_during_read")
        data = b"".join(chunks)
        if len(data) != before.st_size or (digest is not None and hashlib.sha256(data).hexdigest() != digest):
            raise UnsafeFile("original_hash_mismatch")
        return data

    def issue(asset_id, code):
        summary["issue_count"] += 1
        if len(summary["issues"]) < 100:
            summary["issues"].append({"asset_id": str(asset_id), "code": code})
        else:
            summary["issues_truncated"] = True

    try:
        if root.is_symlink() or not root.is_dir():
            raise ReconciliationStopped("asset_root_unavailable")
        with factory() as db:
            db.execute(text("set local statement_timeout = '2s'"))
            if apply and not db.scalar(
                text("select pg_try_advisory_xact_lock(hashtext('labadda_preview_reconciliation'))")
            ):
                raise ReconciliationStopped("reconciliation_busy")
            query = (
                select(Asset)
                .where(Asset.has_preview, Asset.preview_size.is_(None))
                .order_by(Asset.id)
                .limit(max_assets + 1)
            )
            if after_asset is not None:
                query = query.where(Asset.id > after_asset)
            if apply:
                query = query.with_for_update()
            rows = db.scalars(query).all()
            summary["more_unknown_assets"] = len(rows) > max_assets
            rows = rows[:max_assets]
            summary["next_after_asset"] = str(rows[-1].id) if summary["more_unknown_assets"] else None
            plan, candidates = [], []
            for row in rows:
                budget()
                summary["checked_assets"] += 1
                try:
                    original = read_file(store.path(row.storage_key), row.size, row.sha256)
                    regenerated = store._sanitized_preview(original)
                    budget()  # Rendering is bounded by image dimensions, not a hard deadline.
                    preview = read_file(store.path(row.storage_key, preview=True))
                    if preview != regenerated:
                        raise UnsafeFile("preview_regeneration_mismatch")
                    digest = hashlib.sha256(regenerated).hexdigest()
                    candidates.append((row, len(regenerated), digest))
                    summary["candidate_count"] = len(candidates)
                    plan.append(
                        [str(row.id), row.storage_key, row.size, row.sha256, len(regenerated), digest]
                    )
                except ReconciliationStopped:
                    raise
                except Exception as exc:
                    code = str(exc) if isinstance(exc, UnsafeFile) else "validation_unavailable"
                    issue(row.id, code)
                    plan.append([str(row.id), code])
            summary["candidate_count"] = len(candidates)
            # Includes bounded selection, recipe and budgets. No raw content,
            # names, paths or individual content digests enter the public receipt.
            payload = [
                1,
                "sanitized_png_v1",
                summary["budget"],
                summary["after_asset"],
                summary["more_unknown_assets"],
                plan,
            ]
            summary["plan_digest"] = hashlib.sha256(
                json.dumps(payload, separators=(",", ":")).encode()
            ).hexdigest()
            if apply:
                if summary["plan_digest"] != expected_plan:
                    raise ReconciliationStopped("plan_changed")
                for row, size, digest in candidates:
                    row.preview_size, row.preview_sha256 = size, digest
                summary["applied_count"] = len(candidates)
            summary["state"] = "applied" if apply else "dry_run"
            receipt = db.get(StorageInspection, receipt_id, with_for_update=True)
            receipt.status, receipt.summary, receipt.finished_at = "completed", summary, utcnow()
            audit.record(
                db,
                actor=None,
                action="storage.preview_reconcile",
                scope_type="site",
                target_id=receipt_id,
                mode=summary["mode"],
                plan_digest=summary["plan_digest"],
            )
            commit_started = True
            db.commit()
        return {"id": str(receipt_id), "status": "completed", "summary": summary}
    except Exception as exc:
        if commit_started:
            # A lost commit reply must not overwrite a possibly completed job.
            with factory() as fresh:
                receipt = fresh.get(StorageInspection, receipt_id)
                if receipt.status == "completed":
                    return {"id": str(receipt_id), "status": receipt.status, "summary": receipt.summary}
            return {
                "id": str(receipt_id),
                "status": "uncertain",
                "summary": {"state": "commit_unknown", "applied_count": None},
            }
        summary.update(
            state="stopped",
            applied_count=0,
            stop_reason=str(exc) if isinstance(exc, ReconciliationStopped) else "reconciliation_unavailable",
        )
        summary.pop("plan_digest", None)  # A stopped attempt cannot supply application confirmation.
        with factory() as db:
            receipt = db.get(StorageInspection, receipt_id)
            receipt.status, receipt.summary, receipt.finished_at = "failed", summary, utcnow()
            audit.record(
                db,
                actor=None,
                action="storage.preview_reconcile",
                scope_type="site",
                target_id=receipt_id,
                outcome="failed",
                mode=summary["mode"],
                stop_reason=summary["stop_reason"],
            )
            db.commit()
        return {"id": str(receipt_id), "status": "failed", "summary": summary}
