"""C5 private alert policy, concurrency and delivery category semantics."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from labadda import notify
from labadda.cli import alembic_config
from labadda.models import Notification, NotificationPreference
from tests.migration_helpers import downgrade_legacy


def choices(revision=0, **override):
    return {"revision": revision, "mentions": True, "official_notices": True, "reminders": True, **override}


def test_defaults_owner_revision_and_validation(as_user):
    ben, asha = as_user("ben"), as_user("asha")
    assert ben.get("/notification-preferences").json() == choices()
    response = ben.put("/notification-preferences", json=choices(mentions=False))
    assert response.status_code == 200 and response.json() == choices(1, mentions=False)
    assert asha.get("/notification-preferences").json() == choices()
    assert ben.put("/notification-preferences", json=choices()).status_code == 409
    assert ben.put("/notification-preferences", json=choices(1, mentions="false")).status_code == 422
    assert ben.put("/notification-preferences", json={**choices(1), "user_id": "another"}).status_code == 422
    assert ben.get("/notification-preferences", headers={"X-LabAdda-Panel": "1"}).status_code == 401
    assert ben.client.put(ben.url("/notification-preferences"), json=choices(1)).status_code == 403


def test_muted_mentions_do_not_queue_and_existing_history_remains(as_user, ids):
    ben, asha = as_user("ben"), as_user("asha")
    ws = ids["workspaces"]["section_a"]

    def mention(text):
        return asha.post(
            f"/workspaces/{ws}/chat", json={"body": "@ben " + text, "client_id": str(uuid.uuid4())}
        )

    assert mention("Before mute").status_code == 201
    assert ben.put("/notification-preferences", json=choices(mentions=False)).status_code == 200
    assert mention("While muted").status_code == 201
    titles = [row["title"] for row in ben.get("/notifications").json()["items"]]
    assert len(titles) == 1 and "Before mute" in titles[0]
    assert ben.put("/notification-preferences", json=choices(1)).status_code == 200
    assert mention("After enabling").status_code == 201
    assert len(ben.get("/notifications").json()["items"]) == 2


@pytest.mark.parametrize(
    "kind,field", [("mention", "mentions"), ("official", "official_notices"), ("reminder", "reminders")]
)
def test_categories_filter_string_and_uuid_recipients_independently(as_user, ids, db_factory, kind, field):
    api = as_user("ben")
    assert api.put("/notification-preferences", json=choices(**{field: False})).status_code == 200
    with db_factory() as db:
        created = notify.create(
            db,
            recipients=[ids["users"]["ben"], uuid.UUID(ids["users"]["asha"])],
            kind=kind,
            workspace_id=uuid.UUID(ids["workspaces"]["section_a"]),
            source_type="chat",
            source_id=uuid.uuid4(),
            occurrence="synthetic",
        )
        db.commit()
        assert created == 1
        rows = db.scalars(select(Notification)).all()
        assert len(rows) == 1 and str(rows[0].recipient_id) == ids["users"]["asha"]


def test_concurrent_preferences_do_not_overwrite_and_downgrade_guard(as_user, settings):
    api = as_user("ben")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=5).status_code
            for future in [
                pool.submit(api.put, "/notification-preferences", json=choices(mentions=False)),
                pool.submit(api.put, "/notification-preferences", json=choices(reminders=False)),
            ]
        ]
    assert sorted(results) == [200, 409] and api.get("/notification-preferences").json()["revision"] == 1
    with pytest.raises(Exception, match="Notification preferences exist"):
        downgrade_legacy(alembic_config(settings.database_url), "0024")


def test_expired_save_rolls_back_choices(as_user, db_factory, monkeypatch):
    from labadda import identity_locks
    from labadda.api import alert_preferences

    api = as_user("ben")
    original = alert_preferences.lock_identity

    def expire(db, actor, settings):
        monkeypatch.setattr(identity_locks, "session_valid", lambda *_: False)
        return original(db, actor, settings)

    monkeypatch.setattr(alert_preferences, "lock_identity", expire)
    assert api.put("/notification-preferences", json=choices(mentions=False)).status_code == 401
    with db_factory() as db:
        assert db.scalar(select(NotificationPreference)) is None


def test_skipped_scheduled_reminder_is_not_replayed_after_enable(as_user, db_factory):
    from datetime import timedelta

    from labadda.scheduler import process_due_reminders
    from labadda.security import utcnow

    api = as_user("ben")
    now = utcnow()
    assert api.put("/notification-preferences", json=choices(reminders=False)).status_code == 200
    assert (
        api.post(
            "/notes",
            json={
                "title": "Muted scheduled note",
                "body": "Synthetic",
                "remind_at": (now - timedelta(seconds=1)).isoformat(),
            },
        ).status_code
        == 201
    )
    with db_factory() as db:
        assert process_due_reminders(db, now=now) == 0
    assert api.put("/notification-preferences", json=choices(1)).status_code == 200
    with db_factory() as db:
        assert process_due_reminders(db, now=now + timedelta(minutes=1)) == 0
    assert api.get("/notifications").json()["items"] == []
