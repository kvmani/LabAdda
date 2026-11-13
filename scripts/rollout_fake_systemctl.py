#!/usr/bin/env python3
"""A stand-in for systemctl used ONLY by scripts/rehearse-rollout.sh on a machine without systemd.

It reads the real unit files the installer wrote under the rehearsal prefix and starts their
ExecStart as an ordinary background process, so install.sh, lifecycle.py and upgrade.sh can be
exercised end to end. Settings come from the JSON file named in FAKE_SYSTEMCTL_CONFIG, because
lifecycle.py runs systemctl with a cleared environment.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

CONFIG = Path(os.environ.get("FAKE_SYSTEMCTL_CONFIG", "/etc/labadda-fake-systemctl.json"))


def settings() -> dict:
    return json.loads(CONFIG.read_text())


def parse_unit(path: Path) -> dict:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.startswith("#"):
            values.setdefault(key, value)
    return values


def pid_file(cfg: dict, unit: str) -> Path:
    return Path(cfg["state"]) / f"{unit}.pid"


def main_pid(cfg: dict, unit: str) -> int:
    try:
        pid = int(pid_file(cfg, unit).read_text())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return 0


def start_nginx(cfg: dict, action: str) -> None:
    flags = ["-s", "reload"] if action == "reload" else []
    subprocess.run(["nginx", "-c", cfg["nginx_conf"], *flags], check=True)


def start(cfg: dict, unit: str) -> None:
    if unit in ("nginx", "nginx.service"):
        if not main_pid(cfg, "nginx"):
            start_nginx(cfg, "start")
            pid_file(cfg, "nginx").write_text(Path(cfg["nginx_pid"]).read_text().strip())
        return
    path = Path(cfg["unit_dir"]) / unit
    if not path.is_file() or not unit.endswith(".service") or main_pid(cfg, unit):
        return
    spec = parse_unit(path)
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    for line in Path(spec["EnvironmentFile"]).read_text().splitlines():
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key] = value
    command = ["/usr/sbin/runuser", "-u", spec["User"], "--", *shlex.split(spec["ExecStart"])]
    log = Path(cfg["state"]) / f"{unit}.log"
    with log.open("ab") as sink:
        process = subprocess.Popen(
            command, env=env, cwd=spec["WorkingDirectory"], stdout=sink, stderr=sink, start_new_session=True
        )
    pid_file(cfg, unit).write_text(str(process.pid))


def stop(cfg: dict, unit: str) -> None:
    pid = main_pid(cfg, unit)
    if not pid:
        return
    if unit.startswith("nginx"):
        subprocess.run(["nginx", "-c", cfg["nginx_conf"], "-s", "quit"], check=False)
    else:
        os.killpg(pid, signal.SIGTERM)
    for _ in range(100):
        if not main_pid(cfg, unit):
            break
        time.sleep(0.1)
    else:
        os.killpg(pid, signal.SIGKILL)
    pid_file(cfg, unit).unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    cfg = settings()
    words = [a for a in argv if not a.startswith("--")]
    command = words[0]
    units = ["nginx" if u.startswith("nginx") else u for u in words[1:]]
    if command == "is-active":
        if units[0].startswith("postgresql"):  # the host's own database, started outside this stand-in
            up = subprocess.run(["pg_isready", "-q"], check=False).returncode == 0
        else:
            up = bool(main_pid(cfg, units[0]))
        print("active" if up else "inactive")
        return 0 if up else 3
    if command == "show":
        unit = units[0]
        loaded = (Path(cfg["unit_dir"]) / unit).is_file()
        pid = main_pid(cfg, unit)
        print(f"LoadState={'loaded' if loaded else 'not-found'}")
        print(f"ActiveState={'active' if pid else 'inactive'}")
        print(f"MainPID={pid}")
        return 0
    for unit in units:
        if command in ("start", "restart", "reload") or (command == "enable" and "--now" in argv):
            if command in ("restart", "reload") and unit.startswith("nginx") and main_pid(cfg, "nginx"):
                start_nginx(cfg, "reload")
                continue
            if command == "restart":
                stop(cfg, unit)
            start(cfg, unit)
        elif command == "stop" or (command == "disable" and "--now" in argv):
            stop(cfg, unit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
