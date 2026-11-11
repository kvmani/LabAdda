"""Sample the AD-08 gauges once per flush: sessions, sockets, database, asset and disk sizes.

A gauge that cannot be read is skipped for that minute, so it shows as a gap ("unknown"),
never as zero.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Asset, AuthSession
from .registry import REGISTRY, Registry

log = logging.getLogger("labadda.metrics")

# AD-07: "signed-in sessions seen in the last 5 minutes".
ACTIVE_WINDOW = timedelta(minutes=5)


def active_sessions(db: Session, now: datetime) -> int:
    """Normal (not board-only) sessions that are open and were seen recently."""
    return db.scalar(
        select(func.count())
        .select_from(AuthSession)
        .where(
            AuthSession.kind == "normal",
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            AuthSession.last_seen_at >= now - ACTIVE_WINDOW,
        )
    )


def database_bytes(db: Session) -> int:
    return db.scalar(select(func.pg_database_size(func.current_database())))


def asset_bytes(db: Session) -> int:
    """Stored originals plus previews, as one aggregate without names or owners."""
    return db.scalar(select(func.coalesce(func.sum(Asset.size + func.coalesce(Asset.preview_size, 0)), 0)))


def sample(
    db: Session, *, settings: Settings, sockets: int, now: datetime, registry: Registry = REGISTRY
) -> None:
    """Record every gauge that can be read now into the current minute."""
    readings: dict[str, Callable[[], float]] = {
        "sessions.active": lambda: active_sessions(db, now),
        "db.size_bytes": lambda: database_bytes(db),
        "assets.bytes": lambda: asset_bytes(db),
        "disk.free_bytes": lambda: shutil.disk_usage(settings.asset_dir).free,
    }
    registry.set_gauge("sockets.connected", sockets, now=now)
    for name, read in readings.items():
        try:
            # A slow catalogue query must not hold the scheduler or the database.
            db.execute(text("set local statement_timeout = '2s'"))
            value = read()
        except Exception:  # noqa: BLE001 — any failure leaves this gauge unknown for the minute
            db.rollback()
            log.warning("metrics.gauge_unavailable", extra={"metric": name})
            continue
        registry.set_gauge(name, value, now=now)
    db.rollback()
