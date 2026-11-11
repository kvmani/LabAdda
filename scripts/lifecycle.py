#!/usr/bin/env python3
"""Fail-closed maintenance/backup/upgrade orchestration for installed sites.

Defaults to a read-only plan. Run from trusted operator-owned code. Never runs a
shell, provisions a database, rewinds a schema or restores traffic after an unsuccessful
operation. Backups are deleted only by the explicit, plan-first `prune-backups` action.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import backup_tools
import operations
import release
from site_environment import runtime_environment
from site_state import journal, locked, private_directory, sync_directory


def command(argv, *, env=None, cwd=None, timeout=120) -> str:
    """Suppress credential-bearing output; terminate the entire child group on deadline."""
    with subprocess.Popen(
        [str(a) for a in argv],
        env=env or {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as process:
        try:
            stdout, _ = process.communicate(timeout=timeout)
        except BaseException:  # noqa: BLE001 — kill the child on timeout or interrupt, then report it
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise operations.OperationsError(
                "Command interrupted/deadline exceeded; keep maintenance enabled"
            ) from None
        if process.returncode:
            raise operations.OperationsError(
                "Operational command failed; output suppressed; inspect service/database locally"
            )
    return stdout.strip()


class VerificationFailed(operations.OperationsError):
    """The finished backup bundle did not match its manifest."""


def current_release(root: Path) -> tuple[str, Path]:
    current = root / "current"
    if not current.is_symlink():
        raise operations.OperationsError(
            "Expected an active release symlink; initial deployment uses release.py"
        )
    target = current.resolve(strict=True)
    if target.parent != root.resolve() / "releases" or not release.RELEASE_ID.fullmatch(target.name):
        raise operations.OperationsError("Active release is outside the installed release directory")
    release.validate_installed(target)
    return target.name, target


def cli(target: Path, environment: dict, *args) -> str:
    return command(
        [target / "venv/bin/python", "-I", "-m", "labadda.cli", *args],
        env=environment,
        cwd=target / "backend",
        timeout=3600,
    )


def schema(target: Path, site: dict, env: dict) -> str:
    output = command(
        [
            sys.executable,
            "-I",
            str(Path(__file__).with_name("release.py")),
            "preflight",
            "--instance",
            site["root"],
            "--release",
            target.name,
        ],
        env=env,
    )
    match = re.fullmatch(r"Observed database schema: ([A-Za-z0-9_]+)", output)
    if not match:
        raise operations.OperationsError("Invalid schema preflight response")
    return match[1]


def wait_ready(site: dict, *, seconds=60, interval=1) -> bool:
    # Each probe has two 10-second endpoint deadlines. Total <= seconds + 20s.
    end = time.monotonic() + seconds
    while True:
        if operations.probe(site, direct=True)["passed"]:
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(min(interval, max(0, end - time.monotonic())))


def resume_traffic(site: dict, unit: str, marker: Path, log: Path):
    """Start the service, confirm direct readiness, lift maintenance, then confirm the TLS route."""
    command(["systemctl", "start", unit])
    if not wait_ready(site):
        raise operations.OperationsError("Direct readiness failed")
    journal(log, "direct_ready")
    marker.unlink()
    sync_directory(marker.parent)
    if not operations.probe(site)["passed"]:
        raise operations.OperationsError("TLS readiness failed")
    journal(log, "traffic_ready")


def maintenance(
    site: dict,
    action: str,
    expected: str,
    *,
    candidate: str | None = None,
    expected_schema: str | None = None,
    apply=False,
    external_writers_stopped=False,
    resume=False,
) -> dict:
    root = Path(site["root"])
    env = runtime_environment(site)
    active, target = current_release(root)
    if active != expected:
        raise operations.OperationsError("Active release changed; review a fresh plan")
    next_target = None
    if resume and action != "backup":
        raise operations.OperationsError("Only a backup can resume traffic on its own")
    if action == "upgrade":
        if not candidate or not release.RELEASE_ID.fullmatch(candidate) or candidate == active:
            raise operations.OperationsError("Upgrade requires a distinct installed candidate")
        next_target = root / "releases" / candidate
        release.validate_installed(next_target)
    plan = {
        "format": 1,
        "instance": site["instance"],
        "action": action,
        "current": active,
        "candidate": candidate,
        "expected_schema": expected_schema,
        "applied": False,
        "sequence": [
            "lock",
            "verify current and schema",
            "maintenance on",
            "stop service",
            "verify service stopped",
            "consistent verified backup",
        ]
        + (["verify backup bundle"] if action == "backup" else [])
        + (["migrate candidate", "verify schema", "switch code"] if action == "upgrade" else [])
        + (
            ["start service", "direct readiness", "maintenance off", "TLS readiness"]
            if action == "upgrade" or resume
            else ["leave service stopped and maintenance on; explicit resume required"]
        ),
    }
    if not apply:
        return plan
    if not external_writers_stopped:
        raise operations.OperationsError("Attest all external CLI/scheduler writers are stopped")
    unit = f"labadda-{site['instance']}.service"
    marker = root / "traffic/maintenance"
    with locked(root) as state:
        if current_release(root)[0] != active:
            raise operations.OperationsError("Active release changed while waiting for lock")
        if marker.exists() or marker.is_symlink():
            raise operations.OperationsError(
                "Maintenance already enabled; inspect previous journal before proceeding"
            )
        observed = schema(target, site, env)
        if not expected_schema or observed != expected_schema:
            raise operations.OperationsError("Observed schema differs from reviewed expectation")
        private_directory(Path(site["backup_root"]))
        operation = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex
        log = state / (operation + ".jsonl")
        log.touch(mode=0o600, exist_ok=False)
        backup = Path(site["backup_root"]) / operation
        journal(log, "started", action=action, current=active, candidate=candidate, schema=observed)
        # Marker publication is durable before stopping writers or touching durable data.
        with marker.open("x") as flag:
            flag.flush()
            os.fsync(flag.fileno())
        sync_directory(marker.parent)
        try:
            journal(log, "maintenance_enabled")
            command(["systemctl", "stop", unit])
            stopped = command(["systemctl", "show", unit, "--property=ActiveState,MainPID"])
            properties = dict(line.split("=", 1) for line in stopped.splitlines() if "=" in line)
            if properties.get("MainPID") != "0" or properties.get("ActiveState") not in (
                "inactive",
                "failed",
            ):
                raise operations.OperationsError("Service still active; no backup or migration attempted")
            journal(log, "writers_stopped")
            cli(target, env, "backup", backup, "--release", active, "--writers-quiesced")
            manifest_hash = release.digest(backup / "manifest.json")
            journal(log, "backup_verified", bundle=backup.name, manifest_sha256=manifest_hash)
            if action == "backup":
                verify_bundle(target, env, backup, manifest_hash)
                journal(log, "bundle_rechecked", bundle=backup.name)
            if action == "upgrade":
                journal(log, "migration_started")
                cli(next_target, env, "migrate")
                next_schema = schema(next_target, site, env)
                release.switch(root, candidate, next_schema)
                journal(log, "code_switched", release=candidate, schema=next_schema)
            if action == "upgrade" or resume:
                resume_traffic(site, unit, marker, log)
            journal(log, "completed")
            return {
                **plan,
                "applied": True,
                "journal": str(log),
                "backup": str(backup),
                "manifest_sha256": manifest_hash,
                "maintenance": action == "backup" and not resume,
            }
        except BaseException:
            # Never rewind the database or reopen traffic after an unconfirmed operation.
            marker.touch(exist_ok=True)
            sync_directory(marker.parent)
            journal(
                log,
                "failed",
                next_action="Keep maintenance; inspect last completed event and recovery runbook",
            )
            raise


def verify_bundle(target: Path, env: dict, bundle: Path, manifest_hash: str):
    """Re-read the published bundle through the release CLI and compare it with its manifest."""
    try:
        cli(target, env, "verify-backup", bundle, "--manifest-sha256", manifest_hash)
    except operations.OperationsError as error:
        raise VerificationFailed("Backup bundle failed its manifest check") from error


def scheduled_backup(site: dict, args, *, now=None) -> dict:
    """Run a backup and record its outcome, success or failure, in the status file."""
    root = Path(site["root"])
    env = runtime_environment(site)
    status_dir = backup_tools.status_directory(env.get("LABADDA_STATUS_DIR"))
    alias = backup_tools.destination_alias(args.destination_alias)
    try:
        expected, expected_schema = args.expected_current, args.expected_schema
        if args.unattended:
            expected, target = current_release(root)
            expected_schema = schema(target, site, env)
        result = maintenance(
            site,
            "backup",
            expected,
            expected_schema=expected_schema,
            apply=args.apply,
            external_writers_stopped=args.external_writers_stopped,
            resume=args.resume_after_backup,
        )
    except BaseException as error:
        if status_dir and args.apply:
            verification = "failed" if isinstance(error, VerificationFailed) else "not_run"
            # The original error is the one to report; a stale file is flagged by its age.
            with contextlib.suppress(OSError):
                backup_tools.record_outcome(status_dir, destination=alias, now=now, verification=verification)
        raise
    if not result["applied"]:
        return result
    if status_dir is None:
        return {**result, "status_file": "not configured"}
    try:
        backup_tools.record_outcome(
            status_dir,
            destination=alias,
            now=now,
            bundle=Path(result["backup"]),
            schema=expected_schema,
            release=expected,
            verification="passed",
        )
    except OSError:
        return {**result, "status_file": "write failed"}
    return {**result, "status_file": "written"}


def prune_backups(site: dict, keep: int, *, apply=False) -> dict:
    """Plan, and with apply carry out, count-based retention of finished local backups."""
    root, backup_root = Path(site["root"]), Path(site["backup_root"])
    if not backup_root.is_dir() or backup_root.is_symlink():
        raise operations.OperationsError("Backup directory does not exist")
    plan = backup_tools.retention_plan(backup_root, keep)
    if not apply or not plan["remove"]:
        return plan
    with locked(root) as state:
        private_directory(backup_root)
        # Re-plan under the lock: a backup may have finished while the first plan was read.
        plan = backup_tools.retention_plan(backup_root, keep)
        log = state / (
            time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-prune-" + uuid.uuid4().hex + ".jsonl"
        )
        log.touch(mode=0o600, exist_ok=False)
        journal(log, "prune_started", remove=plan["remove"], kept=plan["kept"])
        result = backup_tools.apply_retention(backup_root, plan)
        journal(log, "prune_completed")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("action", choices=("backup", "upgrade", "prune-backups"))
    parser.add_argument("--expected-current")
    parser.add_argument("--expected-schema")
    parser.add_argument("--candidate")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--external-writers-stopped", action="store_true")
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="backup only: take the expected release and schema from the installed site (timer use)",
    )
    parser.add_argument(
        "--resume-after-backup",
        action="store_true",
        help="backup only: after a verified backup restart the service and lift maintenance",
    )
    parser.add_argument(
        "--destination-alias", default="local", help="short name shown for the backup location"
    )
    parser.add_argument("--keep", type=int, help="prune-backups only: how many finished backups to keep")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.action == "prune-backups":
        if args.keep is None:
            parser.error("prune-backups requires --keep")
    elif args.action == "upgrade" and (args.unattended or args.resume_after_backup):
        parser.error("--unattended and --resume-after-backup apply to backup only")
    elif not args.unattended and not (args.expected_current and args.expected_schema):
        parser.error("--expected-current and --expected-schema are required unless --unattended")
    try:
        site = operations.load_site(args.site)
        if args.action == "prune-backups":
            result = prune_backups(site, args.keep, apply=args.apply)
        elif args.action == "backup":
            result = scheduled_backup(site, args)
        else:
            result = maintenance(
                site,
                "upgrade",
                args.expected_current,
                candidate=args.candidate,
                expected_schema=args.expected_schema,
                apply=args.apply,
                external_writers_stopped=args.external_writers_stopped,
            )
        print(json.dumps(result, indent=2))
        return 1 if result.get("status_file") == "write failed" else 0
    except (operations.OperationsError, release.ReleaseError, OSError, ValueError):
        # Never relay a runtime exception that could carry a credential-bearing URL.
        print(
            "Operation unconfirmed. Keep maintenance enabled; inspect the local journal and runbook.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
