"""The administrator setup checklist (HP-07): each item is derived from real state, never ticked.

Every item is `done`, `not_done` or `unknown`. A reading that cannot be taken is `unknown`, never
`not_done` and never `done`. The detail sentences hold counts only, never names or content.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .backup_report import backup_report
from .config import Settings
from .models import User, Workspace
from .overview.people_attention import STAFF_STATUSES, count_units_without_steward


def _item(key: str, label: str, state: str, detail: str, link: tuple[str, str]) -> dict:
    return {
        "key": key,
        "label": label,
        "state": state,
        "detail": detail,
        "screen": link[0],
        "help": link[1],
    }


def _count(db: Session, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0


def _admins(db: Session) -> dict:
    found = _count(db, User.is_admin.is_(True), User.is_active.is_(True))
    return _item(
        "second_admin",
        "A second administrator",
        "done" if found >= 2 else "not_done",
        f"{found} active administrator{'' if found == 1 else 's'}.",
        ("/admin/people", "admin/add-a-person"),
    )


def _units(db: Session) -> dict:
    found = (
        db.scalar(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.kind == "org", Workspace.archived.is_(False), Workspace.parent_id.is_not(None))
        )
        or 0
    )
    return _item(
        "units",
        "Organisation units created",
        "done" if found else "not_done",
        f"{found} unit{'' if found == 1 else 's'} below the top of the organisation.",
        ("/admin/org", "admin/create-move-merge-close-units"),
    )


def _people(db: Session) -> dict:
    found = _count(db, User.is_admin.is_(False), User.is_active.is_(True), User.status.in_(STAFF_STATUSES))
    return _item(
        "people",
        "People added",
        "done" if found else "not_done",
        f"{found} {'person' if found == 1 else 'people'} besides administrators.",
        ("/admin/people", "admin/import-a-staff-list"),
    )


def _stewards(db: Session) -> dict:
    units = db.scalar(
        select(func.count())
        .select_from(Workspace)
        .where(Workspace.kind == "org", Workspace.archived.is_(False))
    )
    missing = count_units_without_steward(db)
    detail = f"{missing} of {units} units have no steward or Head." if missing else "Every unit has one."
    return _item(
        "stewards",
        "A steward or Head for every unit",
        "done" if not missing else "not_done",
        detail,
        ("/admin/org", "admin/unit-administrators"),
    )


def _backups(report: dict) -> dict:
    word = report["status"]
    state = {"healthy": "done", "unknown": "unknown"}.get(word, "not_done")
    return _item(
        "backups",
        "Backups reporting healthy",
        state,
        report["headline"],
        ("/admin/backups", "admin/backups-page"),
    )


def _time_zone(settings: Settings) -> dict:
    set_by_operator = settings.timezone_configured
    return _item(
        "time_zone",
        "Site time zone confirmed",
        "done" if set_by_operator else "not_done",
        f"The site time zone is {settings.timezone}."
        + ("" if set_by_operator else " The operator has not set one, so the default is in use."),
        ("/admin/settings", "admin/settings"),
    )


def _restore(report: dict) -> dict:
    recorded = report["restore_rehearsal"]
    return _item(
        "test_restore",
        "A test restore recorded",
        "done" if recorded else "unknown",
        "A test restore is recorded." if recorded else "No test restore has been recorded or measured.",
        ("/admin/backups", "admin/backups-page"),
    )


def build_checklist(db: Session, settings: Settings, now: datetime) -> dict:
    report = backup_report(settings, now)
    items = [
        _admins(db),
        _units(db),
        _people(db),
        _stewards(db),
        _backups(report),
        _time_zone(settings),
        _restore(report),
    ]
    return {
        "checked_at": now.isoformat().replace("+00:00", "Z"),
        "done": sum(item["state"] == "done" for item in items),
        "total": len(items),
        "items": items,
    }
