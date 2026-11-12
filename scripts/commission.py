#!/usr/bin/env python3
"""Initialize an empty site or restore an isolated target; never start/open traffic."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import lifecycle
import operations
import release


def empty_database(target: Path, env: dict):
    code = """
from sqlalchemy import create_engine, text
from labadda.config import load_settings
engine = create_engine(load_settings().database_url, connect_args={'connect_timeout': 10})
with engine.connect() as db:
    count = db.execute(text(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE left(n.nspname, 3) <> 'pg_' AND n.nspname <> 'information_schema'"
    )).scalar_one()
    if count: raise SystemExit(1)
engine.dispose()
print('empty')
"""
    result = lifecycle.command([target / "venv/bin/python", "-I", "-c", code], env=env, cwd=target)
    if result != "empty":
        raise operations.OperationsError("Expected a separately provisioned empty database")


def prepare(  # noqa: PLR0912, PLR0915 — linear operator script; steps run in a fixed order
    site: dict,
    candidate: str,
    action: str,
    *,
    bundle: Path | None = None,
    manifest_sha256: str | None = None,
    apply=False,
    isolated_target=False,
) -> dict:
    if not release.RELEASE_ID.fullmatch(candidate):
        raise operations.OperationsError("Invalid installed release")
    if action not in ("initialize", "restore"):
        raise operations.OperationsError("Unknown commissioning action")
    root = Path(site["root"])
    target = root / "releases" / candidate
    release.validate_installed(target)
    env = lifecycle.runtime_environment(site)
    current = root / "current"
    assets = root / "assets"
    if current.exists() or current.is_symlink():
        raise operations.OperationsError(
            "Commissioning requires a new isolated instance without a current pointer"
        )
    if action == "restore":
        if (
            not bundle
            or not manifest_sha256
            or not re.fullmatch("[a-f0-9]{64}", manifest_sha256)
            or bundle.is_symlink()
            or not bundle.is_dir()
            or release.digest(bundle / "manifest.json") != manifest_sha256
        ):
            raise operations.OperationsError(
                "Provide an isolated recovery bundle and separately trusted manifest digest"
            )
        if assets.exists() or assets.is_symlink():
            raise operations.OperationsError("Restore asset destination must be absent")
    elif not assets.is_dir() or assets.is_symlink() or any(assets.iterdir()):
        raise operations.OperationsError("Initialization requires a provisioned empty assets directory")
    plan = {
        "format": 1,
        "action": action,
        "candidate": candidate,
        "applied": False,
        "traffic_opened": False,
        "sequence": [
            "verify isolated target",
            "lock",
            "maintenance on",
            "verify empty database",
            "migrate empty database"
            if action == "initialize"
            else "verified isolated database/assets restore",
            "verify schema",
            "leave traffic closed; operator ownership/service/functional qualification required",
        ],
    }
    if not apply:
        return plan
    if not isolated_target:
        raise operations.OperationsError("Explicit isolated-target attestation required")
    marker = root / "traffic/maintenance"
    with lifecycle.locked(root) as state:
        if current.exists() or current.is_symlink() or marker.exists() or marker.is_symlink():
            raise operations.OperationsError(
                "Target changed or already in maintenance; inspect previous operation"
            )
        operation = "commission-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex
        log = state / (operation + ".jsonl")
        log.touch(mode=0o600, exist_ok=False)
        lifecycle.journal(log, "started", action=action, candidate=candidate)
        with marker.open("x") as flag:
            flag.flush()
            os.fsync(flag.fileno())
        lifecycle.sync_directory(marker.parent)
        try:
            # The installed managed service must be stopped; external/unmanaged writers are an attestation.
            status = lifecycle.command(
                [
                    "systemctl",
                    "show",
                    f"labadda-{site['instance']}.service",
                    "--property=LoadState,ActiveState,MainPID",
                ]
            )
            properties = dict(line.split("=", 1) for line in status.splitlines() if "=" in line)
            if (
                properties.get("LoadState") != "loaded"
                or properties.get("MainPID") != "0"
                or properties.get("ActiveState") not in ("inactive", "failed")
            ):
                raise operations.OperationsError("Target service must be installed and stopped")
            empty_database(target, env)
            lifecycle.journal(log, "empty_target_verified")
            if action == "initialize":
                lifecycle.cli(target, env, "migrate")
            else:
                restore_env = {**env, "LABADDA_RESTORE_DATABASE_URL": env["LABADDA_DATABASE_URL"]}
                lifecycle.cli(
                    target,
                    restore_env,
                    "restore",
                    bundle,
                    "--manifest-sha256",
                    manifest_sha256,
                    "--isolated-target",
                )
            lifecycle.journal(log, "content_prepared")
            schema = lifecycle.schema(target, site, env)
            manifest = release.validate_installed(target)
            if schema != manifest["schema"]:
                raise operations.OperationsError("Restored/migrated schema does not match candidate")
            # Do not switch automatically: restored ownership must be checked before starting service.
            lifecycle.journal(log, "completed_isolated", schema=schema)
            return {**plan, "applied": True, "schema": schema, "journal": str(log), "maintenance": True}
        except BaseException:
            lifecycle.journal(
                log, "failed", next_action="Keep target isolated; inspect journal, database and assets"
            )
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("action", choices=("initialize", "restore"))
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--isolated-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = prepare(
            operations.load_site(args.site),
            args.candidate,
            args.action,
            bundle=args.bundle,
            manifest_sha256=args.manifest_sha256,
            apply=args.apply,
            isolated_target=args.isolated_target,
        )
        print(json.dumps(result, indent=2))
        return 0
    except (operations.OperationsError, release.ReleaseError, OSError, ValueError):
        print(
            "Commissioning unconfirmed. Keep target isolated; inspect its private journal and recovery "
            "runbook.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
