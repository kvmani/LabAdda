#!/usr/bin/env python3
"""Fail-closed maintenance/backup/upgrade orchestration for installed sites.

Defaults to a read-only plan. Run from trusted operator-owned code. Never runs a
shell, provisions a database, rewinds a schema, deletes backups or restores traffic
after an unsuccessful operation.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import operations
import release

TLS_ENV = {"PGSSLMODE", "PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY"}

ALLOWED_ENV = {
    "PORT",
    "FRONTEND_DIST",
    "TRUSTED_ORIGINS",
    "DATABASE_URL",
    "BASE_PATH",
    "INSTANCE",
    "ENV",
    "COOKIE_NAME",
    "COOKIE_SECURE",
    "ASSET_DIR",
    "TIMEZONE",
    "SESSION_IDLE_MINUTES",
    "SESSION_ABSOLUTE_HOURS",
    "MAX_ATTACHMENTS",
    "MAX_ATTACHMENT_BYTES",
    "USER_QUOTA_BYTES",
    "RUN_SCHEDULER",
    "REMINDER_INTERVAL_SECONDS",
    "MAX_GROUPS_PER_USER",
    "MAX_GROUP_MEMBERS",
    "LOGIN_ATTEMPTS_PER_WINDOW",
    "LOGIN_WINDOW_SECONDS",
    "BOARD_COMPACT_THRESHOLD",
    "PANEL_IDLE_SECONDS",
    "PANEL_ABSOLUTE_MINUTES",
    "PANEL_PAIRING_SECONDS",
    "BOARD_KEEP_REVISIONS",
}


def runtime_environment(site: dict) -> dict:
    path = Path(site["env_file"])
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid not in (0, os.geteuid()):
        raise operations.OperationsError(
            "Environment file must be operator-owned regular mode0600 or stricter"
        )
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if (
            not sep
            or (key not in TLS_ENV and (not key.startswith("LABADDA_") or key[8:] not in ALLOWED_ENV))
            or key in values
            or any(c.isspace() or c in "'\"\\" or ord(c) < 32 for c in value)
        ):
            raise operations.OperationsError(
                "Environment requires unique allowlisted unquoted KEY=value lines"
            )
        values[key] = value
    required = {
        "LABADDA_INSTANCE": site["instance"],
        "LABADDA_PORT": str(site["port"]),
        "LABADDA_BASE_PATH": site["base_path"],
        "LABADDA_ASSET_DIR": site["root"] + "/assets",
        "LABADDA_FRONTEND_DIST": site["root"] + "/current/frontend/dist",
        "LABADDA_COOKIE_SECURE": "true",
        "LABADDA_TRUSTED_ORIGINS": "https://" + site["server_name"],
    }
    # The generated unit passes the port explicitly; the environment need not repeat it.
    if "LABADDA_PORT" not in values:
        required.pop("LABADDA_PORT")
    if (
        any(values.get(k) != v for k, v in required.items())
        or values.get("LABADDA_ENV") not in ("staging", "pilot")
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", values.get("LABADDA_COOKIE_NAME", ""))
        or values.get("LABADDA_COOKIE_NAME") == "labadda_session"
        or not values.get("LABADDA_DATABASE_URL", "").startswith("postgresql+psycopg://")
    ):
        raise operations.OperationsError(
            "Runtime environment does not match the reviewed site/TLS/storage contract"
        )
    if any(key in values for key in TLS_ENV):
        if values.get("PGSSLMODE") != "verify-full" or not values.get("PGSSLROOTCERT", "").startswith("/"):
            raise operations.OperationsError("PostgreSQL TLS requires verify-full and an explicit CA file")
        for key in TLS_ENV - {"PGSSLMODE"}:
            if key in values and not Path(values[key]).is_absolute():
                raise operations.OperationsError("PostgreSQL TLS files require absolute paths")
        if ("PGSSLCERT" in values) != ("PGSSLKEY" in values):
            raise operations.OperationsError(
                "PostgreSQL client certificate and key must be configured together"
            )
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", **values}


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


def sync_directory(path: Path):
    fd = os.open(path, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_directory(path: Path):
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
        raise operations.OperationsError(
            "Operator state/backup directory must be private and owned by this operator"
        )


@contextmanager
def locked(root: Path):
    state = root / "operations"
    private_directory(state)
    fd = os.open(state / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise operations.OperationsError("Another site operation is running") from None
        yield state
    finally:
        os.close(fd)


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


def journal(path: Path, event: str, **fields):
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps({"at": time.time(), "event": event, **fields}, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())
    sync_directory(path.parent)


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


def maintenance(
    site: dict,
    action: str,
    expected: str,
    *,
    candidate: str | None = None,
    expected_schema: str | None = None,
    apply=False,
    external_writers_stopped=False,
) -> dict:
    root = Path(site["root"])
    env = runtime_environment(site)
    active, target = current_release(root)
    if active != expected:
        raise operations.OperationsError("Active release changed; review a fresh plan")
    next_target = None
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
        + (
            [
                "migrate candidate",
                "verify schema",
                "switch code",
                "start service",
                "direct readiness",
                "maintenance off",
                "TLS readiness",
            ]
            if action == "upgrade"
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
            if action == "upgrade":
                journal(log, "migration_started")
                cli(next_target, env, "migrate")
                next_schema = schema(next_target, site, env)
                release.switch(root, candidate, next_schema)
                journal(log, "code_switched", release=candidate, schema=next_schema)
                command(["systemctl", "start", unit])
                if not wait_ready(site):
                    raise operations.OperationsError("Direct readiness failed")
                journal(log, "direct_ready")
                marker.unlink()
                sync_directory(marker.parent)
                if not operations.probe(site)["passed"]:
                    raise operations.OperationsError("TLS readiness failed")
                journal(log, "traffic_ready")
            journal(log, "completed")
            return {
                **plan,
                "applied": True,
                "journal": str(log),
                "backup": str(backup),
                "manifest_sha256": manifest_hash,
                "maintenance": action == "backup",
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("action", choices=("backup", "upgrade"))
    parser.add_argument("--expected-current", required=True)
    parser.add_argument("--expected-schema", required=True)
    parser.add_argument("--candidate")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--external-writers-stopped", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = maintenance(
            operations.load_site(args.site),
            args.action,
            args.expected_current,
            candidate=args.candidate,
            expected_schema=args.expected_schema,
            apply=args.apply,
            external_writers_stopped=args.external_writers_stopped,
        )
        print(json.dumps(result, indent=2))
        return 0
    except (operations.OperationsError, release.ReleaseError, OSError, ValueError):
        # Never relay a runtime exception that could carry a credential-bearing URL.
        print(
            "Operation unconfirmed. Keep maintenance enabled; inspect the local journal and runbook.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
