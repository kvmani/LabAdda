"""Which software this is: version, commit and date, the same in the app, doctor and settings page."""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path

from . import __version__

BUILD_FILE = Path(__file__).with_name("build_info.json")
REPOSITORY = Path(__file__).resolve().parents[2]
COMMIT = re.compile(r"[0-9a-f]{7,40}\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
CREDIT = "Software conceived and developed by Dr. K. V. Mani Krishna, Materials Group."


def version_label(version: str = __version__) -> str:
    """'0.0.1-beta' is shown to people as '0.0.1 beta'."""
    return version.replace("-", " ")


def _git(*args: str) -> str:
    try:
        done = subprocess.run(  # noqa: S603 — fixed git subcommands, no user input; runs once, cached
            ["git", *args],  # noqa: S607 — git is looked up on PATH like every developer tool
            cwd=REPOSITORY,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _from_bundle() -> tuple[str, str]:
    try:
        data = json.loads(BUILD_FILE.read_text())
    except (OSError, ValueError):
        return "", ""
    return str(data.get("commit", "")), str(data.get("date", ""))


@functools.cache
def commit_and_date() -> tuple[str, str]:
    """The release bundle's stamp when present, else the checkout's git, else unknown ('', '')."""
    commit, date = _from_bundle()
    if not commit:
        commit, date = _git("rev-parse", "--short=7", "HEAD"), _git("log", "-1", "--format=%cs")
    if not COMMIT.match(commit):
        return "", ""
    return commit[:7], date if DATE.match(date) else ""


def build_info() -> dict:
    commit, date = commit_and_date()
    return {
        "version": __version__,
        "version_label": version_label(),
        "commit": commit or None,
        "date": date or None,
        "summary": summary_line(commit, date),
    }


def summary_line(commit: str, date: str) -> str:
    parts = [f"Version {version_label()}", f"commit {commit}" if commit else "commit unknown"]
    if date:
        parts.append(date)
    return " · ".join(parts)
