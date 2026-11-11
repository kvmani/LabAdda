"""P5 foundation: immutable draft proposals. No activation or retention mutation."""

import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .. import audit
from ..capacity import forecast_capacity
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, get_db, get_settings, require_console
from ..errors import Conflict, Forbidden, Unauthenticated
from ..identity_locks import lock_identity
from ..models import PolicyDraft
from ..serialize import iso

router = APIRouter(tags=["governance"])
console_storage_admin = require_console("storage", admin_only=True)
GiB = 1024**3


class ProposedProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: int = Field(default=1, ge=1, le=1)
    mode: str = "observation"
    max_attachment_bytes: int = Field(default=20 * 1024**2, ge=1, le=100 * 1024**2)
    user_quota_bytes: int = Field(default=500 * 1024**2, ge=1, le=100 * GiB)
    workspace_quota_bytes: int = Field(default=2 * GiB, ge=1, le=1000 * GiB)

    @model_validator(mode="after")
    def constraints(self):
        if self.mode != "observation":
            raise ValueError("Only observation proposals are supported; enforcement is not implemented")
        if self.max_attachment_bytes > min(self.user_quota_bytes, self.workspace_quota_bytes):
            raise ValueError("File limit must fit within user and workspace budgets")
        return self


class CapacityProfile(ProposedProfile):
    schema_version: int = Field(default=2, ge=2, le=2)
    site_asset_budget_bytes: int | None = Field(default=None, ge=1, le=10 * 1024 * GiB)
    filesystem_reserve_bytes: int = Field(default=2 * GiB, ge=1, le=100 * GiB)
    filesystem_reserve_percent: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def capacity_constraints(self):
        if (
            self.site_asset_budget_bytes is not None
            and self.max_attachment_bytes > self.site_asset_budget_bytes
        ):
            raise ValueError("File limit must fit within the proposed site asset budget")
        return self


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    base_revision: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=500)
    profile: ProposedProfile | CapacityProfile

    @model_validator(mode="after")
    def reason_present(self):
        self.reason = self.reason.strip()
        if len(self.reason) < 3:
            raise ValueError("Provide a meaningful reason")
        return self


def draft_json(row):
    return {
        "id": str(row.id),
        "revision": row.revision,
        "base_revision": row.base_revision,
        "schema_version": row.schema_version,
        "profile": row.document,
        "reason": row.reason,
        "created_by": str(row.created_by),
        "created_at": iso(row.created_at),
        "status": "draft",
        "enforced": False,
    }


@router.get("/admin/policy-drafts")
def list_drafts(
    limit: int = Query(default=20, ge=1, le=100),
    before: int | None = Query(default=None, ge=1),
    actor: Actor = Depends(console_storage_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    query = select(PolicyDraft).order_by(PolicyDraft.revision.desc()).limit(limit)
    if before is not None:
        query = query.where(PolicyDraft.revision < before)
    return {
        "drafts": [draft_json(r) for r in db.scalars(query)],
        "latest_revision": db.scalar(select(func.coalesce(func.max(PolicyDraft.revision), 0))),
        "scope": "site",
        "activation_supported": False,
        "runtime_limits": {
            "source": "environment",
            "max_attachment_bytes": settings.max_attachment_bytes,
            "user_quota_bytes": settings.user_quota_bytes,
        },
        "supported_schema": ProposedProfile().model_dump(),
        "supported_schemas": [1, 2],
        "supported_capacity_schema": CapacityProfile().model_dump(),
    }


def lock_drafts(db):
    db.execute(text("select pg_advisory_xact_lock(hashtext('labadda_policy_drafts'))"))


def lock_authority(db, actor, settings):
    user = lock_identity(db, actor, settings)
    if not user.is_admin:
        raise Forbidden("admin_required", "Administrator access is required.")


@router.post("/admin/policy-drafts", status_code=201)
def create_draft(
    body: DraftRequest,
    actor: Actor = Depends(console_storage_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    # Serialize proposal revisions. Never infer approval/activation from saving a draft.
    lock_drafts(db)
    lock_authority(db, actor, settings)
    latest = db.scalar(select(func.coalesce(func.max(PolicyDraft.revision), 0)))
    if body.base_revision != latest:
        raise Conflict("policy_conflict", "A newer proposal exists. Reload and compare before saving.")
    row = PolicyDraft(
        revision=latest + 1,
        base_revision=latest,
        schema_version=body.profile.schema_version,
        document=body.profile.model_dump(),
        reason=body.reason,
        created_by=actor.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=actor.user,
        action="policy.draft",
        scope_type="site",
        target_id=row.id,
        revision=row.revision,
    )
    db.commit()
    return draft_json(row)


class CapacityForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    profile: CapacityProfile


@router.post("/admin/capacity-forecasts")
def capacity_forecast(
    body: CapacityForecastRequest,
    request: Request,
    actor: Actor = Depends(console_storage_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    # usage.py imports this module; a top-level import here would be circular.
    from .usage import filesystem_capacity, originals  # noqa: PLC0415

    if request.headers.get(PANEL_HEADER) or request.query_params.get("panel") == "1":
        raise Unauthenticated()
    assets = originals(db)
    filesystem = filesystem_capacity(settings)
    result = forecast_capacity(body.profile, assets, filesystem)
    lock_authority(db, actor, settings)
    digest = hashlib.sha256(
        json.dumps(body.profile.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    audit.record(
        db,
        actor=actor.user,
        action="policy.capacity_forecast",
        scope_type="site",
        profile_digest=digest,
        state="incomplete",
    )
    db.commit()
    return result
