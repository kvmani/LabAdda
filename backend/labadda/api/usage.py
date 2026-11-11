"""Truthful partial measurement; neither reconciliation nor admission enforcement."""

import os
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .. import audit, charges, policy
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings, require_admin
from ..errors import ApiError, Unauthenticated
from ..models import Asset, StorageInspection, UploadReservation, UsageObservation
from ..security import utcnow
from ..serialize import iso
from ..workspace_usage import workspace_observation
from .capabilities import require_usage_reader

router = APIRouter(tags=["usage"])
UNMEASURED = [
    "other_or_historical_derivative_bytes",
    "non_upload_reservations",
    "trash",
    "temporary_archives",
    "reference_reconciliation",
    "todo_logical_bytes",
]

# Physical PostgreSQL storage by category (DL-07: measured separately from logical attribution).
# Table names are fixed constants; sizes include indexes and TOAST.
DATABASE_CATEGORIES = {
    "collaboration_text": ("posts", "chat_messages", "chat_reads", "notifications"),
    "personal_notes": ("notes",),
    "board_history": ("boards", "board_ops", "board_snapshots"),
    "file_metadata": ("assets", "upload_reservations", "upload_receipts"),
    "identity_and_access": (
        "users",
        "credential_tokens",
        "auth_sessions",
        "panel_pairings",
        "workspaces",
        "memberships",
        "usage_reader_grants",
    ),
    "audit_and_governance": (
        "audit_events",
        "policy_drafts",
        "usage_observations",
        "storage_inspections",
        "inventory_jobs",
        "inventory_attempts",
        "content_charges",
    ),
}
DATABASE_SIZES = text("""
SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = current_schema() AND c.relname = ANY(:names)
""")


