"""P5 foundation: immutable draft proposals. No activation or retention mutation."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import audit
from ..config import Settings
from ..deps import Actor, get_db, get_settings, require_admin
from ..errors import Conflict, Forbidden, Unauthenticated
from ..models import AuthSession, PolicyDraft, User
from ..security import session_valid
from ..serialize import iso

router = APIRouter(tags=['governance'])
GiB = 1024**3


class ProposedProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: int = Field(default=1, ge=1, le=1)
    mode: str = 'observation'
    max_attachment_bytes: int = Field(default=20 * 1024**2, ge=1, le=100 * 1024**2)
    user_quota_bytes: int = Field(default=500 * 1024**2, ge=1, le=100 * GiB)
    workspace_quota_bytes: int = Field(default=2 * GiB, ge=1, le=1000 * GiB)

    @model_validator(mode='after')
    def constraints(self):
        if self.mode != 'observation':
            raise ValueError('Only observation proposals are supported; enforcement is not implemented')
        if self.max_attachment_bytes > min(self.user_quota_bytes, self.workspace_quota_bytes):
            raise ValueError('File limit must fit within user and workspace budgets')
        return self


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    base_revision: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)
    profile: ProposedProfile

    @model_validator(mode='after')
    def reason_present(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError('Provide a meaningful reason')
        return self


def draft_json(row):
    return {'id': str(row.id), 'revision': row.revision, 'base_revision': row.base_revision,
            'schema_version': row.schema_version, 'profile': row.document, 'reason': row.reason,
            'created_by': str(row.created_by), 'created_at': iso(row.created_at), 'status': 'draft', 'enforced': False}


@router.get('/admin/policy-drafts')
def list_drafts(limit: int = Query(default=20, ge=1, le=100), before: int | None = Query(default=None, ge=1),
                actor: Actor = Depends(require_admin), db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings)):
    query = select(PolicyDraft).order_by(PolicyDraft.revision.desc()).limit(limit)
    if before is not None:
        query = query.where(PolicyDraft.revision < before)
    return {'drafts': [draft_json(r) for r in db.scalars(query)],
            'latest_revision': db.scalar(select(func.coalesce(func.max(PolicyDraft.revision), 0))),
            'scope': 'site', 'activation_supported': False,
            'runtime_limits': {'source': 'environment', 'max_attachment_bytes': settings.max_attachment_bytes,
                               'user_quota_bytes': settings.user_quota_bytes},
            'supported_schema': ProposedProfile().model_dump()}


def lock_drafts(db):
    db.execute(text("select pg_advisory_xact_lock(hashtext('labadda_policy_drafts'))"))


def lock_authority(db, actor, settings):
    # Lock in the same user → session order used by deactivation/reset. Refresh
    # cached ORM identities after any lock wait; hold authorization through commit.
    # NO KEY UPDATE blocks role/password writes while allowing FK key-share checks.
    user = db.scalar(select(User).where(User.id == actor.id).with_for_update(key_share=True).execution_options(populate_existing=True))
    session = db.scalar(select(AuthSession).where(AuthSession.id == actor.session.id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active or session is None or not session_valid(session, settings):
        raise Unauthenticated()
    if not user.is_admin:
        raise Forbidden('admin_required', 'Administrator access is required.')


@router.post('/admin/policy-drafts', status_code=201)
def create_draft(body: DraftRequest, actor: Actor = Depends(require_admin), db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    # Serialize proposal revisions. Never infer approval/activation from saving a draft.
    lock_drafts(db)
    lock_authority(db, actor, settings)
    latest = db.scalar(select(func.coalesce(func.max(PolicyDraft.revision), 0)))
    if body.base_revision != latest:
        raise Conflict('policy_conflict', 'A newer proposal exists. Reload and compare before saving.')
    row = PolicyDraft(revision=latest + 1, base_revision=latest, schema_version=1,
                      document=body.profile.model_dump(), reason=body.reason, created_by=actor.id)
    db.add(row)
    db.flush()
    audit.record(db, actor=actor.user, action='policy.draft', scope_type='site', target_id=row.id,
                 revision=row.revision)
    db.commit()
    return draft_json(row)
