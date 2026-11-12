"""Overview browser data, restricted to the disposable local browser databases.

Usage: overview-fixture.py clean | problems | restore
"""

import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from labadda.config import load_settings
from labadda.db import session_factory
from labadda.metrics.flush import upsert
from labadda.metrics.registry import Sample
from labadda.models import (
    Membership,
    MetricSample,
    OpsEvent,
    UsageReaderGrant,
    User,
    Workspace,
)

STEWARD = "asha"


def _units(db) -> list[Workspace]:
    return list(db.scalars(select(Workspace).where(Workspace.kind == "org")))


def _staff_every_unit(db, steward: User) -> None:
    for unit in _units(db):
        has_steward = db.scalar(
            select(Membership.id)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == unit.id,
                Membership.role == "steward",
                User.is_active,
            )
        )
        mine = db.scalar(
            select(Membership).where(Membership.workspace_id == unit.id, Membership.user_id == steward.id)
        )
        if has_steward is None and mine is None:
            db.add(Membership(user_id=steward.id, workspace_id=unit.id, role="steward"))


def _remove_steward(db, unit_name: str) -> None:
    unit = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.name == unit_name))
    assert unit is not None
    db.execute(delete(Membership).where(Membership.workspace_id == unit.id, Membership.role == "steward"))


def _latency(now: datetime) -> list[Sample]:
    hour = now.replace(minute=0, second=0, microsecond=0)
    return [
        Sample(
            hour - timedelta(days=back, hours=1),
            "http.latency_p95",
            "all",
            80 + back * 9,
            1,
        )
        for back in range(5)
    ]


def _gauges(now: datetime) -> list[Sample]:
    """Readings a few minutes old so that the tiles are measured whatever the live collector wrote."""
    minute = now.replace(second=0, microsecond=0) - timedelta(minutes=2)
    return [
        Sample(minute, "sessions.active", "", 7, 1),
        Sample(minute, "sockets.connected", "", 3, 1),
        Sample(minute, "assets.bytes", "", 2 * 1024**2, 1),
        Sample(minute, "db.size_bytes", "", 8 * 1024**2, 1),
    ]


def prepare(mode: str) -> None:
    settings = load_settings()
    url = make_url(settings.database_url)
    assert settings.environment == "test" and url.host == "localhost"
    assert url.database in {"labadda_e2e_root", "labadda_e2e_prefix"}
    now = datetime.now(UTC)
    with session_factory(settings.database_url)() as db:
        steward = db.scalar(select(User).where(User.username == STEWARD))
        dana = db.scalar(select(User).where(User.username == "dana"))
        admin = db.scalar(select(User).where(User.username == "admin"))
        assert steward is not None and dana is not None and admin is not None
        db.execute(delete(OpsEvent))
        db.execute(
            delete(MetricSample).where(
                MetricSample.metric == "http.latency_p95",
                MetricSample.resolution == "hour",
            )
        )
        if mode in {"clean", "problems"}:
            upsert(db, "hour", _latency(now))
            upsert(db, "minute", _gauges(now))
            if db.get(UsageReaderGrant, dana.id) is None:
                db.add(
                    UsageReaderGrant(
                        user_id=dana.id,
                        granted_by=admin.id,
                        reason="Synthetic browser check",
                        expires_at=now + timedelta(hours=4),
                    )
                )
        if mode == "clean":
            _staff_every_unit(db, steward)
        elif mode == "problems":
            _staff_every_unit(db, steward)
            _remove_steward(db, "Catalysis Section")
            db.add(
                OpsEvent(
                    code="scheduler.late",
                    component="scheduler",
                    severity="critical",
                    summary="A scheduled task has not run.",
                    detail={},
                    first_at=now,
                    last_at=now,
                )
            )
        else:
            # Put back what the fixture seeds: Asha steers only her own section.
            keep = db.scalar(select(Workspace.id).where(Workspace.name == "Thin Films Section"))
            db.execute(
                delete(Membership).where(
                    Membership.user_id == steward.id,
                    Membership.role == "steward",
                    Membership.workspace_id != keep,
                )
            )
        db.commit()


if __name__ == "__main__":
    prepare(sys.argv[1])