@router.get("/workspaces/{workspace_id}/usage")
def workspace_usage(
    workspace_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    if request.headers.get(PANEL_HEADER) or request.query_params.get("panel") == "1":
        raise Unauthenticated()
    policy.require_read(db, actor.user, workspace_id)
    try:
        db.execute(text("set local statement_timeout = '2s'"))
        result = workspace_observation(db, workspace_id)
        # Refresh identity/session and grants after measurement as well. A
        # slow read must not deliver counters under an already revoked grant.
        db.expire_all()
        refreshed = current_actor(request, db)
        policy.require_read(db, refreshed.user, workspace_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError(
            "measurement_unavailable", "Usage measurement is unavailable. Retry later.", status=503
        ) from exc
    return result


def originals(db, user_id=None):
    query = select(
        func.count(Asset.id),
        func.coalesce(func.sum(Asset.size), 0),
        func.coalesce(func.sum(case((Asset.status == "provisional", Asset.size), else_=0)), 0),
        func.coalesce(func.sum(Asset.preview_size), 0),
        func.count(case((Asset.has_preview & Asset.preview_size.is_(None), 1))),
    )
    if user_id is not None:
        query = query.where(Asset.owner_id == user_id)
    pending = select(func.coalesce(func.sum(UploadReservation.bytes), 0)).where(
        UploadReservation.expires_at > utcnow()
    )
    if user_id is not None:
        pending = pending.where(UploadReservation.user_id == user_id)
    query = query.add_columns(pending.scalar_subquery())
    try:
        db.execute(text("set local statement_timeout = '2s'"))
        count, total, provisional, preview_bytes, unknown_previews, reserved = db.execute(query).one()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError(
            "measurement_unavailable", "Usage measurement is unavailable. Retry later.", status=503
        ) from exc
    return {
        "state": "partial",
        "source": "asset_metadata",
        "observed_at": iso(utcnow()),
        "tracked_files": count,
        "tracked_original_bytes": int(total),
        "tracked_preview_bytes": int(preview_bytes),
        "unknown_preview_files": unknown_previews,
        "pending_upload_original_bytes": int(reserved),
        "provisional_original_bytes": int(provisional),
        "committed_original_bytes": int(total - provisional),
        "unmeasured": UNMEASURED,
        "complete_for_enforcement": False,
    }


def logical_charges(db, user_id=None):
    """Versioned text/board logical charges (DL-07); separate from original-file bytes."""
    try:
        db.execute(text("set local statement_timeout = '2s'"))
        measured = charges.summary(db, user_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError(
            "measurement_unavailable", "Usage measurement is unavailable. Retry later.", status=503
        ) from exc
    return {
        **measured,
        "source": "content_charges_ledger",
        "observed_at": iso(utcnow()),
        "complete_for_enforcement": False,
    }


@router.get("/usage")
def user_usage(
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    measured = originals(db, actor.id)
    limit = settings.user_quota_bytes
    return {
        "scope": "current_user",
        "measurement": measured,
        "logical_charges": logical_charges(db, actor.id),
        "runtime_limit": {"bytes": limit, "source": "environment", "policy_proposals_enforced": False},
        "tracked_original_percent": round(measured["tracked_original_bytes"] / limit * 100, 1)
        if limit > 0
        else None,
        "available_features": {"archives": False, "quota_exceptions": False, "retention": False},
    }


def database_physical(db) -> dict:
    """Site-wide physical database storage. Shared overhead: never attributed to users or workspaces."""
    names = [t for tables in DATABASE_CATEGORIES.values() for t in tables]
    unknown = {
        "state": "unknown",
        "database_bytes": None,
        "categories": dict.fromkeys(DATABASE_CATEGORIES),
        "other_bytes": None,
        "board_history": {"retained_operations": None, "snapshots": None},
    }
    try:
        db.execute(text("set local statement_timeout = '2s'"))
        sizes = dict(db.execute(DATABASE_SIZES, {"names": names}).all())
        total = int(db.scalar(text("select pg_database_size(current_database())")))
        retained = db.scalar(text("select count(*) from board_ops"))
        snapshots = db.scalar(text("select count(*) from board_snapshots"))
    except SQLAlchemyError:
        db.rollback()
        return {**unknown, "observed_at": iso(utcnow())}
    categories = {k: sum(int(sizes.get(t, 0)) for t in tables) for k, tables in DATABASE_CATEGORIES.items()}
    return {
        "state": "ready",
        "observed_at": iso(utcnow()),
        "database_bytes": total,
        "categories": categories,
        # System catalogs, migration bookkeeping and free space inside the database files.
        "other_bytes": max(0, total - sum(categories.values())),
        "board_history": {"retained_operations": retained, "snapshots": snapshots},
        "scope": "physical_postgresql_storage_including_indexes",
        "attribution": "site_overhead_not_charged_to_users",
    }


def filesystem_capacity(settings):
    filesystem = {
        "state": "unknown",
        "free_bytes": None,
        "total_bytes": None,
        "free_inodes": None,
        "scope": "filesystem_containing_asset_directory",
        "site_budget": None,
    }
    try:
        info = os.statvfs(settings.asset_dir)
        filesystem.update(
            state="ready",
            free_bytes=info.f_bavail * info.f_frsize,
            total_bytes=info.f_blocks * info.f_frsize,
            free_inodes=info.f_favail,
        )
    except OSError:
        pass
    filesystem["observed_at"] = iso(utcnow())
    return filesystem


def site_payload(db, settings):
    measured = originals(db)
    filesystem = filesystem_capacity(settings)
    return {
        "schema_version": 1,
        "scope": "site",
        "state": "partial",
        "assets": measured,
        "logical_charges": logical_charges(db),
        "database": database_physical(db),
        "filesystem": filesystem,
        "note": "Filesystem capacity is shared; it is not a configured site quota.",
        "policy_enforcement_changed": False,
    }


@router.get("/admin/usage")
def site_usage(
    actor: Actor = Depends(require_usage_reader),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return site_payload(db, settings)


@router.post("/admin/usage-observations", status_code=201)
def record_observation(
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from .governance import lock_authority

    db.execute(text("select pg_advisory_xact_lock(hashtext('labadda_usage_observations'))"))
    lock_authority(db, actor, settings)
    measured = site_payload(db, settings)
    # Keep only 100 observations. This is explicitly operational telemetry, not
    # immutable policy/audit history or a deletion candidate ledger.
    row = UsageObservation(schema_version=1, payload=measured, created_by=actor.id, created_at=utcnow())
    db.add(row)
    db.flush()
    old_ids = (
        select(UsageObservation.id)
        .order_by(UsageObservation.created_at.desc(), UsageObservation.id.desc())
        .offset(100)
    )
    db.query(UsageObservation).filter(UsageObservation.id.in_(old_ids)).delete(synchronize_session=False)
    audit.record(db, actor=actor.user, action="usage.observe", scope_type="site", target_id=row.id)
    db.commit()
    return {"id": str(row.id), "observed_at": iso(row.created_at), "measurement": measured}


@router.get("/admin/usage-observations")
def observations(actor: Actor = Depends(require_usage_reader), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(UsageObservation)
        .order_by(UsageObservation.created_at.desc(), UsageObservation.id.desc())
        .limit(20)
    )
    return {
        "observations": [
            {"id": str(r.id), "observed_at": iso(r.created_at), "measurement": r.payload} for r in rows
        ],
        "retention": {"maximum_samples": 100, "returned_samples": 20},
    }


@router.get("/admin/storage-inspections")
def inspections(actor: Actor = Depends(require_usage_reader), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(StorageInspection)
        .order_by(StorageInspection.created_at.desc(), StorageInspection.id.desc())
        .limit(20)
    )
    return {
        "inspections": [
            {
                "id": str(r.id),
                "status": r.status,
                "started_at": iso(r.created_at),
                "finished_at": iso(r.finished_at),
                "summary": r.summary,
            }
            for r in rows
        ],
        "trigger": "trusted_operator_cli",
        "enforcement_authority": False,
    }
