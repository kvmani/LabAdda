"""Staff-state consistency and date-only sign-in observations; no content authority."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from .config import Settings
from .models import User
from .security import utcnow

StaffStatus = Literal["invited", "active", "on_leave", "suspended", "retired", "left"]
STATUSES = ("invited", "active", "on_leave", "suspended", "retired", "left")


def site_date(settings: Settings, *, now: datetime | None = None) -> date:
    """Resolve a calendar date in the configured site zone, not the host zone."""
    instant = now or utcnow()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("A timezone-aware observation is required")
    return instant.astimezone(ZoneInfo(settings.timezone)).date()


def set_status(
    user: User,
    status: StaffStatus,
    *,
    effective_on: date | None = None,
    leave_sign_in: bool | None = None,
) -> None:
    """Keep the legacy access switch consistent without silently activating an invite."""
    if status not in STATUSES:
        raise ValueError("Unknown staff status")
    if leave_sign_in is not None and status != "on_leave":
        raise ValueError("Leave sign-in choice only applies to on_leave")
    enabled = status in {"invited", "active", "on_leave"}
    if status == "on_leave" and leave_sign_in is not None:
        enabled = leave_sign_in
    changed = user.status != status or user.is_active != enabled
    user.status = status
    # Invited accounts need the activation endpoint; normal login still requires a password.
    user.is_active = enabled
    if status == "invited":
        user.must_set_password = True
    if changed:
        user.status_effective_on = effective_on
        user.revision = (user.revision + 1) if user.revision is not None else 1


def record_sign_in(db: Session, user: User, settings: Settings, *, now: datetime | None = None) -> None:
    """Persist only the site-local date; concurrent logins cannot move it backwards."""
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(last_seen_on=func.greatest(User.last_seen_on, site_date(settings, now=now)))
    )


def patch_legacy_record(
    user: User,
    *,
    display_name: str | None,
    is_admin: bool | None,
    is_active: bool | None,
    effective_on: date,
) -> dict[str, str | bool | int | None]:
    """Keep the compatibility endpoint versioned, with bounded audit metadata."""
    previous_revision = user.revision
    changes = {
        "status_before": user.status,
        "name_before": user.display_name,
        "admin_before": user.is_admin,
        "access_before": user.is_active,
        "revision_before": previous_revision,
    }
    if display_name is not None:
        user.display_name = display_name.strip()
    if is_admin is not None:
        user.is_admin = is_admin
    if is_active is not None and is_active != user.is_active:
        if user.status == "on_leave":
            set_status(user, "on_leave", leave_sign_in=is_active, effective_on=effective_on)
        else:
            enabled_status = "invited" if user.must_set_password else "active"
            set_status(user, enabled_status if is_active else "left", effective_on=effective_on)
    if display_name is not None or is_admin is not None or is_active is not None:
        user.revision = previous_revision + 1
    changes.update(
        status_after=user.status,
        name_after=user.display_name,
        admin_after=user.is_admin,
        access_after=user.is_active,
        revision_after=user.revision,
    )
    return changes
