"""Narrow operational observer delegation; administration and content remain separate."""
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from .. import audit
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings, require_admin
from ..errors import Forbidden, Invalid, NotFound, TooMany
from ..models import UsageReaderGrant, User
from ..security import login_limiter, utcnow, verify_password
from ..serialize import iso
from .governance import lock_authority

router = APIRouter(tags=['capabilities'])


def can_read_usage(db, actor):
    return actor.user.is_admin or db.scalar(select(UsageReaderGrant.user_id).where(
        UsageReaderGrant.user_id == actor.id, UsageReaderGrant.expires_at > utcnow())) is not None


def require_usage_reader(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if not can_read_usage(db, actor):
        raise Forbidden('usage_read_required', 'Operational read access is required.')
    return actor


@router.get('/capabilities')
def own_capabilities(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return {'usage.read': can_read_usage(db, actor), 'policy.draft': actor.user.is_admin,
            'identity.admin': actor.user.is_admin}


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: uuid.UUID
    hours: int = Field(default=24, ge=1, le=720, strict=True)
    reason: str = Field(min_length=3, max_length=500, strict=True)
    password: SecretStr = Field(min_length=1, max_length=1024)


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500, strict=True)
    password: SecretStr = Field(min_length=1, max_length=1024)


def authenticate_action(db, actor, settings, password):
    if not login_limiter.hit('usage-grant:'+str(actor.id), 10, 300):
        raise TooMany()
    # All grant writers use one serialization key, then user → session locks.
    db.execute(text("select pg_advisory_xact_lock(hashtext('labadda_usage_readers'))"))
    lock_authority(db, actor, settings)
    if not verify_password(actor.user.password_hash, password):
        audit.record(db, actor=actor.user, action='usage.reader.reauthenticate', scope_type='identity',
                     scope_id=actor.id, outcome='denied')
        db.commit()
        raise Forbidden('reauthentication_failed', 'Password confirmation failed.')


@router.get('/admin/usage-readers')
def readers(actor: Actor = Depends(require_admin), db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.execute(select(UsageReaderGrant, User).join(User, User.id == UsageReaderGrant.user_id)
                      .order_by(and_(User.is_active, UsageReaderGrant.expires_at > now).desc(), UsageReaderGrant.expires_at).limit(200)).all()
    total = db.scalar(select(func.count()).select_from(UsageReaderGrant))
    return {'grants':[{'user_id':str(user.id), 'username':user.username, 'reason':grant.reason,
                      'expires_at':iso(grant.expires_at), 'active':user.is_active and grant.expires_at > now}
                     for grant,user in rows], 'maximum_returned':200, 'total_count':total, 'truncated':total > 200}


@router.post('/admin/usage-readers', status_code=201)
def grant_reader(body: GrantRequest, actor: Actor = Depends(require_admin), db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    if len(body.reason.strip()) < 3:
        raise Invalid('reason_required', 'Provide a meaningful reason.')
    authenticate_action(db, actor, settings, body.password.get_secret_value())
    # Do not lock a second user after the actor: concurrent role operations may
    # lock users in different orders. Metadata grants never activate a disabled user.
    user = db.get(User, body.user_id, populate_existing=True)
    if user is None:
        raise NotFound()
    if not user.is_active or user.is_admin:
        raise Invalid('ineligible_observer', 'Choose an active non-administrator.')
    row = db.get(UsageReaderGrant, body.user_id)
    if row is None:
        row = UsageReaderGrant(user_id=body.user_id)
        db.add(row)
    row.granted_by, row.reason = actor.id, body.reason.strip()
    row.created_at, row.expires_at = utcnow(), utcnow()+timedelta(hours=body.hours)
    audit.record(db, actor=actor.user, action='usage.reader.grant', scope_type='identity',
                 target_id=user.id, reason=body.reason.strip(), expires_at=row.expires_at)
    db.commit()
    return {'user_id':str(user.id), 'capability':'usage.read', 'expires_at':iso(row.expires_at)}


@router.post('/admin/usage-readers/revoke')
def revoke_reader(body: RevokeRequest, actor: Actor = Depends(require_admin), db: Session = Depends(get_db),
                  settings: Settings = Depends(get_settings)):
    if len(body.reason.strip()) < 3:
        raise Invalid('reason_required', 'Provide a meaningful reason.')
    authenticate_action(db, actor, settings, body.password.get_secret_value())
    row = db.get(UsageReaderGrant, body.user_id)
    if row is None:
        raise NotFound()
    db.delete(row)
    audit.record(db, actor=actor.user, action='usage.reader.revoke', scope_type='identity',
                 target_id=body.user_id, reason=body.reason.strip())
    db.commit()
    return {'revoked':True}
