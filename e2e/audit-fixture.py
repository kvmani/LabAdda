"""Audit explorer browser data restricted to the disposable local browser databases."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.engine import make_url

from labadda.config import load_settings
from labadda.db import session_factory
from labadda.models import AuditEvent, User, Workspace


def prepare() -> None:
    """Add fictional audit history without touching retained demos or operator databases."""
    settings = load_settings()
    url = make_url(settings.database_url)
    assert settings.environment == "test" and url.host == "localhost"
    assert url.database in {"labadda_e2e_root", "labadda_e2e_prefix"}
    with session_factory(settings.database_url)() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        ben = db.scalar(select(User).where(User.username == "ben"))
        unit = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.parent_id.is_not(None)))
        assert admin is not None and ben is not None and unit is not None
        if db.scalar(select(AuditEvent.id).where(AuditEvent.reason == "Browser check start")) is not None:
            return
        start = datetime(2026, 1, 5, 9, tzinfo=UTC)
        for index in range(130):
            db.add(
                AuditEvent(
                    actor_id=admin.id,
                    action="identity.update",
                    scope_type="identity",
                    target_id=str(ben.id),
                    reason="Browser check start" if index == 0 else f"Browser check {index:03}",
                    detail={"display_name": f"Ben {index:03}"},
                    created_at=start + timedelta(minutes=index),
                )
            )
        stamp = start + timedelta(days=1)
        db.add(
            AuditEvent(
                actor_id=admin.id,
                action="membership.set",
                scope_type="workspace",
                scope_id=str(unit.id),
                target_id=str(ben.id),
                reason="Role review",
                detail={"before": "member", "after": "steward"},
                created_at=stamp,
            )
        )
        db.add(
            AuditEvent(
                actor_id=admin.id,
                action="identity.update",
                scope_type="identity",
                target_id=str(ben.id),
                reason="=HYPERLINK(1)",
                created_at=stamp + timedelta(minutes=1),
            )
        )
        db.add(
            AuditEvent(
                actor_id=ben.id,
                action="auth.login",
                scope_type="identity",
                target_id=str(ben.id),
                outcome="denied",
                created_at=stamp + timedelta(minutes=2),
            )
        )
        db.commit()


if __name__ == "__main__":
    prepare()
