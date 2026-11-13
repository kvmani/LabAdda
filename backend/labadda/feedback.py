"""Feedback sent to the administrators: validation, storage and the shapes the console reads.

The person chooses to send this, so administrators may read it (unlike other content). Version,
commit, username and time are filled in here from the server; only the page and screen size
come from the browser, and both are validated.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit, buildinfo
from .config import Settings
from .errors import Conflict, Invalid, TooMany
from .identity_locks import lock_identity
from .models import Asset, Feedback, FeedbackMail
from .reservations import check_original_capacity
from .security import feedback_limiter, utcnow
from .serialize import iso
from .storage import FEEDBACK_TYPES, AssetStore, safe_display_name

CATEGORIES = ("problem", "suggestion", "question")
STATUSES = ("new", "seen", "resolved")
MAX_MESSAGE = 5000
MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
SENDS_PER_HOUR = 10
HOUR_SECONDS = 3600
SCREEN = re.compile(r"\d{2,5}x\d{2,5}")
CLIENT_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")


@dataclass(frozen=True)
class Upload:
    name: str | None
    content_type: str | None
    data: bytes


def clean_message(text: str) -> str:
    """Plain text: keep line breaks and tabs, refuse other control characters."""
    message = text.replace("\r\n", "\n").strip()
    if not message:
        raise Invalid("empty_message", "Write what you want to tell the administrators.")
    if len(message) > MAX_MESSAGE:
        raise Invalid("message_too_long", f"Keep the message under {MAX_MESSAGE} characters.")
    if any(unicodedata.category(c) in {"Cc", "Cs"} and c not in "\n\t" for c in message):
        raise Invalid("invalid_message", "The message contains characters that cannot be sent.")
    return message


def clean_route(route: str | None) -> str | None:
    """Keep the page path only: a query string or fragment could carry a token or a search."""
    if not route:
        return None
    path = route.split("?")[0].split("#")[0].strip()
    if not path.startswith("/") or len(path) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return None
    return path


def clean_screen(screen: str | None) -> str | None:
    return screen if screen and SCREEN.fullmatch(screen) else None


def _check_files(files: list[Upload], settings: Settings) -> None:
    if len(files) > min(MAX_FILES, settings.max_attachments):
        raise Invalid("too_many_attachments", f"Attach at most {MAX_FILES} files.")
    for upload in files:
        if not upload.data:
            raise Invalid("empty_file", "A file you attached is empty.")
        if len(upload.data) > MAX_FILE_BYTES:
            raise Invalid(
                "file_too_large", f"Each file must be {MAX_FILE_BYTES // (1024 * 1024)} MiB or smaller."
            )
    if sum(len(u.data) for u in files) > MAX_TOTAL_BYTES:
        raise Invalid(
            "files_too_large",
            f"All files together must be {MAX_TOTAL_BYTES // (1024 * 1024)} MiB or smaller.",
        )


def _existing(db: Session, user_id: uuid.UUID, client_id: str) -> Feedback | None:
    return db.scalar(select(Feedback).where(Feedback.user_id == user_id, Feedback.client_id == client_id))


def submit(
    db: Session,
    store: AssetStore,
    actor,
    settings: Settings,
    *,
    client_id: str,
    category: str,
    message: str,
    route: str | None,
    screen: str | None,
    user_agent: str | None,
    files: list[Upload],
    session_factory,
) -> Feedback:
    """Store the message and files, queue the e-mail copy and commit; return the saved row."""
    if not CLIENT_ID.fullmatch(client_id):
        raise Invalid("invalid_request_id", "Reload the page and try again.")
    if category not in CATEGORIES:
        raise Invalid("invalid_category", "Choose problem, suggestion or question.")
    message = clean_message(message)
    _check_files(files, settings)
    identity = SimpleNamespace(id=actor.id, session=SimpleNamespace(id=actor.session.id))
    user = lock_identity(db, identity, settings)
    previous = _existing(db, user.id, client_id)
    if previous is not None:
        if previous.message != message or previous.category != category:
            raise Conflict("client_id_reused", "This request ID was already used for different feedback.")
        return previous
    if not feedback_limiter.hit(f"feedback:{user.id}", SENDS_PER_HOUR, HOUR_SECONDS):
        raise TooMany("feedback_rate_limited", "You have sent a lot of feedback this hour. Try again later.")
    if files:
        check_original_capacity(db, identity, settings, sum(len(u.data) for u in files))
    stored = []
    try:
        for upload in files:
            stored.append((store.save(upload.data, upload.content_type, FEEDBACK_TYPES), upload.name))
        row = Feedback(
            user_id=user.id,
            client_id=client_id,
            username=user.username,
            created_at=utcnow(),
            category=category,
            message=message,
            route=clean_route(route),
            software_version=buildinfo.software_version(),
            commit=buildinfo.software_commit(),
            user_agent=(user_agent or "")[:300] or None,
            screen=clean_screen(screen),
        )
        db.add(row)
        db.flush()
        for position, (file, name) in enumerate(stored):
            db.add(
                Asset(
                    owner_id=user.id,
                    feedback_id=row.id,
                    # Strictly increasing so attachments keep the order the person chose.
                    created_at=row.created_at + timedelta(microseconds=position),
                    status="committed",
                    storage_key=file.storage_key,
                    media_type=file.media_type,
                    display_name=safe_display_name(name, file.media_type),
                    size=file.size,
                    sha256=file.sha256,
                    has_preview=file.has_preview,
                    preview_size=file.preview_size,
                    preview_sha256=file.preview_sha256,
                )
            )
        db.add(FeedbackMail(feedback_id=row.id, next_attempt_at=utcnow()))
        audit.record(
            db,
            actor=user,
            action="feedback.submit",
            scope_type="site",
            target_id=row.id,
            category=category,
            files=len(files),
        )
        lock_identity(db, identity, settings)
    except Exception:
        db.rollback()
        for file, _ in stored:
            store.delete(file.storage_key)
        raise
    return _commit(
        db, store, row.id, stored, session_factory=session_factory, user_id=user.id, client_id=client_id
    )


def _commit(db, store, feedback_id, stored, *, session_factory, user_id, client_id) -> Feedback:
    try:
        db.commit()
    except Exception:
        db.rollback()
        # A lost COMMIT answer is not proof of rollback: keep the files if the row exists.
        with session_factory() as fresh:
            saved = _existing(fresh, user_id, client_id)
        if saved is None:
            for file, _ in stored:
                store.delete(file.storage_key)
        raise
    return db.get(Feedback, feedback_id)


def attachments(db: Session, feedback_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Asset]]:
    found: dict[uuid.UUID, list[Asset]] = {fid: [] for fid in feedback_ids}
    if feedback_ids:
        for asset in db.scalars(
            select(Asset).where(Asset.feedback_id.in_(feedback_ids)).order_by(Asset.created_at, Asset.id)
        ):
            found[asset.feedback_id].append(asset)
    return found


def attachment_counts(db: Session, feedback_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not feedback_ids:
        return {}
    rows = db.execute(
        select(Asset.feedback_id, func.count())
        .where(Asset.feedback_id.in_(feedback_ids))
        .group_by(Asset.feedback_id)
    )
    return dict(rows.all())


def mail_json(mail: FeedbackMail | None, configured: bool) -> dict:
    if mail is None:
        return {"status": "none", "attempts": 0, "reason": None, "sent_at": None, "next_attempt_at": None}
    return {
        "status": mail.status,
        "attempts": mail.attempts,
        "reason": mail.last_error,
        "sent_at": iso(mail.sent_at),
        "next_attempt_at": iso(mail.next_attempt_at) if mail.status == "queued" else None,
        "waiting_for_setup": mail.status == "queued" and not configured,
    }


def summary_json(row: Feedback, count: int, mail: FeedbackMail | None, configured: bool) -> dict:
    return {
        "id": str(row.id),
        "created_at": iso(row.created_at),
        "username": row.username,
        "category": row.category,
        "route": row.route,
        "status": row.status,
        "attachment_count": count,
        "email": mail_json(mail, configured),
    }


def detail_json(row: Feedback, assets: list[Asset], mail: FeedbackMail | None, settings: Settings) -> dict:
    base = f"{settings.api_prefix}/admin/feedback/{row.id}/attachments"
    return {
        **summary_json(row, len(assets), mail, settings.mail_configured),
        "message": row.message,
        "software_version": row.software_version,
        "commit": row.commit,
        "user_agent": row.user_agent,
        "screen": row.screen,
        "admin_note": row.admin_note,
        "handled_at": iso(row.handled_at),
        "attachments": [
            {
                "id": str(a.id),
                "display_name": a.display_name,
                "media_type": a.media_type,
                "size": a.size,
                "url": f"{base}/{a.id}",
                "preview_url": f"{base}/{a.id}/preview" if a.has_preview else None,
            }
            for a in assets
        ],
    }


def sent_json(row: Feedback) -> dict:
    """What the sender gets back: confirmation, not a copy of what administrators see."""
    return {"id": str(row.id), "created_at": iso(row.created_at)}


def metadata_preview(user, now: datetime | None = None) -> dict:
    """The server-known facts shown on the form so people see exactly what is sent."""
    return {
        "username": user.username,
        "time": iso(now or utcnow()),
        "software_version": buildinfo.software_version(),
        "commit": buildinfo.software_commit(),
    }
