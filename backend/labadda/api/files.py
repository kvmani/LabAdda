"""Attachment upload and protected same-origin download (S3 files)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import policy
from ..config import Settings
from ..deps import Actor, current_actor, get_db, get_settings
from ..errors import Invalid, NotFound
from ..models import Asset, Post
from ..security import utcnow
from ..serialize import asset_json
from ..storage import AssetStore, safe_display_name

router = APIRouter(tags=["files"])
PROTECTED_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


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
async def upload(request: Request, file: UploadFile = File(...), actor: Actor = Depends(current_actor),
                 db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    data = await _read_limited(file, settings.max_attachment_bytes)
    used = db.scalar(select(func.coalesce(func.sum(Asset.size), 0)).where(Asset.owner_id == actor.id)) or 0
    if used + len(data) > settings.user_quota_bytes:
        raise Invalid("quota_exceeded", "Your storage quota is full. Remove old attachments or ask an administrator.")
    stored = _store(request).save(data, file.content_type)
    asset = Asset(owner_id=actor.id, storage_key=stored.storage_key, media_type=stored.media_type,
                  display_name=safe_display_name(file.filename, stored.media_type), size=stored.size,
                  sha256=stored.sha256, has_preview=stored.has_preview)
    db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _store(request).delete(stored.storage_key)
        raise
    return asset_json(asset, settings.api_prefix)


@router.delete("/uploads/{asset_id}")
def discard_upload(asset_id: uuid.UUID, request: Request, actor: Actor = Depends(current_actor),
                   db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id, with_for_update=True)
    if asset is None or asset.owner_id != actor.id or asset.status != "provisional":
        raise NotFound()
    key = asset.storage_key
    db.delete(asset)
    db.commit()
    _store(request).delete(key)
    return {"ok": True}


def _authorized_asset(db: Session, actor: Actor, asset_id: uuid.UUID) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise NotFound()
    if asset.status == "provisional":
        if asset.owner_id != actor.id:
            raise NotFound()
        return asset
    post = db.get(Post, asset.post_id)
    if post is None or post.deleted_at is not None or not policy.can_read(db, actor.user, post.workspace_id):
        raise NotFound()
    return asset


@router.get("/files/{asset_id}")
def download(asset_id: uuid.UUID, request: Request, actor: Actor = Depends(current_actor),
             db: Session = Depends(get_db)):
    asset = _authorized_asset(db, actor, asset_id)
    path = _store(request).path(asset.storage_key)
    if not path.exists():
        raise NotFound()
    disposition = "attachment" if asset.media_type == "application/pdf" else "inline"
    return FileResponse(path, media_type=asset.media_type, filename=asset.display_name,
                        content_disposition_type=disposition, headers=PROTECTED_HEADERS)


@router.get("/files/{asset_id}/preview")
def preview(asset_id: uuid.UUID, request: Request, actor: Actor = Depends(current_actor),
            db: Session = Depends(get_db)):
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
    stale = db.scalars(select(Asset).where(Asset.status == "provisional", Asset.created_at < cutoff)
                       .with_for_update(skip_locked=True)).all()
    keys = [a.storage_key for a in stale]
    for a in stale:
        db.delete(a)
    db.commit()
    for key in keys:
        store.delete(key)
    return len(keys)
