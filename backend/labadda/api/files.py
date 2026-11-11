"""Attachment upload and protected same-origin download (S3 files)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Header, Path, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import policy
from ..config import Settings
from ..deps import PANEL_HEADER, Actor, current_actor, get_db, get_settings, panel_actor
from ..errors import ApiError, Invalid, NotFound
from ..identity_locks import lock_identity
from ..models import Asset, ChatMessage, Post, UploadReceipt, UploadReservation
from ..reservations import consume_upload, release_upload, reserve_upload
from ..security import utcnow
from ..serialize import asset_json
from ..storage import AssetStore, safe_display_name

router = APIRouter(tags=["files"])
PROTECTED_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}
REQUEST_KEY_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


def _store(request: Request) -> AssetStore:
    return request.app.state.assets


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks, total = [], 0
    while True:
        chunk = await upload.read(1024 * 256)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise Invalid("file_too_large", f"Each file must be {limit // (1024 * 1024)} MiB or smaller.")
        chunks.append(chunk)
    if total == 0:
        raise Invalid("empty_file", "The file is empty.")
    return b"".join(chunks)


@router.post("/uploads", status_code=201)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(default=None, pattern=REQUEST_KEY_PATTERN),
):
    data = await _read_limited(file, settings.max_attachment_bytes)
    return await run_in_threadpool(
        _persist_upload, request, db, actor, settings, data, file.content_type, file.filename, idempotency_key
    )


def _persist_upload(request, db, actor, settings, data, content_type, filename, request_key=None):
    from types import SimpleNamespace

    # Immutable references avoid consulting expired request-ORM objects during
    # failure resolution through a fresh connection.
    identity = SimpleNamespace(id=actor.id, session=SimpleNamespace(id=actor.session.id))
    # Bind the key to measured content AND submitted metadata, with an explicit
    # version. A different name/type is a different intent, even for equal bytes.
    fingerprint = hashlib.sha256(
        json.dumps(
            [1, hashlib.sha256(data).hexdigest(), len(data), content_type, filename],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    admission = reserve_upload(db, identity, settings, len(data), request_key, fingerprint)
    if admission.asset_id is not None:
        return asset_json(_authorized_asset(db, actor, admission.asset_id), settings.api_prefix)
    reservation_id = admission.reservation_id
    stored = None
    candidate_id = uuid.uuid4()
    commit_started = False
    try:
        stored = _store(request).save(data, content_type)
        lock_identity(db, identity, settings)
        asset = Asset(
            id=candidate_id,
            owner_id=identity.id,
            storage_key=stored.storage_key,
            media_type=stored.media_type,
            display_name=safe_display_name(filename, stored.media_type),
            size=stored.size,
            sha256=stored.sha256,
            has_preview=stored.has_preview,
            preview_size=stored.preview_size,
            preview_sha256=stored.preview_sha256,
        )
        db.add(asset)
        db.flush()
        consume_upload(db, identity, settings, reservation_id, admission.receipt_id, candidate_id)
        db.flush()
        lock_identity(db, identity, settings)
        commit_started = True
        db.commit()
        return asset_json(asset, settings.api_prefix)
    except Exception:
        db.rollback()
        if commit_started:
            # A lost COMMIT response is not evidence of rollback. Never unlink
            # potentially committed bytes. A fresh confirmed row can complete
            # this request; absence/unavailable verification remains uncertain.
            try:
                with request.app.state.session_factory() as fresh:
                    confirmed = fresh.get(Asset, candidate_id)
                    if confirmed is not None and confirmed.storage_key == stored.storage_key:
                        user = lock_identity(fresh, identity, settings)
                        reader = SimpleNamespace(id=identity.id, user=user, is_panel=False)
                        return asset_json(_authorized_asset(fresh, reader, candidate_id), settings.api_prefix)
            except ApiError:
                raise
            except Exception:
                pass
            raise ApiError(
                "upload_commit_unknown",
                "Upload outcome is uncertain. Storage was retained for inspection; do not retry blindly.",
                status=503,
            )
        try:
            if stored is not None:
                _store(request).delete(stored.storage_key)
        finally:
            release_upload(db, identity.id, reservation_id, admission.receipt_id)
        raise


@router.get("/uploads/requests/{request_key}")
def upload_receipt(
    request_key: str = Path(pattern=REQUEST_KEY_PATTERN),
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    receipt = db.scalar(
        select(UploadReceipt).where(
            UploadReceipt.user_id == actor.id,
            UploadReceipt.request_key == request_key,
            UploadReceipt.expires_at > utcnow(),
        )
    )
    if receipt is None:
        raise NotFound()
    state = receipt.state
    asset = None
    if state == "complete":
        if receipt.asset_id is None:
            raise ApiError(
                "upload_result_unavailable", "The original upload is no longer available.", status=410
            )
        asset = asset_json(_authorized_asset(db, actor, receipt.asset_id), settings.api_prefix)
    elif state == "pending":
        reservation = db.get(UploadReservation, receipt.reservation_id) if receipt.reservation_id else None
        if reservation is None or reservation.expires_at <= utcnow():
            state = "expired"
    return {
        "request_key": receipt.request_key,
        "state": state,
        "created_at": receipt.created_at.isoformat(),
        "expires_at": receipt.expires_at.isoformat(),
        "asset": asset,
    }


@router.delete("/uploads/{asset_id}")
def discard_upload(
    asset_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(current_actor),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id, with_for_update=True)
    if asset is None or asset.owner_id != actor.id or asset.status != "provisional":
        raise NotFound()
    key = asset.storage_key
    db.delete(asset)
    db.commit()
    _store(request).delete(key)
    return {"ok": True}


def file_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    """Desktop session, or (with the panel header) a board-only panel session."""
    # <img> requests cannot send headers, so panels mark image URLs with ?panel=1 instead.
    if request.headers.get(PANEL_HEADER) or request.query_params.get("panel") == "1":
        return panel_actor(request, db)
    return current_actor(request, db)


def _authorized_asset(db: Session, actor: Actor, asset_id: uuid.UUID) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise NotFound()
    if actor.is_panel:
        # Panels see only images embedded on their own board.
        if (
            asset.board_workspace_id is None
            or asset.board_workspace_id != actor.session.workspace_id
            or not policy.can_read(db, actor.user, asset.board_workspace_id)
        ):
            raise NotFound()
        return asset
    if asset.status == "provisional":
        if asset.owner_id != actor.id:
            raise NotFound()
        return asset
    if asset.board_workspace_id is not None:
        # Board images are readable by anyone who can read that board.
        if not policy.can_read(db, actor.user, asset.board_workspace_id):
            raise NotFound()
        return asset
    if asset.chat_message_id is not None:
        message = db.get(ChatMessage, asset.chat_message_id)
        if message is None or not policy.can_read(db, actor.user, message.workspace_id):
            raise NotFound()
        return asset
    post = db.get(Post, asset.post_id)
    if post is None or post.deleted_at is not None or not policy.can_read(db, actor.user, post.workspace_id):
        raise NotFound()
    return asset


@router.get("/files/{asset_id}")
def download(
    asset_id: uuid.UUID, request: Request, actor: Actor = Depends(file_actor), db: Session = Depends(get_db)
):
    asset = _authorized_asset(db, actor, asset_id)
    path = _store(request).path(asset.storage_key)
    if not path.exists():
        raise NotFound()
    disposition = "attachment" if asset.media_type == "application/pdf" else "inline"
    return FileResponse(
        path,
        media_type=asset.media_type,
        filename=asset.display_name,
        content_disposition_type=disposition,
        headers=PROTECTED_HEADERS,
    )


@router.get("/files/{asset_id}/preview")
def preview(
    asset_id: uuid.UUID, request: Request, actor: Actor = Depends(file_actor), db: Session = Depends(get_db)
):
    asset = _authorized_asset(db, actor, asset_id)
    if not asset.has_preview:
        raise NotFound()
    path = _store(request).path(asset.storage_key, preview=True)
    if not path.exists():
        raise NotFound()
    return FileResponse(path, media_type="image/png", headers=PROTECTED_HEADERS)


def cleanup_provisional(db: Session, store: AssetStore, settings: Settings) -> int:
    """Remove provisional uploads older than the retention window. Never touches committed files."""
    cutoff = utcnow() - timedelta(hours=settings.provisional_upload_hours)
    stale = db.scalars(
        select(Asset)
        .where(Asset.status == "provisional", Asset.created_at < cutoff)
        .with_for_update(skip_locked=True)
    ).all()
    keys = [a.storage_key for a in stale]
    for a in stale:
        db.delete(a)
    db.commit()
    for key in keys:
        store.delete(key)
    return len(keys)
