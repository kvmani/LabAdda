"""The site notice banner (AD-11): one short plain-text notice, shown between two times."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from . import audit
from .errors import Conflict, Invalid
from .models import SiteBanner, User
from .security import utcnow
from .serialize import iso

MAX_LENGTH = 280
Level = Literal["info", "warning"]


def clean_message(text: str) -> str:
    """Plain text on one line: markup is shown as typed (the page escapes it), controls refused."""
    message = " ".join(text.split())
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in message):
        raise Invalid("invalid_banner", "The notice may contain letters, numbers and punctuation only.")
    if len(message) > MAX_LENGTH:
        raise Invalid("banner_too_long", f"The notice may be at most {MAX_LENGTH} characters.")
    return message


def banner_json(row: SiteBanner | None) -> dict | None:
    if row is None:
        return None
    return {
        "message": row.message,
        "level": row.level,
        "starts_at": iso(row.starts_at),
        "ends_at": iso(row.ends_at),
        "revision": row.revision,
    }


def active_banner(db: Session, now: datetime | None = None) -> SiteBanner | None:
    row = db.get(SiteBanner, 1)
    now = now or utcnow()
    return row if row is not None and row.starts_at <= now < row.ends_at else None


def save_banner(
    db: Session,
    actor: User,
    *,
    message: str,
    level: Level | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
    expected_revision: int,
) -> SiteBanner | None:
    """Publish, replace or (with an empty message) remove the notice; audited in the same commit."""
    row = db.get(SiteBanner, 1, with_for_update=True)
    if (row.revision if row else 0) != expected_revision:
        raise Conflict("banner_changed", "The notice was changed by someone else. Reload and try again.")
    now = utcnow()
    text = clean_message(message)
    before = {"level": row.level, "starts_at": iso(row.starts_at), "ends_at": iso(row.ends_at)} if row else {}
    if not text:
        if row is None:
            return None
        db.delete(row)
        audit.record(db, actor=actor, action="site.banner_clear", scope_type="site", before=before)
        db.commit()
        return None
    if level is None or ends_at is None:
        raise Invalid("invalid_banner", "Choose a level and an end time for the notice.")
    starts = starts_at or now
    if ends_at <= starts or ends_at <= now:
        raise Invalid("invalid_banner_times", "The notice must end after it starts, in the future.")
    if row is None:
        row = SiteBanner(id=1, revision=0)
        db.add(row)
    row.message, row.level, row.starts_at, row.ends_at = text, level, starts, ends_at
    row.revision += 1
    row.updated_at = now
    # The text itself stays out of the trail; the length is enough to tell what was published.
    audit.record(
        db,
        actor=actor,
        action="site.banner_set",
        scope_type="site",
        before=before,
        after={"level": level, "starts_at": iso(starts), "ends_at": iso(ends_at)},
        message_length=len(text),
    )
    db.commit()
    return row
