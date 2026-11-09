"""Durable, operator-only inventory execution; a narrow observation job protocol.

Lease loss may leave an unaccepted diagnostic scan receipt, never an accepted
result from a stale attempt. Retries repeat a read-only scan from the beginning.
"""
from datetime import timedelta
import hashlib
import json
import re
import time
import uuid

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from . import audit
from .inventory import inventory_storage
from .models import InventoryAttempt, InventoryJob, StorageInspection

LEASE_SECONDS = 30


class InventoryParameters(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    max_entries: int = Field(default=10000, ge=1, le=100000)
    max_assets: int = Field(default=10000, ge=1, le=100000)
    max_seconds: int = Field(default=30, ge=1, le=300)


class JobConflict(ValueError):
    """The requested transition is no longer permitted."""


def _now(db):
    return db.scalar(select(func.clock_timestamp()))


def _locked(db, job_id):
    db.execute(text("set local lock_timeout = '2s'"))
    job = db.scalar(select(InventoryJob).where(InventoryJob.id == job_id).with_for_update())
    if job is None:
        raise JobConflict('Unknown inventory job')
    return job


def _event(db, job, action):
    audit.record(db, actor=None, action='inventory_job.' + action, scope_type='site',
                 target_id=job.id, source='operator_cli', attempt=job.attempt, outcome=job.state)


def enqueue(factory, request_key: str, parameters: dict) -> uuid.UUID:
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', request_key):
        raise ValueError('Use an 8–64 character opaque request key')
    payload = InventoryParameters.model_validate(parameters).model_dump()
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with factory() as db:
        db.execute(text("set local lock_timeout = '2s'"))
        db.execute(insert(InventoryJob).values(id=uuid.uuid4(), request_key=request_key, plan_digest=digest,
                   parameters=payload, state='queued', attempt=0).on_conflict_do_nothing(index_elements=['request_key']))
        job = db.scalar(select(InventoryJob).where(InventoryJob.request_key == request_key).with_for_update())
        if job.plan_digest != digest:
            raise JobConflict('Request key already names different parameters')
        _event(db, job, 'request')
        db.commit()
        return job.id


def claim(factory, job_id, *, retry: bool = False) -> tuple[int, dict]:
    with factory() as db:
        job = _locked(db, job_id)
        now = _now(db)
        if job.state == 'running':
            if job.lease_until > now or not retry:
                raise JobConflict('Running or expired attempt requires explicit retry')
            previous = db.get(InventoryAttempt, (job.id, job.attempt))
            previous.state, previous.finished_at = 'expired', now
        elif job.state != 'queued' and not (retry and job.state in {'failed', 'partial', 'paused'}):
            raise JobConflict('Job is not eligible to run')
        if job.attempt >= 100:
            raise JobConflict('Attempt limit reached; create a new reviewed request')
        job.attempt += 1
        job.state, job.lease_until, job.updated_at = 'running', now + timedelta(seconds=LEASE_SECONDS), now
        db.add(InventoryAttempt(job_id=job.id, number=job.attempt, state='running', started_at=now, heartbeat_at=now))
        _event(db, job, 'claim')
        result = job.attempt, dict(job.parameters)
        db.commit()
        return result


def _owned(db, job_id, number):
    job = _locked(db, job_id)
    now = _now(db)
    if job.state != 'running' or job.attempt != number or job.lease_until <= now:
        raise JobConflict('Attempt no longer owns a current lease')
    return job, now


def heartbeat(factory, job_id, number):
    with factory() as db:
        job, now = _owned(db, job_id, number)
        job.lease_until, job.updated_at = now + timedelta(seconds=LEASE_SECONDS), now
        db.get(InventoryAttempt, (job.id, number)).heartbeat_at = now
        db.commit()


def finish(factory, job_id, number, result):
    with factory() as db:
        job, now = _owned(db, job_id, number)
        receipt = db.get(StorageInspection, uuid.UUID(result['id']))
        if receipt is None or receipt.summary.get('job') != {'id': str(job.id), 'attempt': number}:
            raise JobConflict('Receipt does not belong to this attempt')
        status = receipt.status
        if status == 'completed' and not receipt.summary.get('selected_pass_complete'):
            status = 'partial'
        if status not in {'completed', 'partial', 'failed'}:
            raise ValueError('Invalid inventory outcome')
        attempt = db.get(InventoryAttempt, (job.id, number))
        attempt.state, attempt.finished_at = status, now
        attempt.receipt_id = uuid.UUID(result['id'])
        job.state, job.lease_until, job.updated_at = status, None, now
        _event(db, job, 'finish')
        db.commit()


def cancel(factory, job_id):
    with factory() as db:
        job = _locked(db, job_id)
        if job.state == 'cancelled':
            return
        if job.state in {'completed', 'failed', 'partial'}:
            raise JobConflict('Terminal result cannot be cancelled')
        now = _now(db)
        if job.state == 'running':
            attempt = db.get(InventoryAttempt, (job.id, job.attempt))
            attempt.state, attempt.finished_at = 'cancelled', now
        job.state, job.lease_until, job.updated_at = 'cancelled', None, now
        _event(db, job, 'cancel')
        db.commit()


def run(factory, root, job_id, *, retry=False):
    number, parameters = claim(factory, job_id, retry=retry)
    next_heartbeat = 0.0

    def checkpoint():
        nonlocal next_heartbeat
        if time.monotonic() >= next_heartbeat:
            heartbeat(factory, job_id, number)
            next_heartbeat = time.monotonic() + 1

    # All work is observational. A failed/unconfirmed receipt commit leaves the
    # job running until its lease expires; no automatic retry or assumed success.
    result = inventory_storage(factory, root, checkpoint=checkpoint,
                               job_context={'id': str(job_id), 'attempt': number}, **parameters)
    finish(factory, job_id, number, result)
    return result


def pause_restored_jobs(conn):
    """No copied lease survives isolated recovery; retain attempt history."""
    conn.execute(text("update inventory_attempts set state='paused', finished_at=clock_timestamp() where state='running'"))
    conn.execute(text("update inventory_jobs set state='paused', lease_until=null, updated_at=clock_timestamp() where state in ('queued','running')"))


def describe(db, job, *, now=None):
    from .serialize import iso
    now = _now(db) if now is None else now
    attempts = db.scalars(select(InventoryAttempt).where(InventoryAttempt.job_id == job.id)
                          .order_by(InventoryAttempt.number)).all()
    return {'id': str(job.id), 'kind': 'asset_directory_inventory', 'state': job.state,
            'source': 'operator_cli', 'scope': 'site', 'policy_revision': None,
            'plan_digest': job.plan_digest, 'parameters': job.parameters,
            'attempt': job.attempt, 'lease_until': iso(job.lease_until),
            'lease_expired': job.state == 'running' and job.lease_until <= now,
            'created_at': iso(job.created_at), 'updated_at': iso(job.updated_at),
            'attempts': [{'number': a.number, 'state': a.state, 'started_at': iso(a.started_at),
                          'heartbeat_at': iso(a.heartbeat_at), 'finished_at': iso(a.finished_at),
                          'receipt_id': str(a.receipt_id) if a.receipt_id else None} for a in attempts],
            'enforcement_authority': False, 'deletion_authorized': False}
