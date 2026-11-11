"""Raise, repeat and resolve operational events from health state changes (AD-06).

A problem word (degraded, unavailable, stale) opens one event per item and word; repeats while
it stays open only raise its count. Only a healthy reading resolves an item's events: unknown and
unsupported readings neither raise nor resolve, and acknowledging never changes an item's state.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import OpsEvent
from .catalog import BY_KEY
from .types import PROBLEMS, Result

SEVERITY = {"degraded": "warning", "stale": "warning", "unavailable": "error"}
LIVE = ("open", "acknowledged")


def code_for(item: str, status: str) -> str:
    return f"{item}.{status}"


def _summary(item: str, result: Result) -> str:
    return f"{BY_KEY[item].label} is {result.status}. {result.detail}"[:240]


def _detail(result: Result) -> dict:
    return {"status": result.status, "value": result.value, "unit": result.unit, "message": result.detail}


def _resolve(db: Session, item: str, now: datetime, keep: str | None = None) -> None:
    statement = update(OpsEvent).where(OpsEvent.component == item, OpsEvent.state.in_(LIVE))
    if keep:
        statement = statement.where(OpsEvent.code != keep)
    db.execute(statement.values(state="resolved", resolved_at=now))


def apply(db: Session, item: str, result: Result, previous: str | None) -> None:
    """Bring the events of one item in line with its new reading; the caller commits."""
    now = result.checked_at
    if result.status == "healthy":
        if previous != "healthy":
            _resolve(db, item, now)
        return
    if result.status not in PROBLEMS:
        return
    code = code_for(item, result.status)
    _resolve(db, item, now, keep=code)
    live = db.scalar(
        select(OpsEvent).where(OpsEvent.code == code, OpsEvent.component == item, OpsEvent.state.in_(LIVE))
    )
    if live is None:
        db.add(
            OpsEvent(
                code=code,
                component=item,
                severity=SEVERITY[result.status],
                summary=_summary(item, result),
                detail=_detail(result),
                first_at=now,
                last_at=now,
                count=1,
                state="open",
            )
        )
    elif previous != result.status:
        # Seen again after a restart or a lapse in sampling: a repeat, not a new row.
        live.count += 1
        live.last_at = now
        live.summary = _summary(item, result)
        live.detail = _detail(result)
