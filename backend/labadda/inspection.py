"""Bounded non-destructive inspection of database-referenced asset files.

Does not enumerate or delete unreferenced files, repair counters or authorize purge.
Run as the trusted host operator. A live filesystem is not a transactional snapshot.
"""
import hashlib
import stat
import time
import os
from pathlib import Path

from sqlalchemy import func, select, text

from . import audit
from .models import Asset, StorageInspection
from .security import utcnow
from .storage import AssetStore


class BudgetExceeded(Exception):
    pass


def inspect_storage(factory, root: Path, *, max_files: int = 10000, max_bytes: int = 1024**3,
                    max_seconds: float = 30) -> dict:
    if not 1 <= max_files <= 100000 or not 1 <= max_bytes <= 10*1024**3 or not 0 < max_seconds <= 300:
        raise ValueError('Inspection budget is outside supported bounds')
    began = time.monotonic()
    with factory() as db:
        row = StorageInspection(status='running', summary={'source':'operator_cli', 'complete_for_enforcement':False}, created_at=utcnow())
        db.add(row); db.commit(); inspection_id = row.id
    summary = {'source':'operator_cli', 'state':'partial', 'complete_for_enforcement':False,
               'scope':'database_referenced_assets', 'checked_assets':0, 'checked_files':0,
               'verified_original_bytes':0, 'readable_preview_bytes':0, 'bytes_read':0,
               'verified_preview_bytes':0, 'verified_previews':0, 'unknown_previews':0, 'selected_previews':0,
               'issue_count':0, 'issues':[], 'issues_truncated':False,
               'budget':{'files':max_files,'bytes':max_bytes,'seconds':max_seconds},
               'unmeasured':['unreferenced_files','text_and_board_bytes','reservations','trash','archives'],
               'concurrent_changes_possible':True, 'preview_integrity':'unverified',
               'time_budget_kind':'cooperative_scan_only'}
    store = AssetStore(root)
    def issue(asset_id, code, file_class):
        summary['issue_count'] += 1
        if len(summary['issues']) < 100:
            summary['issues'].append({'asset_id':str(asset_id),'code':code,'file_class':file_class})
        else:
            summary['issues_truncated'] = True
    def check_budget():
        if time.monotonic()-began >= max_seconds or summary['checked_files'] >= max_files:
            raise BudgetExceeded()
    def check_file(path, asset_id, size=None, expected_hash=None, file_class='original'):
        check_budget()
        summary['checked_files'] += 1
        # No following a final symlink; parents must resolve beneath this private root.
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            issue(asset_id,'unsafe_path',file_class); return None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    issue(asset_id,'not_regular',file_class); return None
                if size is not None and before.st_size != size:
                    issue(asset_id,'size_mismatch',file_class); return None
                if summary['bytes_read'] + before.st_size > max_bytes:
                    raise BudgetExceeded()
                h = hashlib.sha256(); read = 0
                while True:
                    if time.monotonic()-began >= max_seconds:
                        raise BudgetExceeded()
                    chunk = stream.read(min(256*1024, max_bytes-summary['bytes_read']+1))
                    if not chunk: break
                    summary['bytes_read'] += len(chunk); read += len(chunk)
                    if summary['bytes_read'] > max_bytes: raise BudgetExceeded()
                    h.update(chunk)
                after = os.fstat(stream.fileno())
                if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns) or read != before.st_size:
                    issue(asset_id,'changed_during_read',file_class); return None
                if expected_hash is not None and h.hexdigest() != expected_hash:
                    issue(asset_id,'hash_mismatch',file_class); return None
                return read
        except OSError:
            issue(asset_id,'file_unavailable',file_class); return None
    status = 'partial'
    try:
        if root.is_symlink() or not root.is_dir():
            raise ValueError('Asset root must be a regular directory')
        with factory() as db:
            db.execute(text("set local statement_timeout = '2s'"))
            total = db.scalar(select(func.count()).select_from(Asset))
            summary['observed_asset_rows'] = total
            # Fixed, bounded selection; new rows are never silently added to this pass.
            rows = db.execute(select(Asset.id, Asset.storage_key, Asset.size, Asset.sha256, Asset.has_preview,
                                     Asset.preview_size, Asset.preview_sha256)
                              .order_by(Asset.id).limit(max_files+1)).all()
        summary['selected_asset_rows'] = min(len(rows), max_files)
        summary['selected_previews'] = sum(bool(item.has_preview) for item in rows[:max_files])
        summary['unknown_previews'] = sum(item.has_preview and item.preview_size is None for item in rows[:max_files])
        for item in rows[:max_files]:
            check_budget()
            original = check_file(store.path(item.storage_key), item.id, item.size, item.sha256)
            summary['checked_assets'] += 1
            if original is not None: summary['verified_original_bytes'] += original
            if item.has_preview:
                known = item.preview_size is not None and item.preview_sha256 is not None
                preview = check_file(store.path(item.storage_key,preview=True), item.id,
                                     item.preview_size, item.preview_sha256, file_class='preview')
                if preview is not None:
                    summary['readable_preview_bytes'] += preview
                    if known:
                        summary['verified_preview_bytes'] += preview
                        summary['verified_previews'] += 1
        summary['selected_pass_complete'] = len(rows) <= max_files
        status = 'completed' if summary['selected_pass_complete'] else 'partial'
    except BudgetExceeded:
        summary['selected_pass_complete'] = False
        summary['stop_reason'] = 'budget_exhausted'
    except Exception:
        status = 'failed'
        summary['selected_pass_complete'] = False
        summary['stop_reason'] = 'inspection_unavailable'
    summary['state'] = 'original_references_verified' if status == 'completed' and summary['issue_count'] == 0 and summary['readable_preview_bytes'] == 0 else 'partial'
    if status == 'completed' and summary['issue_count'] == 0:
        summary['preview_integrity'] = 'verified_selected' if summary['selected_previews'] and not summary['unknown_previews'] else 'unverified'
    summary['elapsed_seconds'] = round(time.monotonic()-began,3)
    with factory() as db:
        row = db.get(StorageInspection, inspection_id)
        row.status, row.summary, row.finished_at = status, summary, utcnow()
        audit.record(db, actor=None, action='storage.inspect', scope_type='site', target_id=inspection_id,
                     outcome=status, source='operator_cli')
        db.commit()
    return {'id':str(inspection_id),'status':status,'summary':summary}
