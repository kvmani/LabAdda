#!/usr/bin/env python3
"""Fail when any pinned dependency version is younger than a minimum age (default 30 days).

Reads every pin in backend/requirements.lock (including transitive ones) and every package in
frontend/package-lock.json, then asks the package index when each exact version was released.
The index addresses are settings so the same check runs against the office mirror. A version whose
release date cannot be found counts as a failure: "unknown" is never treated as old enough.

    check_dependency_age.py [--min-age-days 30] [--pypi-url URL] [--npm-url URL] [--python-only|--npm-only]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)\s*(?:#.*)?$")
Fetch = Callable[[str, str], dict | None]


def python_pins(lock_text: str) -> list[tuple[str, str]]:
    pins = []
    for line in lock_text.splitlines():
        match = PIN.match(line.strip())
        if match:
            pins.append((match[1], match[2]))
    return sorted(set(pins))


def npm_pins(lock: dict) -> list[tuple[str, str]]:
    pins = set()
    for key, entry in lock.get("packages", {}).items():
        if "node_modules/" in key and entry.get("version") and not entry.get("link"):
            pins.add((key.rsplit("node_modules/", 1)[1], entry["version"]))
    return sorted(pins)


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def pypi_release_date(doc: dict, version: str) -> datetime | None:
    stamps = [f.get("upload_time_iso_8601") for f in doc.get("releases", {}).get(version, [])]
    stamps = [s for s in stamps if s]
    return min(_parse_time(s) for s in stamps) if stamps else None


def npm_release_date(doc: dict, version: str) -> datetime | None:
    stamp = doc.get("time", {}).get(version)
    return _parse_time(stamp) if stamp else None


def make_fetch(pypi_url: str, npm_url: str, timeout: float = 30) -> Fetch:
    def fetch(kind: str, name: str) -> dict | None:
        if kind == "pypi":
            url = f"{pypi_url.rstrip('/')}/pypi/{urllib.parse.quote(name)}/json"
        else:
            url = f"{npm_url.rstrip('/')}/{urllib.parse.quote(name, safe='@').replace('/', '%2F')}"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 — operator-set https URL
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return None
            except (OSError, ValueError):
                pass
            if attempt == 2:
                return None
        return None

    return fetch


def check(
    pins: dict[str, list[tuple[str, str]]], fetch: Fetch, *, now: datetime, min_days: int
) -> tuple[list[tuple], list[tuple]]:
    """Return (too_new, unknown); each item is (kind, name, version, released_or_None)."""
    dates = {"pypi": pypi_release_date, "npm": npm_release_date}
    names = {(kind, name) for kind, items in pins.items() for name, _ in items}
    with ThreadPoolExecutor(max_workers=16) as pool:
        docs = dict(zip(sorted(names), pool.map(lambda key: fetch(*key), sorted(names)), strict=True))
    cutoff = now - timedelta(days=min_days)
    too_new, unknown = [], []
    for kind, items in pins.items():
        for name, version in items:
            doc = docs[(kind, name)]
            released = dates[kind](doc, version) if doc else None
            if released is None:
                unknown.append((kind, name, version, None))
            elif released > cutoff:
                too_new.append((kind, name, version, released))
    return too_new, unknown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--min-age-days", type=int, default=30)
    parser.add_argument("--pypi-url", default="https://pypi.org")
    parser.add_argument("--npm-url", default="https://registry.npmjs.org")
    parser.add_argument("--root", type=Path, default=ROOT)
    only = parser.add_mutually_exclusive_group()
    only.add_argument("--python-only", action="store_true")
    only.add_argument("--npm-only", action="store_true")
    args = parser.parse_args(argv)
    pins: dict[str, list[tuple[str, str]]] = {}
    if not args.npm_only:
        pins["pypi"] = python_pins((args.root / "backend/requirements.lock").read_text())
    if not args.python_only:
        pins["npm"] = npm_pins(json.loads((args.root / "frontend/package-lock.json").read_text()))
    now = datetime.now(UTC)
    too_new, unknown = check(
        pins, make_fetch(args.pypi_url, args.npm_url), now=now, min_days=args.min_age_days
    )
    total = sum(len(v) for v in pins.values())
    for kind, name, version, released in too_new:
        print(
            f"TOO NEW  {kind:4} {name}=={version}  released {released:%Y-%m-%d} ({(now - released).days} days)"
        )
    for kind, name, version, _ in unknown:
        print(f"UNKNOWN  {kind:4} {name}=={version}  release date not found in the index")
    print(
        f"dependency age: {total} pins checked, minimum {args.min_age_days} days; "
        f"{len(too_new)} too new, {len(unknown)} unknown"
    )
    return 1 if too_new or unknown else 0


if __name__ == "__main__":
    raise SystemExit(main())
