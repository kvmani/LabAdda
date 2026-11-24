#!/usr/bin/env python3
"""Fail when the built frontend's first-load or console code grows past its budget (UX-12).

Sizes are gzipped bytes, as the browser receives them over the office network. The first-load
chunk is what every person downloads before the first screen; the console chunk only
administrators download. Raise a budget deliberately, in the same commit as the reason.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "dist" / "assets"
# Gzipped kilobytes. Measured 2026-11-24: first load 96, console 68.
BUDGETS_KB = {"index": 110, "Admin": 80}


def gzipped(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9))


def largest(prefix: str) -> tuple[Path, int] | None:
    found = [(path, gzipped(path)) for path in ASSETS.glob(f"{prefix}-*.js")]
    return max(found, key=lambda item: item[1]) if found else None


def main() -> int:
    if not ASSETS.is_dir():
        print(f"check_bundle: no build at {ASSETS}; run npm run build first", file=sys.stderr)
        return 2
    problems = []
    for prefix, budget in BUDGETS_KB.items():
        chunk = largest(prefix)
        if chunk is None:
            problems.append(f"{prefix}: no chunk found")
            continue
        size_kb = chunk[1] / 1024
        print(f"check_bundle: {chunk[0].name} {size_kb:.1f} KB gzipped (budget {budget} KB)")
        if size_kb > budget:
            problems.append(f"{prefix}: {size_kb:.1f} KB is over its {budget} KB budget")
    for problem in problems:
        print("check_bundle: " + problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
