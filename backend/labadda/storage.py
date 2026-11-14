"""Validated attachment storage outside the code tree (S3 files)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import logging
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .errors import Invalid

SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}
EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "text/plain": ".txt",
}
# Feedback also takes WebP screenshots and plain-text logs; every other upload keeps the shorter list.
FEEDBACK_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg", "image/webp", "text/plain"})
DEFAULT_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})
PREVIEW_MAX = 800
Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs


@dataclass
class StoredFile:
    storage_key: str
    media_type: str
    size: int
    sha256: str
    has_preview: bool
    preview_size: int
    preview_sha256: str | None


def safe_display_name(name: str | None, media_type: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[^\w .()+-]", "_", base).strip(" .") or "attachment"
    stem, _ = os.path.splitext(base)
    return (stem[:150] or "attachment") + EXTENSIONS[media_type]


def _looks_like_text(data: bytes) -> bool:
    """Plain text is the only type with no signature: accept valid UTF-8 without control bytes."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return all(c in "\t\n\r" or (c >= " " and c != "\x7f") for c in text)


def _check_declared(media_type: str, declared: str | None) -> str:
    accepted = {media_type, "application/octet-stream"}
    if media_type == "image/jpeg":
        accepted.add("image/jpg")
    if media_type == "text/plain":
        accepted.add("text/csv")
    if declared and declared not in accepted:
        raise Invalid("type_mismatch", "The file type does not match its contents.")
    return media_type


def detect_media_type(
    head: bytes, declared: str | None, allowed: frozenset[str] = DEFAULT_TYPES, whole: bytes | None = None
) -> str:
    """Decide the type from the bytes; the declared type may only agree, never decide."""
    if "image/webp" in allowed and head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return _check_declared("image/webp", declared)
    for media_type, sigs in SIGNATURES.items():
        if media_type in allowed and any(head.startswith(s) for s in sigs):
            return _check_declared(media_type, declared)
    if "text/plain" in allowed and whole is not None and _looks_like_text(whole):
        return _check_declared("text/plain", declared)
    if allowed == FEEDBACK_TYPES:
        raise Invalid("unsupported_type", "Attach PNG, JPEG or WebP pictures, PDF or text files only.")
    raise Invalid("unsupported_type", "Attach PDF, PNG or JPEG files only.")


class AssetStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, storage_key: str, preview: bool = False) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", storage_key):
            raise ValueError("bad storage key")
        name = storage_key + (".preview.png" if preview else ".bin")
        return self.root / storage_key[:2] / name

    def save(
        self, data: bytes, declared_type: str | None, allowed: frozenset[str] = DEFAULT_TYPES
    ) -> StoredFile:
        media_type = detect_media_type(data[:16], declared_type, allowed, data)
        has_preview = False
        preview_bytes = None
        if media_type.startswith("image/"):
            preview_bytes = self._sanitized_preview(data)
            has_preview = True
        key = secrets.token_urlsafe(24)
        target = self.path(key)
        missing_directories = []
        directory = target.parent
        while not directory.exists():
            missing_directories.append(directory)
            directory = directory.parent
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        owned = []
        try:
            # Exclusive creation and no-clobber publication prevent a collision
            # from replacing/deleting somebody else's existing object.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            owned.append(tmp)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(tmp, target)
            owned.append(target)
            tmp.unlink()
            if preview_bytes is not None:
                preview = self.path(key, preview=True)
                fd = os.open(preview, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                owned.append(preview)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(preview_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            # Sync both file entries and each newly created directory's entry
            # in its parent, up through the previously existing ancestor.
            if hasattr(os, "O_DIRECTORY"):
                directories = [target.parent, *(path.parent for path in missing_directories)]
                for path in dict.fromkeys(directories):
                    directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
        except Exception:
            for path in reversed(owned):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logging.getLogger("labadda").error("asset_partial_write_cleanup_failed")
            raise
        return StoredFile(
            key,
            media_type,
            len(data),
            hashlib.sha256(data).hexdigest(),
            has_preview,
            len(preview_bytes) if preview_bytes is not None else 0,
            hashlib.sha256(preview_bytes).hexdigest() if preview_bytes is not None else None,
        )

    @staticmethod
    def _sanitized_preview(data: bytes) -> bytes:
        """Decode and re-encode as a fresh PNG; drops metadata and any trailing payload."""
        try:
            with Image.open(io.BytesIO(data)) as img:
                if img.width * img.height > Image.MAX_IMAGE_PIXELS:
                    raise Invalid("image_too_large", "The image exceeds the supported pixel limit.")
                img.load()
                preview = img.convert("RGBA") if img.mode in ("P", "LA", "RGBA") else img.convert("RGB")
                preview.thumbnail((PREVIEW_MAX, PREVIEW_MAX))
                out = io.BytesIO()
                preview.save(out, format="PNG")
                return out.getvalue()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
            raise Invalid("invalid_image", "The image could not be read.") from None

    def delete(self, storage_key: str) -> None:
        for preview in (False, True):
            with contextlib.suppress(FileNotFoundError):
                self.path(storage_key, preview).unlink()
