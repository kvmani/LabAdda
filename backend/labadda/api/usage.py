"""Truthful partial measurement; neither reconciliation nor admission enforcement."""
import os

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .. import audit
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_admin
from ..errors import ApiError
from ..models import Asset, StorageInspection, UsageObservation
from ..security import utcnow
from ..serialize import iso

from .capabilities import require_usage_reader

router = APIRouter(tags=['usage'])
UNMEASURED = ['derivative_bytes', 'text_and_board_logical_bytes', 'reservations', 'trash',
              'temporary_archives', 'reference_reconciliation']


def originals(db, user_id=None):
    query = select(func.count(Asset.id), func.coalesce(func.sum(Asset.size), 0),
        func.coalesce(func.sum(case((Asset.status == 'provisional', Asset.size), else_=0)), 0))
    if user_id is not None:
        query = query.where(Asset.owner_id == user_id)
    try:
        db.execute(text("set local statement_timeout = '2s'"))
        count, total, provisional = db.execute(query).one()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError('measurement_unavailable', 'Usage measurement is unavailable. Retry later.', status=503) from exc
    return {'state': 'partial', 'source': 'asset_metadata', 'observed_at': iso(utcnow()),
            'tracked_files': count, 'tracked_original_bytes': int(total),
            'provisional_original_bytes': int(provisional), 'committed_original_bytes': int(total-provisional),
            'unmeasured': UNMEASURED, 'complete_for_enforcement': False}


@router.get('/usage')
def user_usage(actor: Actor = Depends(current_actor), db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings)):
    measured = originals(db, actor.id)
    limit = settings.user_quota_bytes
    return {'scope': 'current_user', 'measurement': measured,
            'runtime_limit': {'bytes': limit, 'source': 'environment', 'policy_proposals_enforced': False},
            'tracked_original_percent': round(measured['tracked_original_bytes'] / limit * 100, 1) if limit > 0 else None,
            'available_features': {'archives': False, 'quota_exceptions': False, 'retention': False}}


def site_payload(db, settings):
    measured = originals(db)
    filesystem = {'state': 'unknown', 'free_bytes': None, 'total_bytes': None, 'free_inodes': None,
                  'scope': 'filesystem_containing_asset_directory', 'site_budget': None}
    try:
        info = os.statvfs(settings.asset_dir)
        filesystem.update(state='ready', free_bytes=info.f_bavail*info.f_frsize,
                          total_bytes=info.f_blocks*info.f_frsize, free_inodes=info.f_favail)
    except OSError:
        pass
    filesystem['observed_at'] = iso(utcnow())
    return {'schema_version': 1, 'scope': 'site', 'state': 'partial', 'assets': measured,
            'filesystem': filesystem, 'note': 'Filesystem capacity is shared; it is not a configured site quota.',
            'policy_enforcement_changed': False}


@router.get('/admin/usage')
def site_usage(actor: Actor = Depends(require_usage_reader), db: Session = Depends(get_db),
               settings: Settings = Depends(get_settings)):
    return site_payload(db, settings)


@router.post('/admin/usage-observations', status_code=201)
def record_observation(actor: Actor = Depends(require_admin), db: Session = Depends(get_db),
                       settings: Settings = Depends(get_settings)):
    from .governance import lock_authority
    db.execute(text("select pg_advisory_xact_lock(hashtext('labadda_usage_observations'))"))
    lock_authority(db, actor, settings)
    measured = site_payload(db, settings)
    # Keep only 100 observations. This is explicitly operational telemetry, not
    # immutable policy/audit history or a deletion candidate ledger.
    row = UsageObservation(schema_version=1, payload=measured, created_by=actor.id, created_at=utcnow())
    db.add(row)
    db.flush()
    old_ids = select(UsageObservation.id).order_by(UsageObservation.created_at.desc(), UsageObservation.id.desc()).offset(100)
    db.query(UsageObservation).filter(UsageObservation.id.in_(old_ids)).delete(synchronize_session=False)
    audit.record(db, actor=actor.user, action='usage.observe', scope_type='site', target_id=row.id)
    db.commit()
    return {'id': str(row.id), 'observed_at': iso(row.created_at), 'measurement': measured}


@router.get('/admin/usage-observations')
def observations(actor: Actor = Depends(require_usage_reader), db: Session = Depends(get_db)):
    rows = db.scalars(select(UsageObservation).order_by(UsageObservation.created_at.desc(), UsageObservation.id.desc()).limit(20))
    return {'observations': [{'id': str(r.id), 'observed_at': iso(r.created_at), 'measurement': r.payload} for r in rows],
            'retention': {'maximum_samples': 100, 'returned_samples': 20}}


@router.get('/admin/storage-inspections')
def inspections(actor: Actor = Depends(require_usage_reader), db: Session = Depends(get_db)):
    rows = db.scalars(select(StorageInspection).order_by(StorageInspection.created_at.desc(), StorageInspection.id.desc()).limit(20))
    return {'inspections': [{'id':str(r.id), 'status':r.status, 'started_at':iso(r.created_at),
                            'finished_at':iso(r.finished_at), 'summary':r.summary} for r in rows],
            'trigger': 'trusted_operator_cli', 'enforcement_authority': False}
