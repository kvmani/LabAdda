#!/usr/bin/env python3
"""Check that repository documentation is navigable and the delivery plan is consistent.

Fails when a relative Markdown link or heading anchor does not resolve, when an agent
instruction file exceeds its size limit, or when a package in the plan table has no card,
an unknown status or an unknown dependency. Standard library only; changes nothing.

    python3 scripts/check_docs.py [repository-root]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKIPPED_DIRECTORIES = {".git", "node_modules", ".venv", "var", "dist", "build"}
SIZE_LIMITS = {"AGENTS.md": 160, "backend/AGENTS.md": 80, "frontend/AGENTS.md": 80}
PLAN_INDEX = "docs/plan/README.md"
PLAN_STATUSES = {"done", "in progress", "next", "queued", "owner", "deferred"}
DEPENDENCY_WORDS = {"—", "all above"}

LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
PACKAGE_ID = re.compile(r"^[A-Z]\d+$")


def markdown_files(root: Path) -> list[Path]:
    """Return every Markdown file below root, skipping generated and vendored directories."""
    found = []
    for path in sorted(root.rglob("*.md")):
        if not SKIPPED_DIRECTORIES.intersection(path.relative_to(root).parts):
            found.append(path)
    return found


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Return (line number, line) pairs that are outside fenced code blocks."""
    lines = []
    inside_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            inside_fence = not inside_fence
            continue
        if not inside_fence:
            lines.append((number, line))
    return lines


def slug(heading: str) -> str:
    """Return the anchor GitHub generates for a heading."""
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    plain = plain.replace("`", "").replace("*", "").strip().lower()
    kept = "".join(ch for ch in plain if ch.isalnum() or ch in " -_")
    return kept.replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Return every heading anchor in a Markdown document, numbering duplicates as GitHub does."""
    seen: dict[str, int] = {}
    result = set()
    for _, line in prose_lines(text):
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def check_links(root: Path, files: list[Path]) -> list[str]:
    """Return a problem for each relative link whose file or anchor does not exist."""
    problems = []
    anchor_cache: dict[Path, set[str]] = {}

    def anchors_of(path: Path) -> set[str]:
        if path not in anchor_cache:
            anchor_cache[path] = anchors(path.read_text(encoding="utf-8"))
        return anchor_cache[path]

    for source in files:
        text = source.read_text(encoding="utf-8")
        for number, line in prose_lines(text):
            for target in LINK.findall(INLINE_CODE.sub("", line)):
                if EXTERNAL.match(target):
                    continue
                file_part, _, anchor = target.partition("#")
                destination = (source.parent / file_part).resolve() if file_part else source
                where = f"{source.relative_to(root)}:{number}"
                if not destination.exists():
                    problems.append(f"{where}: link target does not exist: {target}")
                    continue
                if anchor and destination.suffix == ".md" and anchor not in anchors_of(destination):
                    problems.append(f"{where}: no heading for anchor: {target}")
    return problems


def check_sizes(root: Path) -> list[str]:
    """Return a problem for each agent instruction file that is missing or too long."""
    problems = []
    for name, limit in SIZE_LIMITS.items():
        path = root / name
        if not path.exists():
            problems.append(f"{name}: required file is missing")
            continue
        length = len(path.read_text(encoding="utf-8").splitlines())
        if length > limit:
            problems.append(f"{name}: {length} lines exceeds the limit of {limit}; move detail into docs/")
    return problems


def plan_rows(text: str) -> list[tuple[int, list[str]]]:
    """Return (line number, cells) for each package row of the plan table."""
    rows = []
    for number, line in prose_lines(text):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 6 and PACKAGE_ID.match(cells[1]):
            rows.append((number, cells))
    return rows


def check_plan(root: Path) -> list[str]:
    """Return a problem for each inconsistency in the delivery plan table."""
    index = root / PLAN_INDEX
    if not index.exists():
        return [f"{PLAN_INDEX}: required file is missing"]
    rows = plan_rows(index.read_text(encoding="utf-8"))
    if not rows:
        return [f"{PLAN_INDEX}: no package rows found in the plan table"]
    problems = []
    known = {cells[1] for _, cells in rows}
    if len(known) != len(rows):
        problems.append(f"{PLAN_INDEX}: a package ID appears more than once")
    for number, (_, package, _, depends, status, card) in rows:
        where = f"{PLAN_INDEX}:{number}"
        if status not in PLAN_STATUSES:
            problems.append(f"{where}: {package} has unknown status '{status}'")
        for dependency in (item.strip() for item in depends.split(",")):
            if dependency not in known and dependency not in DEPENDENCY_WORDS:
                problems.append(f"{where}: {package} depends on unknown package '{dependency}'")
        link = LINK.search(card)
        if not link:
            problems.append(f"{where}: {package} has no card link")
            continue
        file_part, _, anchor = link.group(1).partition("#")
        card_file = (index.parent / file_part) if file_part else index
        if not anchor.startswith(package.lower() + "-"):
            problems.append(f"{where}: {package} card link does not point at its own card")
        elif card_file.exists():
            heading = re.compile(rf"^#{{2,3}} {package} · ", re.MULTILINE)
            if not heading.search(card_file.read_text(encoding="utf-8")):
                problems.append(f"{where}: {package} has no card heading in {card_file.name}")
    return problems


def run(root: Path) -> list[str]:
    """Return every documentation problem found below root."""
    files = markdown_files(root)
    return check_links(root, files) + check_sizes(root) + check_plan(root)


def main(arguments: list[str]) -> int:
    root = Path(arguments[1]).resolve() if len(arguments) > 1 else Path(__file__).resolve().parents[1]
    problems = run(root)
    for problem in problems:
        print(problem)
    if problems:
        print(f"check_docs: {len(problems)} problem(s)")
        return 1
    print("check_docs: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
