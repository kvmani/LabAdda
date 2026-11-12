"""Activity page browser data, restricted to the disposable local browser databases."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

from labadda.config import load_settings
from labadda.db import session_factory
from labadda.metrics.flush import upsert
from labadda.metrics.registry import Sample
from labadda.models import ActivityDay, UsageReaderGrant, User, Workspace
from labadda.people import site_date

# Six active people in Thin Films (shown); four in the division and Chen in Catalysis are
# left out together, so the page shows one suppressed unit beside a published one.
GROUPS = (("Thin Films Section", "films", 6), ("Surface Science Division", "division", 4))


def _people(db, unit_name: str, prefix: str, count: int) -> list[User]:
    unit = db.scalar(select(Workspace).where(Workspace.kind == "org", Workspace.name == unit_name))
    assert unit is not None
    found = []
    for number in range(count):
        username = f"activity-{prefix}-{number}"
        person = db.scalar(select(User).where(User.username == username))
        if person is None:
            person = User(
                username=username,
                display_name=f"Synthetic {prefix} {number}",
                must_set_password=True,
                home_workspace_id=unit.id,
            )
            db.add(person)
            db.flush()
        found.append(person)
    return found


def _samples(now: datetime) -> list[Sample]:
    hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    rows = [
        Sample(hour, "posts.created", "org", 4, 1),
        Sample(hour, "chat.messages", "group", 6, 1),
        Sample(hour, "tasks.created", "project", 2, 1),
        Sample(hour, "uploads.count", "org", 3, 1),
        Sample(hour, "uploads.size_band", "under_1mb", 3, 1),
        Sample(hour, "sockets.connected", "", 5, 1),
        Sample(hour, "assets.bytes", "", 3_500_000, 1),
        Sample(hour, "db.size_bytes", "", 48_000_000, 1),
    ]
    rows += [
        Sample(hour - timedelta(hours=back), "http.requests", "chat", 10 + back, 1) for back in range(12)
    ]
    return rows


def prepare() -> None:
    settings = load_settings()
    url = make_url(settings.database_url)
    assert settings.environment == "test" and url.host == "localhost"
    assert url.database in {"labadda_e2e_root", "labadda_e2e_prefix"}
    now = datetime.now(UTC)
    today = site_date(settings, now=now)
    with session_factory(settings.database_url)() as db:
        active = [person for unit, prefix, count in GROUPS for person in _people(db, unit, prefix, count)]
        chen = db.scalar(select(User).where(User.username == "chen"))
        admin = db.scalar(select(User).where(User.username == "admin"))
        dana = db.scalar(select(User).where(User.username == "dana"))
        assert chen is not None and admin is not None and dana is not None
        for person in [*active, chen]:
            db.execute(insert(ActivityDay).values(user_id=person.id, day=today).on_conflict_do_nothing())
        upsert(db, "hour", _samples(now))
        if db.get(UsageReaderGrant, dana.id) is None:
            db.add(
                UsageReaderGrant(
                    user_id=dana.id,
                    granted_by=admin.id,
                    reason="Synthetic browser check",
                    expires_at=now + timedelta(hours=4),
                )
            )
        db.commit()


if __name__ == "__main__":
    prepare()
