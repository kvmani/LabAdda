"""T26 durable inventory leases and recovery; synthetic observation jobs only."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from alembic import command
from labadda import inventory_jobs as jobs
from labadda.cli import alembic_config
from labadda.models import InventoryAttempt, InventoryJob, StorageInspection
from labadda.security import utcnow
from sqlalchemy import select, text


def expire(factory, job_id):
    with factory() as db:
        db.get(InventoryJob, job_id).lease_until = utcnow() - timedelta(seconds=1)
        db.commit()


def test_idempotent_queue_and_parameter_binding(db_factory, ids):
    job_id = jobs.enqueue(db_factory, "inventory-key", {})
    assert jobs.enqueue(db_factory, "inventory-key", {"max_entries": 10000}) == job_id
    with pytest.raises(jobs.JobConflict):
        jobs.enqueue(db_factory, "inventory-key", {"max_entries": 1})
    with db_factory() as db:
        assert len(list(db.scalars(select(InventoryJob)))) == 1


@pytest.mark.parametrize(
    "parameters",
    [{"path": "/etc"}, {"max_entries": True}, {"max_seconds": float("nan")}, {"max_assets": 100001}],
)
def test_invalid_job_parameters(db_factory, ids, parameters):
    with pytest.raises(ValueError):
        jobs.enqueue(db_factory, "inventory-key", parameters)


def test_parallel_queue_and_claim_are_single_owner(db_factory, ids):
    with ThreadPoolExecutor(max_workers=4) as pool:
        created = list(pool.map(lambda _: jobs.enqueue(db_factory, "same-key-123", {}), range(4)))
    assert len(set(created)) == 1

    def claim():
        try:
            return jobs.claim(db_factory, created[0])[0]
        except jobs.JobConflict:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        claimed = list(pool.map(lambda _: claim(), range(4)))
    assert claimed.count(1) == 1 and claimed.count(None) == 3


def test_expired_attempt_cannot_heartbeat_or_finish(db_factory, settings, ids):
    job_id = jobs.enqueue(db_factory, "expired-key", {})
    number, _ = jobs.claim(db_factory, job_id)
    expire(db_factory, job_id)
    with pytest.raises(jobs.JobConflict):
        jobs.heartbeat(db_factory, job_id, number)
    with pytest.raises(jobs.JobConflict):
        jobs.claim(db_factory, job_id)
    second, _ = jobs.claim(db_factory, job_id, retry=True)
    assert second == 2
    with pytest.raises(jobs.JobConflict):
        jobs.finish(db_factory, job_id, number, {})
    with db_factory() as db:
        assert db.get(InventoryAttempt, (job_id, 1)).state == "expired"


def test_successful_job_and_terminal_replay(db_factory, settings, ids):
    settings.asset_dir.mkdir()
    job_id = jobs.enqueue(db_factory, "complete-key", {})
    result = jobs.run(db_factory, settings.asset_dir, job_id)
    with db_factory() as db:
        assert db.get(InventoryJob, job_id).state == "completed"
        attempt = db.get(InventoryAttempt, (job_id, 1))
        assert str(attempt.receipt_id) == result["id"]
        assert attempt.finished_at is not None
    with pytest.raises(jobs.JobConflict):
        jobs.run(db_factory, settings.asset_dir, job_id, retry=True)


def test_cancellation_fences_active_worker_and_is_idempotent(db_factory, ids):
    job_id = jobs.enqueue(db_factory, "cancel-key", {})
    number, _ = jobs.claim(db_factory, job_id)
    jobs.cancel(db_factory, job_id)
    jobs.cancel(db_factory, job_id)
    with pytest.raises(jobs.JobConflict):
        jobs.heartbeat(db_factory, job_id, number)
    with pytest.raises(jobs.JobConflict):
        jobs.finish(db_factory, job_id, number, {})
    with pytest.raises(jobs.JobConflict):
        jobs.claim(db_factory, job_id, retry=True)
    with db_factory() as db:
        assert db.get(InventoryAttempt, (job_id, 1)).state == "cancelled"


def test_scan_checkpoint_observes_cancellation(db_factory, settings, ids, monkeypatch):
    settings.asset_dir.mkdir()
    job_id = jobs.enqueue(db_factory, "checkpoint-key", {})
    heartbeat = jobs.heartbeat

    def cancel_before_check(factory, ident, number):
        jobs.cancel(factory, ident)
        heartbeat(factory, ident, number)

    monkeypatch.setattr(jobs, "heartbeat", cancel_before_check)
    with pytest.raises(jobs.JobConflict):
        jobs.run(db_factory, settings.asset_dir, job_id)
    with db_factory() as db:
        assert db.get(InventoryJob, job_id).state == "cancelled"
        receipt = db.scalar(select(StorageInspection))
        assert receipt.status == "failed"  # diagnostic receipt is not an accepted job result
        assert db.get(InventoryAttempt, (job_id, 1)).receipt_id is None


def test_retry_preserves_failed_attempt(db_factory, settings, ids):
    job_id = jobs.enqueue(db_factory, "failed-key", {})
    assert jobs.run(db_factory, settings.asset_dir, job_id)["status"] == "failed"
    settings.asset_dir.mkdir()
    jobs.run(db_factory, settings.asset_dir, job_id, retry=True)
    with db_factory() as db:
        assert db.get(InventoryAttempt, (job_id, 1)).state == "failed"
        assert db.get(InventoryAttempt, (job_id, 2)).state == "completed"


def test_recovery_pauses_work_and_rejects_copied_leases(db_factory, ids):
    queued = jobs.enqueue(db_factory, "queued-key", {})
    running = jobs.enqueue(db_factory, "running-key", {})
    number, _ = jobs.claim(db_factory, running)
    with db_factory() as db:
        jobs.pause_restored_jobs(db)
        db.commit()
    with pytest.raises(jobs.JobConflict):
        jobs.heartbeat(db_factory, running, number)
    with db_factory() as db:
        assert db.get(InventoryJob, queued).state == "paused"
        assert db.get(InventoryAttempt, (running, 1)).state == "paused"
    assert jobs.claim(db_factory, running, retry=True)[0] == 2


def test_audit_failure_rolls_back_claim(db_factory, ids, monkeypatch):
    job_id = jobs.enqueue(db_factory, "audit-key", {})

    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic audit unavailable")

    monkeypatch.setattr(jobs.audit, "record", unavailable)
    with pytest.raises(RuntimeError):
        jobs.claim(db_factory, job_id)
    with db_factory() as db:
        assert db.get(InventoryJob, job_id).state == "queued"
        assert db.get(InventoryAttempt, (job_id, 1)) is None


def test_wrong_receipt_cannot_complete_attempt(db_factory, settings, ids):
    from labadda.inventory import inventory_storage

    settings.asset_dir.mkdir()
    job_id = jobs.enqueue(db_factory, "receipt-key", {})
    number, _ = jobs.claim(db_factory, job_id)
    unrelated = inventory_storage(db_factory, settings.asset_dir)
    with pytest.raises(jobs.JobConflict):
        jobs.finish(db_factory, job_id, number, unrelated)


def test_migration_refuses_to_drop_job_history(db_factory, settings, ids):
    jobs.enqueue(db_factory, "migration-key", {})
    with pytest.raises(RuntimeError, match="Inventory jobs exist"):
        command.downgrade(alembic_config(settings.database_url), "0015")
    with db_factory() as db:
        from labadda.app import expected_schema_head

        assert db.scalar(text("select version_num from alembic_version")) == expected_schema_head()


def test_operator_cli_queue_run_and_replay(settings, db_factory, ids, monkeypatch, capsys):
    from labadda import cli

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    settings.asset_dir.mkdir()
    assert cli.main(["queue-inventory", "--request-key", "cli-test-key"]) == 0
    job_id = json.loads(capsys.readouterr().out)["job_id"]
    assert cli.main(["run-inventory", job_id]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    assert cli.main(["run-inventory", job_id]) == 2


def test_lost_completion_reply_is_resolved_from_durable_history(db_factory, settings, ids, monkeypatch):
    from sqlalchemy.orm import Session

    settings.asset_dir.mkdir()
    job_id = jobs.enqueue(db_factory, "lost-reply-key", {})
    commit = Session.commit
    lost = False

    def lose_reply(db):
        nonlocal lost
        completing = any(
            isinstance(row, InventoryJob) and row.state == "completed" for row in db.identity_map.values()
        )
        commit(db)
        if completing and not lost:
            lost = True
            raise OSError("synthetic lost commit reply")

    monkeypatch.setattr(Session, "commit", lose_reply)
    with pytest.raises(OSError):
        jobs.run(db_factory, settings.asset_dir, job_id)
    with db_factory() as db:
        detail = jobs.describe(db, db.get(InventoryJob, job_id))
        assert detail["state"] == "completed"
        assert detail["attempts"][0]["receipt_id"] is not None
    with pytest.raises(jobs.JobConflict):
        jobs.run(db_factory, settings.asset_dir, job_id, retry=True)


def test_completion_audit_failure_preserves_unaccepted_receipt(db_factory, settings, ids, monkeypatch):
    settings.asset_dir.mkdir()
    job_id = jobs.enqueue(db_factory, "finish-audit-key", {})
    event = jobs._event

    def fail_finish(db, job, action):
        if action == "finish":
            raise RuntimeError("synthetic audit unavailable")
        event(db, job, action)

    monkeypatch.setattr(jobs, "_event", fail_finish)
    with pytest.raises(RuntimeError):
        jobs.run(db_factory, settings.asset_dir, job_id)
    with db_factory() as db:
        assert db.get(InventoryJob, job_id).state == "running"
        assert db.get(InventoryAttempt, (job_id, 1)).receipt_id is None
        assert db.scalar(select(StorageInspection)).status == "completed"
