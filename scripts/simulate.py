#!/usr/bin/env python3
"""Dedicated synthetic collaboration regression system; owns disposable local stack only.

No remote URL or custom database is accepted. Default is a read-only plan. Each
browser suite receives freshly seeded root/prefix databases. Workload uses TLS.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "quick": ("chat-attachments", "alert-preferences"),
    "full": (
        "admin-console",
        "flows",
        "todos",
        "task-assignment",
        "task-comments",
        "task-updates",
        "task-conversion",
        "task-board-reference",
        "chat-threads",
        "chat-attachments",
        "dashboard",
        "alert-preferences",
    ),
}


class SimulationError(Exception):
    pass


def run(argv, env, log: Path, timeout: float):
    with (
        log.open("ab") as output,
        subprocess.Popen(
            [str(a) for a in argv],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ) as process,
    ):
        try:
            result = process.wait(timeout=timeout)
        except BaseException:  # noqa: BLE001 — kill the child on timeout or interrupt, then report it
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise SimulationError("Stage interrupted or timed out") from None
        if result:
            raise SimulationError(f"Stage exited {result}; inspect its private synthetic log")


def save(path: Path, report: dict):
    temporary = path.with_suffix(".next")
    with temporary.open("w") as target:
        json.dump(report, target, indent=2, allow_nan=False)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def environment(out: Path, *, tls=False) -> dict:
    # Connection settings and all LabAdda selectors are controlled by this runner.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("LABADDA_", "PG")) and k not in ("DATABASE_URL",)
    }
    env.update(
        LABADDA_RUN_DIR=str(ROOT / "var/simulation-stack"),
        LABADDA_PROXY_PORT="8080",
        LABADDA_PROXY_TLS="1" if tls else "0",
        LABADDA_PYTHON=str(ROOT / ".venv/bin"),
        LABADDA_PG="postgresql+psycopg://labadda:labadda-dev@localhost:5432",
        LABADDA_LOGIN_ATTEMPTS_PER_WINDOW="200" if tls else "10",
        LABADDA_E2E_SHOTS=str(out),
        LABADDA_CHROMIUM=os.environ.get("LABADDA_CHROMIUM", "/usr/bin/chromium"),
        LABADDA_FIXTURE_PASSWORD="fixture-pass-123",  # noqa: S106 — documented development fixture password
    )
    return env


def stopped(env: dict) -> bool:
    """Confirm owned listeners closed and recorded app PIDs absent or reaped zombies."""
    for port in (8001, 8002, 8080):
        with socket.socket() as connection:
            connection.settimeout(0.2)
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                return False
    for instance in ("root", "staging"):
        pid_file = Path(env["LABADDA_RUN_DIR"]) / instance / "pid"
        if not pid_file.exists():
            continue
        try:
            pid = int(pid_file.read_text().strip())
            if pid <= 1:
                return False
            status = Path(f"/proc/{pid}/status")
            if status.exists() and not any(
                line.startswith("State:") and "Z" in line for line in status.read_text().splitlines()
            ):
                return False
        except (ValueError, OSError):
            return False
    return True


def confirm_stop(env: dict):
    end = time.monotonic() + 10
    while not stopped(env):
        if time.monotonic() >= end:
            raise SimulationError("Disposable listener/process shutdown unconfirmed")
        time.sleep(0.2)


def interrupted(signum, frame):
    raise KeyboardInterrupt("Simulation termination requested")


def execute(profile: str, out: Path) -> dict:
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {
        "format": 1,
        "profile": profile,
        "passed": False,
        "stages": [],
        "cleanup_passed": False,
        "started_at": time.time(),
        "scope": "synthetic local root/prefix only; no site/device acceptance",
    }
    report_path = out / "report.json"
    save(report_path, report)
    env = environment(out)
    stack = ROOT / "scripts/proxy-stack.sh"

    def stage(name, command, stage_env, timeout):
        entry = {"name": name, "passed": False, "started_at": time.time()}
        report["stages"].append(entry)
        save(report_path, report)
        try:
            run(command, stage_env, out / (name + ".log"), timeout)
            entry["passed"] = True
        finally:
            entry["elapsed_seconds"] = round(time.time() - entry["started_at"], 2)
            save(report_path, report)

    try:
        for suite in PROFILES[profile]:
            stage(suite + "-fixtures", [stack, "start"], env, 180)
            command = ["node", ROOT / "e2e" / (suite + ".mjs")]
            if suite == "flows":
                command += ["http://127.0.0.1:8080", "", "/labadda-staging"]
            else:
                command += [out / suite]
            stage(suite, command, env, 600)
            stage(suite + "-stop", [stack, "stop"], env, 30)
        env = environment(out, tls=True)
        stage("workload-fixtures", [stack, "start"], env, 180)
        clients, drawers, seconds = (5, 2, 20) if profile == "quick" else (30, 8, 90)
        for name, base in (("root", ""), ("prefix", "/labadda-staging")):
            stage(
                "workload-" + name,
                [
                    ROOT / ".venv/bin/python",
                    ROOT / "scripts/rehearsal.py",
                    "--synthetic-target",
                    "--origin",
                    "https://127.0.0.1:8080",
                    "--base",
                    base,
                    "--cafile",
                    ROOT / "var/simulation-stack/tls/ca.crt",
                    "--clients",
                    clients,
                    "--drawers",
                    drawers,
                    "--seconds",
                    seconds,
                    "--enforce-targets",
                    "--out",
                    out / ("workload-" + name + ".json"),
                ],
                env,
                600,
            )
    except (SimulationError, OSError, KeyboardInterrupt):
        report["failure"] = "Stage failed or interrupted; inspect last stage log. Fresh rerun required."
    finally:
        try:
            run([stack, "stop"], env, out / "cleanup.log", 30)
            confirm_stop(env)
            report["cleanup_passed"] = True
        except (SimulationError, OSError, KeyboardInterrupt):
            report["failure"] = "Cleanup unconfirmed; inspect disposable stack before rerunning."
        report["finished_at"] = time.time()
        report["passed"] = (
            "failure" not in report
            and bool(report["stages"])
            and all(s["passed"] for s in report["stages"])
            and report["cleanup_passed"]
        )
        save(report_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="quick")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--apply-disposable",
        action="store_true",
        help="Reset only labadda_e2e_root/labadda_e2e_prefix and own ports8001/8002/8080",
    )
    args = parser.parse_args(argv)
    if not args.apply_disposable:
        print(
            json.dumps(
                {
                    "profile": args.profile,
                    "browser_suites": PROFILES[args.profile],
                    "workloads": ["TLS root", "TLS prefix"],
                    "applied": False,
                },
                indent=2,
            )
        )
        return 0
    if os.environ.get("LABADDA_ENV") in ("staging", "pilot"):
        parser.error("Run simulation from a development/test environment, never a site service environment")
    (ROOT / "var").mkdir(exist_ok=True)
    with (ROOT / "var/simulation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another simulation owns the disposable stack")
        previous_handler = signal.signal(signal.SIGTERM, interrupted)
        try:
            report = execute(args.profile, args.out.absolute())
        except OSError:
            print("Cannot create exclusive output directory; choose a new private path.", file=sys.stderr)
            return 1
        finally:
            signal.signal(signal.SIGTERM, previous_handler)
    print(json.dumps({"passed": report["passed"], "report": str(args.out / "report.json")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
