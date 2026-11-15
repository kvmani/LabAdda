"""In-app system configuration management with fallback to environment Settings."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from .config import Settings
from .models import SystemSetting
from .security import utcnow

log = logging.getLogger("labadda.settings")


def get_setting(db: Session, key: str, default: str = "") -> str:
    """Return the setting value stored in database, or the given default."""
    row = db.get(SystemSetting, key)
    return row.value if row is not None else default


def get_max_whiteboards(db: Session, settings: Settings) -> int:
    """Get the effective allowed number of whiteboards per scope."""
    val = get_setting(db, "max_whiteboards_per_scope", "")
    if val.isdigit():
        return max(1, min(20, int(val)))
    return settings.max_whiteboards_per_scope


def set_setting(
    db: Session,
    key: str,
    value: str,
    description: str | None = None,
    user_id: uuid.UUID | None = None,
) -> SystemSetting:
    """Insert or update a system setting row."""
    row = db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(
            key=key,
            value=value,
            description=description,
            updated_at=utcnow(),
            updated_by=user_id,
        )
        db.add(row)
    else:
        row.value = value
        if description is not None:
            row.description = description
        row.updated_at = utcnow()
        row.updated_by = user_id
    db.commit()
    log.info("System setting '%s' updated to '%s' by user %s", key, value, user_id)
    return row
