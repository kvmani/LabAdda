#!/usr/bin/env python3
"""Connected build-time audit of exact Python pins and production npm dependencies.

No application content is read or transmitted. Unknown/failed advisory checks fail closed.
Run before packaging; keep its JSON report with the candidate's transfer record.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from check_dependency_age import python_pins

ROOT = Path(__file__).resolve().parents[1]


def python_advisories(pin: tuple[str, str]) -> dict:
    """Return active published advisories for this exact version, or an explicit unknown."""
    name, version = pin
    address = f"https://pypi.org/pypi/{urllib.parse.quote(name)}/{urllib.parse.quote(version)}/json"
    result = {"name": name, "version": version, "state": "checked", "advisories": []}
    try:
        with urllib.request.urlopen(address, timeout=30) as response:
            metadata = json.load(response)
        result["advisories"] = [
            {"id": row["id"], "aliases": row.get("aliases", []), "fixed_in": row.get("fixed_in", [])}
            for row in metadata["vulnerabilities"]
            if not row.get("withdrawn")
        ]
    except (OSError, ValueError, KeyError):
        result["state"] = "unknown"
    return result


def audit(root: Path) -> dict:
    """Audit all Python lock entries and only frontend production dependencies."""
    pins = python_pins((root / "backend/requirements.lock").read_text())
    with ThreadPoolExecutor(max_workers=8) as pool:
        python = list(pool.map(python_advisories, pins))
    command = subprocess.run(
        ["npm", "audit", "--omit=dev", "--json"],
        cwd=root / "frontend",
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        npm = json.loads(command.stdout)
        totals = npm["metadata"]["vulnerabilities"]
        npm_ok = command.returncode == 0 and totals["total"] == 0
    except (ValueError, KeyError):
        npm, npm_ok = {"state": "unknown"}, False
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "sources": ["PyPI published version advisories", "npm production dependency audit"],
        "python": python,
        "npm": npm,
        "passed": npm_ok and all(row["state"] == "checked" and not row["advisories"] for row in python),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = audit(args.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
