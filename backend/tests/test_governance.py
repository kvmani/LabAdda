"""T15/T28/T29 foundation: proposals never activate a rule."""

import pytest


def payload(revision=0, **profile):
    return {"base_revision": revision, "reason": "Synthetic capacity review", "profile": profile}


def test_draft_revisions_conflicts_and_observation(as_user):
    admin = as_user("admin")
    before = admin.get("/admin/policy-drafts").json()
    assert before["latest_revision"] == 0
    assert not before["activation_supported"]
    first = admin.post("/admin/policy-drafts", json=payload())
    assert first.status_code == 201 and first.json()["revision"] == 1
    assert first.json()["enforced"] is False
    assert admin.post("/admin/policy-drafts", json=payload()).status_code == 409
    assert (
        admin.post("/admin/policy-drafts", json=payload(1, user_quota_bytes=800 * 1024**2)).status_code == 201
    )
    after = admin.get("/admin/policy-drafts", params={"before": 2}).json()
    assert len(after["drafts"]) == 1
    assert after["runtime_limits"] == before["runtime_limits"]
    audit = admin.get("/admin/audit").json()["events"]
    assert sum(e["action"] == "policy.draft" for e in audit) == 2


@pytest.mark.parametrize(
    "profile",
    [
        {"mode": "enforced"},
        {"unknown": 1},
        {"user_quota_bytes": True},
        {"max_attachment_bytes": 0},
        {"max_attachment_bytes": 30, "user_quota_bytes": 20},
        {"schema_version": 3},
    ],
)
def test_invalid_policy_never_saved(as_user, profile):
    admin = as_user("admin")
    assert admin.post("/admin/policy-drafts", json=payload(**profile)).status_code == 422
    assert admin.get("/admin/policy-drafts").json()["latest_revision"] == 0


def test_non_admin_denied(as_user):
    ben = as_user("ben")
    assert ben.get("/admin/policy-drafts").status_code == 403
    assert ben.post("/admin/policy-drafts", json=payload()).status_code == 403


def test_csrf_required(as_user):
    admin = as_user("admin")
    assert admin.client.post(admin.url("/admin/policy-drafts"), json=payload()).status_code == 403


def test_history_survives_downgrade_attempt(as_user, settings):
    from alembic import command
    from labadda.cli import alembic_config

    admin = as_user("admin")
    assert admin.post("/admin/policy-drafts", json=payload()).status_code == 201
    with pytest.raises(RuntimeError, match="Policy drafts exist"):
        command.downgrade(alembic_config(settings.database_url), "0005")
    assert admin.get("/admin/policy-drafts").json()["latest_revision"] == 1


@pytest.mark.parametrize("change", ["demote", "revoke"])
def test_queued_proposal_rechecks_authority(make_client, db_factory, monkeypatch, change):
    import threading
    from sqlalchemy import text
    from labadda.api import governance

    admin = make_client("admin")
    entered, resume = threading.Event(), threading.Event()
    original = governance.lock_drafts

    def wait(db):
        entered.set()
        assert resume.wait(5)
        original(db)

    monkeypatch.setattr(governance, "lock_drafts", wait)
    results = []
    worker = threading.Thread(
        target=lambda: results.append(admin.post("/admin/policy-drafts", json=payload()))
    )
    worker.start()
    try:
        assert entered.wait(5)
        with db_factory() as db:
            if change == "demote":
                db.execute(text("update users set is_admin=false where username='admin'"))
            else:
                db.execute(
                    text(
                        "update auth_sessions set revoked_at=now() where user_id=(select id from users where username='admin')"
                    )
                )
            db.commit()
    finally:
        resume.set()
        worker.join(10)
    assert not worker.is_alive()
    assert results[0].status_code == (403 if change == "demote" else 401)
    with db_factory() as db:
        assert db.scalar(text("select count(*) from policy_drafts")) == 0
