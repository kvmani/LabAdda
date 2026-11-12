"""Operator and developer commands: ``labadda <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import load_settings
from .db import session_factory

ROOT = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = url
    return cfg


def run_doctor(args: argparse.Namespace) -> int:
    """Run the read-only installation checks; exit 0 only when none failed."""
    from . import doctor

    environ = dict(os.environ)
    if args.env_file is not None:
        try:
            environ.update(doctor.read_env_file(args.env_file))
        except (OSError, ValueError):
            print("The environment file could not be read as LABADDA_ settings.", file=sys.stderr)
            return 2
    host = doctor.live_host(environ, port=args.port)
    results = doctor.run_checks(host)
    if args.json:
        print(json.dumps(doctor.as_report(results, host.now()), indent=2))
    else:
        print(doctor.format_report(results))
    return 0 if doctor.passed(results) else 1


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911, PLR0912, PLR0915 — one flat dispatch over every subcommand; splitting would hide the command table
    parser = argparse.ArgumentParser(prog="labadda")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply schema migrations to head")
    seed = sub.add_parser("seed", help="load the fictional fixture (development/test only)")
    seed.add_argument("--reset", action="store_true", help="erase all data first")
    serve = sub.add_parser("serve", help="run the ASGI server on loopback")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    admin = sub.add_parser(
        "create-admin", help="create an administrator and print a one-time activation token"
    )
    admin.add_argument("username")
    admin.add_argument("--display-name", default=None)
    sub.add_parser("reminders", help="process due reminders once")
    backup = sub.add_parser("backup", help="snapshot a writer-quiesced database and assets")
    backup.add_argument("destination", type=Path)
    backup.add_argument("--release", required=True)
    backup.add_argument("--writers-quiesced", action="store_true", required=True)
    doctor = sub.add_parser("doctor", help="check this installation; say in plain words how to fix problems")
    doctor.add_argument("--json", action="store_true", help="print the report as JSON")
    doctor.add_argument("--env-file", type=Path, help="read LABADDA_ settings from this file first")
    doctor.add_argument("--port", type=int, help="the port the service listens on, if not in the settings")
    verify = sub.add_parser("verify-backup", help="re-check a finished backup bundle against its manifest")
    verify.add_argument("bundle", type=Path)
    verify.add_argument("--manifest-sha256", required=True)
    restore = sub.add_parser("restore", help="restore to a distinct empty, isolated database")
    restore.add_argument("bundle", type=Path)
    restore.add_argument("--manifest-sha256", required=True)
    restore.add_argument("--isolated-target", action="store_true", required=True)
    inspect = sub.add_parser("inspect-storage", help="bounded read-only inspection of referenced asset bytes")
    inspect.add_argument("--max-files", type=int, default=10000)
    inspect.add_argument("--max-bytes", type=int, default=1024**3)
    inspect.add_argument("--max-seconds", type=float, default=30)
    inventory = sub.add_parser("inventory-storage", help="bounded metadata-only asset-directory inventory")
    inventory.add_argument("--max-entries", type=int, default=10000)
    inventory.add_argument("--max-assets", type=int, default=10000)
    inventory.add_argument("--max-seconds", type=float, default=30)
    queue_inventory = sub.add_parser("queue-inventory", help="queue an idempotent operator inventory job")
    queue_inventory.add_argument("--request-key", required=True)
    queue_inventory.add_argument("--max-entries", type=int, default=10000)
    queue_inventory.add_argument("--max-assets", type=int, default=10000)
    queue_inventory.add_argument("--max-seconds", type=int, default=30)
    run_inventory = sub.add_parser("run-inventory", help="run one queued inventory job with a durable lease")
    run_inventory.add_argument("job_id", type=uuid.UUID)
    run_inventory.add_argument(
        "--retry", action="store_true", help="explicitly retry an expired, partial, failed or paused job"
    )
    cancel_inventory = sub.add_parser(
        "cancel-inventory", help="cancel a queued or active inventory job at its next checkpoint"
    )
    cancel_inventory.add_argument("job_id", type=uuid.UUID)
    reconcile = sub.add_parser(
        "reconcile-previews", help="dry-run or explicitly apply verified historical preview metadata"
    )
    reconcile.add_argument("--max-assets", type=int, default=100)
    reconcile.add_argument("--max-bytes", type=int, default=100 * 1024**2)
    reconcile.add_argument("--max-seconds", type=float, default=30)
    reconcile.add_argument("--after-asset", type=uuid.UUID)
    reconcile.add_argument("--apply", action="store_true")
    reconcile.add_argument("--expected-plan")
    reconcile.add_argument("--writers-quiesced", action="store_true")
    charges = sub.add_parser(
        "reconcile-charges", help="dry-run or explicitly apply text/board logical-charge ledger corrections"
    )
    charges.add_argument("--max-items", type=int, default=10_000)
    charges.add_argument("--max-boards", type=int, default=50)
    charges.add_argument("--max-board-objects", type=int, default=200_000)
    charges.add_argument("--max-seconds", type=float, default=30)
    charges.add_argument("--after-item", help="cursor from a previous receipt, e.g. post:<id>")
    charges.add_argument("--after-board", type=uuid.UUID)
    charges.add_argument("--apply", action="store_true")
    charges.add_argument("--expected-plan")
    charges.add_argument("--writers-quiesced", action="store_true")
    show_inventory = sub.add_parser("show-inventory", help="show sanitized inventory job and attempt status")
    show_inventory.add_argument("job_id", type=uuid.UUID)
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return run_doctor(args)
    settings = load_settings()

    if args.cmd == "reconcile-charges":
        from .charge_reconciliation import reconcile_content_charges

        try:
            result = reconcile_content_charges(
                session_factory(settings.database_url),
                max_items=args.max_items,
                max_boards=args.max_boards,
                max_board_objects=args.max_board_objects,
                max_seconds=args.max_seconds,
                after_item=args.after_item,
                after_board=args.after_board,
                apply=args.apply,
                expected_plan=args.expected_plan,
                writers_quiesced=args.writers_quiesced,
            )
            print(json.dumps(result))
            clean = result["status"] == "completed" and (args.apply or result["summary"]["issue_count"] == 0)
            return 0 if clean else 2
        except Exception:
            print(
                "Charge reconciliation unconfirmed. Inspect its receipt; check budgets, stopped writers "
                "and the "
                "reviewed plan. Only ledger rows are ever corrected; no content is changed.",
                file=sys.stderr,
            )
            return 2

    if args.cmd == "reconcile-previews":
        from .preview_reconciliation import reconcile_previews

        try:
            result = reconcile_previews(
                session_factory(settings.database_url),
                settings.asset_dir,
                max_assets=args.max_assets,
                max_bytes=args.max_bytes,
                max_seconds=args.max_seconds,
                after_asset=args.after_asset,
                apply=args.apply,
                expected_plan=args.expected_plan,
                writers_quiesced=args.writers_quiesced,
            )
            print(json.dumps(result))
            return 0 if result["status"] == "completed" and result["summary"]["issue_count"] == 0 else 2
        except Exception:
            print(
                "Preview reconciliation unconfirmed. Inspect its receipt; check budgets, stopped writers "
                "and the reviewed plan. No files are rewritten or deleted.",
                file=sys.stderr,
            )
            return 2

    if args.cmd in {"queue-inventory", "run-inventory", "cancel-inventory", "show-inventory"}:
        from . import inventory_jobs

        try:
            factory = session_factory(settings.database_url)
            if args.cmd == "show-inventory":
                from .models import InventoryJob

                with factory() as db:
                    job = db.get(InventoryJob, args.job_id)
                    if job is None:
                        raise ValueError("Unknown inventory job")
                    print(json.dumps(inventory_jobs.describe(db, job)))
                return 0
            if args.cmd == "queue-inventory":
                job_id = inventory_jobs.enqueue(
                    factory,
                    args.request_key,
                    {
                        "max_entries": args.max_entries,
                        "max_assets": args.max_assets,
                        "max_seconds": args.max_seconds,
                    },
                )
                print(json.dumps({"job_id": str(job_id)}))
                return 0
            if args.cmd == "cancel-inventory":
                inventory_jobs.cancel(factory, args.job_id)
                print(json.dumps({"job_id": str(args.job_id), "state": "cancelled"}))
                return 0
            result = inventory_jobs.run(factory, settings.asset_dir, args.job_id, retry=args.retry)
            print(json.dumps(result))
            return 0 if result["summary"]["selected_pass_complete"] else 2
        except Exception:
            print(
                "Inventory job unconfirmed. Inspect its job and attempt records before retrying. "
                "No files are modified; expired attempts require explicit --retry.",
                file=sys.stderr,
            )
            return 2

    if args.cmd == "inventory-storage":
        from .inventory import inventory_storage

        try:
            result = inventory_storage(
                session_factory(settings.database_url),
                settings.asset_dir,
                max_entries=args.max_entries,
                max_assets=args.max_assets,
                max_seconds=args.max_seconds,
            )
            print(json.dumps(result))
            return 0 if result["summary"]["selected_pass_complete"] else 2
        except Exception:
            print(
                "Inventory unconfirmed. Check its receipt, budgets, asset root and database access. "
                "No files were changed or deleted.",
                file=sys.stderr,
            )
            return 2

    if args.cmd == "inspect-storage":
        from .inspection import inspect_storage

        try:
            result = inspect_storage(
                session_factory(settings.database_url),
                settings.asset_dir,
                max_files=args.max_files,
                max_bytes=args.max_bytes,
                max_seconds=args.max_seconds,
            )
            print(json.dumps(result))
            return 0 if result["status"] == "completed" and result["summary"]["issue_count"] == 0 else 2
        except Exception:
            print(
                "Inspection failed. Check budgets, asset root and database access; no files were repaired "
                "or removed.",
                file=sys.stderr,
            )
            return 2

    if args.cmd == "backup":
        from .recovery import backup as create_backup

        try:
            sha = create_backup(
                settings.database_url,
                settings.asset_dir,
                args.destination,
                args.release,
                writers_quiesced=args.writers_quiesced,
            )
            print(f"Recovery manifest SHA-256: {sha}")
            return 0
        except Exception:
            print(
                "Backup failed; no readiness claim. Check stopped writers, paths, database access and "
                "PostgreSQL clients.",
                file=sys.stderr,
            )
            return 2

    if args.cmd == "verify-backup":
        from .recovery import file_hash, verify_bundle

        try:
            manifest = verify_bundle(args.bundle)
            if file_hash(args.bundle / "manifest.json") != args.manifest_sha256:
                raise ValueError("Manifest digest differs from the recorded value")
            print(json.dumps({"verified": True, "schema": manifest["schema"]}))
            return 0
        except Exception:
            print("Backup verification failed; do not rely on this bundle.", file=sys.stderr)
            return 2

    if args.cmd == "restore":
        from .recovery import restore as restore_backup

        target_url = os.environ.get("LABADDA_RESTORE_DATABASE_URL")
        if not target_url:
            print("Set LABADDA_RESTORE_DATABASE_URL to a distinct empty target.", file=sys.stderr)
            return 2
        try:
            print(
                json.dumps(
                    restore_backup(
                        args.bundle,
                        args.manifest_sha256,
                        target_url,
                        settings.asset_dir,
                        isolated_target=args.isolated_target,
                    )
                )
            )
            return 0
        except Exception:
            print(
                "Restore failed. Keep target isolated; inspect integrity, empty target, clients and "
                "access. Never activate a partial restore.",
                file=sys.stderr,
            )
            return 2

    if args.cmd == "migrate":
        command.upgrade(alembic_config(settings.database_url), "head")
        return 0
    if args.cmd == "seed":
        if not settings.fixtures_allowed:
            print("Refusing to load fixtures: LABADDA_ENV must be development or test.", file=sys.stderr)
            return 2
        from .fixtures import reset_database
        from .fixtures import seed as run_seed

        with session_factory(settings.database_url)() as db:
            if args.reset:
                reset_database(db)
            print(json.dumps(run_seed(db), indent=2))
        return 0
    if args.cmd == "serve":
        import uvicorn

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        uvicorn.run(
            "labadda.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            proxy_headers=True,
            forwarded_allow_ips="127.0.0.1",
            ws_max_size=64 * 1024,
        )
        return 0
    if args.cmd == "create-admin":
        from sqlalchemy import select

        from . import audit, people
        from .credentials import issue_credential
        from .models import User

        with session_factory(settings.database_url)() as db:
            username = args.username.strip().lower()
            if db.scalar(select(User).where(User.username == username)):
                print("That username already exists.", file=sys.stderr)
                return 1
            user = User(username=username, display_name=args.display_name or username, is_admin=True)
            people.set_status(user, "invited", effective_on=people.site_date(settings))
            db.add(user)
            db.flush()
            token, cred = issue_credential(db, user, "activation", None, settings)
            audit.record(
                db,
                actor=None,
                action="identity.create",
                scope_type="identity",
                target_id=user.id,
                reason="Operator initial administrator setup",
                status_before=None,
                status_after=user.status,
                is_admin=True,
            )
            db.commit()
            print(f"Activation token for {username} (expires {cred.expires_at.isoformat()}):")
            print(token)
            print("Open <base>/activate and enter this token. Do not store it in logs.")
        return 0
    if args.cmd == "reminders":
        from .scheduler import process_due_reminders

        with session_factory(settings.database_url)() as db:
            print(f"created {process_due_reminders(db)} notifications")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
