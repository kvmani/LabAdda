"""Bounded, metadata-only asset-directory observations; never a deletion plan.

Directory descriptors prevent symlink traversal during enumeration. Only the
store's two-level layout is traversed. No names, keys or content enter receipts.
"""
import math
import os
from pathlib import Path
import re
import stat
import time

from sqlalchemy import select, text

from . import audit
from .models import Asset, StorageInspection
from .security import utcnow


class InventoryLimit(Exception):
    pass


def inventory_storage(factory, root: Path, *, max_entries: int = 10000,
                      max_assets: int = 10000, max_seconds: float = 30, checkpoint=None, job_context: dict | None = None) -> dict:
    if (type(max_entries) is not int or not 1 <= max_entries <= 100000
            or type(max_assets) is not int or not 1 <= max_assets <= 100000
            or not math.isfinite(max_seconds) or not 0 < max_seconds <= 300):
        raise ValueError('Inventory budget is outside supported bounds')
    began = time.monotonic()
    summary = {
        'source': 'operator_cli', 'scope': 'asset_directory_inventory',
        'state': 'partial', 'complete_for_enforcement': False,
        'concurrent_changes_possible': True, 'deletion_authorized': False,
        'time_budget_kind': 'cooperative_scan_only',
        'budget': {'entries': max_entries, 'assets': max_assets, 'seconds': max_seconds},
        'checked_entries': 0, 'regular_file_entries': 0, 'unique_files': 0,
        'apparent_bytes': 0, 'allocated_bytes': 0, 'hardlink_aliases': 0,
        'issue_count': 0, 'issues_by_code': {}, 'classes': {},
        'unmeasured': ['database', 'outside_asset_root', 'file_integrity', 'missing_referenced_files',
                       'directory_metadata', 'shared_extent_deduplication'],
    }
    if job_context is not None:
        summary["job"] = dict(job_context)
    with factory() as db:
        receipt = StorageInspection(status='running', summary=summary, created_at=utcnow())
        db.add(receipt)
        db.commit()
        receipt_id = receipt.id

    def issue(code):
        summary['issue_count'] += 1
        counts = summary['issues_by_code']
        counts[code] = counts.get(code, 0) + 1

    def check_time():
        if checkpoint is not None:
            checkpoint()
        if time.monotonic() - began >= max_seconds:
            raise InventoryLimit()

    seen = set()
    status = 'partial'
    try:
        with factory() as db:
            db.execute(text("set local statement_timeout = '2s'"))
            rows = db.execute(select(Asset.storage_key, Asset.has_preview)
                              .order_by(Asset.id).limit(max_assets + 1)).all()
        if len(rows) > max_assets:
            summary['stop_reason'] = 'reference_budget_exhausted'
            raise InventoryLimit()
        references = {key: preview for key, preview in rows}
        summary['observed_asset_rows'] = len(rows)
        check_time()
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        root_fd = os.open(root, flags)
        try:
            root_device = os.fstat(root_fd).st_dev

            def scan(directory_fd, shard=None):
                with os.scandir(directory_fd) as entries:
                    for entry in entries:
                        check_time()
                        if summary['checked_entries'] >= max_entries:
                            raise InventoryLimit()
                        summary['checked_entries'] += 1
                        try:
                            info = entry.stat(follow_symlinks=False)
                            if stat.S_ISDIR(info.st_mode):
                                if shard is not None or not re.fullmatch(r'[A-Za-z0-9_-]{2}', entry.name):
                                    issue('unsupported_directory')
                                    continue
                                child = os.open(entry.name, flags, dir_fd=directory_fd)
                                try:
                                    opened = os.fstat(child)
                                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                                        issue('changed_directory')
                                    elif opened.st_dev != root_device:
                                        issue('different_filesystem')
                                    else:
                                        scan(child, entry.name)
                                finally:
                                    os.close(child)
                                continue
                            if not stat.S_ISREG(info.st_mode):
                                issue('symlink_or_special_file')
                                continue
                            summary['regular_file_entries'] += 1
                            identity = (info.st_dev, info.st_ino)
                            # Aggregate physical totals count each inode once. Class totals
                            # count directory entries, since aliases may cross classes.
                            if identity in seen:
                                summary['hardlink_aliases'] += 1
                            else:
                                seen.add(identity)
                                summary['unique_files'] += 1
                                summary['apparent_bytes'] += info.st_size
                                summary['allocated_bytes'] += info.st_blocks * 512
                            match = re.fullmatch(r'([A-Za-z0-9_-]{20,80})(\.bin|\.preview\.png|\.tmp)', entry.name)
                            kind = 'unexpected'
                            if match and shard == match[1][:2]:
                                key, suffix = match.groups()
                                if suffix == '.tmp':
                                    kind = 'temporary'
                                elif key in references and (suffix == '.bin' or references[key]):
                                    kind = 'referenced_original' if suffix == '.bin' else 'referenced_preview'
                                else:
                                    kind = 'unreferenced_candidate'
                            bucket = summary['classes'].setdefault(kind, {'entries': 0, 'apparent_bytes': 0})
                            bucket['entries'] += 1
                            bucket['apparent_bytes'] += info.st_size
                        except OSError:
                            issue('entry_unavailable')
            scan(root_fd)
        finally:
            os.close(root_fd)
        status = 'completed'
        summary['state'] = 'observed' if not summary['issue_count'] else 'partial'
    except InventoryLimit:
        summary.setdefault('stop_reason', 'scan_budget_exhausted')
    except Exception:
        status = 'failed'
        summary['stop_reason'] = 'inventory_unavailable'
    summary['selected_pass_complete'] = status == 'completed' and not summary['issue_count']
    summary['elapsed_seconds'] = round(time.monotonic() - began, 3)
    with factory() as db:
        receipt = db.get(StorageInspection, receipt_id)
        receipt.status, receipt.summary, receipt.finished_at = status, summary, utcnow()
        audit.record(db, actor=None, action='storage.inventory', scope_type='site',
                     target_id=receipt_id, outcome=status, source='operator_cli')
        db.commit()
    return {'id': str(receipt_id), 'status': status, 'summary': summary}
