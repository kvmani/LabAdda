"""Race-safe reservations for original bytes under the existing pilot limit.

This is not the complete P5 ledger: derivative/site/text budgets are not enforced.
"""
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, func, select

from .errors import ApiError, Conflict, Invalid
from .identity_locks import lock_identity
from .models import Asset, UploadReceipt, UploadReservation, User
from .security import utcnow

RESERVATION_SECONDS = 600
RECEIPT_HOURS = 24


def check_original_capacity(db, actor, settings, size):
    """Caller must hold the user identity lock through its Asset commit."""
    now = utcnow()
    # Only metadata expires here; do not guess which filesystem paths are safe
    # to delete after an interrupted worker. Orphan reconciliation is separate.
    db.execute(delete(UploadReservation).where(UploadReservation.user_id == actor.id,
                                             UploadReservation.expires_at <= now))
    used = db.scalar(select(func.coalesce(func.sum(Asset.size),0)).where(Asset.owner_id == actor.id))
    pending = db.scalar(select(func.coalesce(func.sum(UploadReservation.bytes),0)).where(
        UploadReservation.user_id == actor.id, UploadReservation.expires_at > now))
    if used + pending + size > settings.user_quota_bytes:
        raise Invalid('quota_exceeded', 'Your original-file allowance is exhausted, including pending uploads. Retry after they finish or contact an administrator.')


@dataclass(frozen=True)
class Admission:
    reservation_id: UUID | None = None
    receipt_id: UUID | None = None
    asset_id: UUID | None = None


def reserve_upload(db, actor, settings, size, request_key=None, fingerprint=None):
    lock_identity(db, actor, settings)
    now = utcnow()
    db.execute(delete(UploadReceipt).where(UploadReceipt.user_id == actor.id,
                                         UploadReceipt.expires_at <= now))
    if request_key is not None:
        previous = db.scalar(select(UploadReceipt).where(UploadReceipt.user_id == actor.id,
                                                        UploadReceipt.request_key == request_key))
        if previous is not None:
            if previous.fingerprint != fingerprint:
                raise Conflict('upload_key_reused', 'This upload key belongs to different file content or metadata.')
            if previous.state == 'complete':
                if previous.asset_id is None:
                    raise ApiError('upload_result_unavailable', 'The original upload is no longer available.', status=410)
                return Admission(receipt_id=previous.id, asset_id=previous.asset_id)
            reservation = db.get(UploadReservation, previous.reservation_id) if previous.reservation_id else None
            if previous.state == 'pending' and reservation is not None and reservation.expires_at > now:
                raise Conflict('upload_in_progress', 'This upload is pending. Check its receipt before retrying.')
            raise Conflict('upload_request_incomplete',
                           'This attempt did not complete. Inspect its receipt before starting a new request key.')
    check_original_capacity(db, actor, settings, size)
    row = UploadReservation(user_id=actor.id, bytes=size, created_at=now,
                            expires_at=now+timedelta(seconds=RESERVATION_SECONDS))
    db.add(row)
    db.flush()
    reservation_id = row.id
    receipt_id = None
    if request_key is not None:
        receipt = UploadReceipt(
            user_id=actor.id, request_key=request_key, fingerprint=fingerprint,
            state='pending', reservation_id=reservation_id, created_at=now,
            expires_at=now+timedelta(hours=RECEIPT_HOURS))
        db.add(receipt)
        db.flush()
        receipt_id = receipt.id
    db.commit()
    return Admission(reservation_id=reservation_id, receipt_id=receipt_id)


def consume_upload(db, actor, settings, reservation_id, receipt_id=None, asset_id=None):
    lock_identity(db, actor, settings)
    row = db.get(UploadReservation, reservation_id, with_for_update=True)
    if row is None or row.user_id != actor.id or row.expires_at <= utcnow():
        raise Invalid('upload_reservation_expired','Upload reservation expired. Retry the upload.')
    if receipt_id is not None:
        receipt = db.get(UploadReceipt, receipt_id, with_for_update=True)
        if receipt is None or receipt.user_id != actor.id or receipt.state != 'pending' \
                or receipt.reservation_id != reservation_id:
            raise Conflict('upload_request_incomplete', 'Upload request identity no longer matches its reservation.')
        receipt.state, receipt.asset_id, receipt.reservation_id = 'complete', asset_id, None
    db.delete(row)
    # Caller flushes the matching Asset in this same transaction. Never commit
    # reservation release separately from its replacement durable original.


def release_upload(db, actor_id, reservation_id, receipt_id=None):
    db.rollback()
    # Serialize cleanup with admission too. Authorization may have expired, so
    # take the identity row lock without requiring a still-valid session.
    # Reservation deletion can SET NULL its receipt: keep user → lease → receipt
    # ordering across expiry cleanup, finalization and definite failure release.
    db.scalar(select(User).where(User.id == actor_id).with_for_update(key_share=True))
    db.get(UploadReservation, reservation_id, with_for_update=True)
    if receipt_id is not None:
        receipt = db.get(UploadReceipt, receipt_id, with_for_update=True)
        if receipt is not None and receipt.user_id == actor_id and receipt.state == 'pending' \
                and receipt.reservation_id == reservation_id:
            receipt.state, receipt.reservation_id = 'failed', None
    db.execute(delete(UploadReservation).where(UploadReservation.id == reservation_id,
                                             UploadReservation.user_id == actor_id))
    db.commit()
