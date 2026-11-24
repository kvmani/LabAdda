#!/usr/bin/env python3
"""Fail when a hand-written source file grows past 400 lines (Q4).

Files that were already longer when this check arrived are listed in ``RATCHET`` with their size
then; each may shrink but never grow, and a file that drops to 400 lines or fewer must be removed
from the list. Tests, fixtures, migrations, lock files and generated code are not checked.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 400
ROOTS = ("backend/labadda", "frontend/src", "scripts", "deploy")
SUFFIXES = {".py", ".ts", ".tsx", ".sh", ".mjs"}
SKIP_PARTS = {"node_modules", "__pycache__", "migrations", "gallery"}
# Size on 2026-11-24. Split these files; lower or remove an entry in the same commit.
RATCHET: dict[str, int] = {
    "scripts/generate_presentation.py": 1286,
    "scripts/seed_50_org_simulation.py": 1224,
    "frontend/src/pages/Board.tsx": 1070,
    "scripts/generate_user_onboarding_deck.py": 1002,
    "frontend/src/features/personal-board/PersonalBoard.tsx": 820,
    "scripts/release.py": 618,
    "backend/labadda/boardstate.py": 510,
    "backend/labadda/doctor.py": 504,
    "frontend/src/pages/Chat.tsx": 465,
    "backend/labadda/api/posts.py": 462,
    "backend/labadda/api/board.py": 446,
    "frontend/src/components/ConversationTask.tsx": 438,
    "backend/labadda/api/todos.py": 437,
    "scripts/rehearsal.py": 420,
    "backend/labadda/cli.py": 408,
    "backend/labadda/realtime.py": 405,
}


def checked_files() -> list[Path]:
    files = []
    for top in ROOTS:
        for path in (ROOT / top).rglob("*"):
            if not path.is_file() or path.suffix not in SUFFIXES or ".test." in path.name:
                continue
            if SKIP_PARTS & set(path.relative_to(ROOT).parts):
                continue
            files.append(path)
    return sorted(files)


def problems() -> list[str]:
    found = []
    seen = set()
    for path in checked_files():
        name = path.relative_to(ROOT).as_posix()
        lines = len(path.read_text(encoding="utf-8").splitlines())
        allowed = RATCHET.get(name)
        if allowed is None and lines > LIMIT:
            found.append(f"{name}: {lines} lines; split it below {LIMIT}")
        elif allowed is not None:
            seen.add(name)
            if lines > allowed:
                found.append(f"{name}: grew to {lines} lines (at most {allowed}); split it instead")
            elif lines <= LIMIT:
                found.append(f"{name}: now {lines} lines; remove it from RATCHET")
    found += [f"{name}: listed in RATCHET but missing" for name in sorted(set(RATCHET) - seen)]
    return found


def main() -> int:
    found = problems()
    for problem in found:
        print("check_sizes: " + problem, file=sys.stderr)
    if not found:
        print(f"check_sizes: OK ({len(RATCHET)} files still over {LIMIT} lines, none grew)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
