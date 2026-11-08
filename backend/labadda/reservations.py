"""Race-safe reservations for original bytes under the existing pilot limit.

This is not the complete P5 ledger: derivative/site/text budgets are not enforced.
"""
from datetime import timedelta

from sqlalchemy import delete, func, select

from .errors import Invalid
from .identity_locks import lock_identity
from .models import Asset, UploadReservation
from .security import utcnow

RESERVATION_SECONDS = 600


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


def reserve_upload(db, actor, settings, size):
    lock_identity(db, actor, settings)
    check_original_capacity(db, actor, settings, size)
    now = utcnow()
    row = UploadReservation(user_id=actor.id, bytes=size, created_at=now,
                            expires_at=now+timedelta(seconds=RESERVATION_SECONDS))
    db.add(row); db.flush(); reservation_id = row.id
    db.commit()
    return reservation_id


def consume_upload(db, actor, settings, reservation_id):
    lock_identity(db, actor, settings)
    row = db.get(UploadReservation, reservation_id, with_for_update=True)
    if row is None or row.user_id != actor.id or row.expires_at <= utcnow():
        raise Invalid('upload_reservation_expired','Upload reservation expired. Retry the upload.')
    db.delete(row)
    # Caller adds the matching Asset in this same transaction. Never commit
    # reservation release separately from its replacement durable original.


def release_upload(db, actor_id, reservation_id):
    db.rollback()
    db.execute(delete(UploadReservation).where(UploadReservation.id == reservation_id,
                                             UploadReservation.user_id == actor_id))
    db.commit()
