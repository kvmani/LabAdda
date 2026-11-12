#!/usr/bin/env python3
"""Check that the in-app help pages are complete and still true to the application (HP-09).

Fails when a page lacks required front matter or template sections, when its `screen` route is
not defined in frontend/src/App.tsx, when a **bold on-screen label** does not occur in the
frontend source, or when a link does not reach another help page. Standard library only;
changes nothing.

    python3 scripts/check_help.py [repository-root]

The event-code rule (H3) is a separate function that H3 switches on by setting
EVENT_CODE_CHECK_ENABLED. H3 also adds the administrator pages to REQUIRED_PAGES.

Operator pages (H4) must quote only real commands: every `scripts/<name>.py` or `labadda`
command in a code block or code span must name an existing tool, one of its subcommands, and
only options that tool defines. The tools' argparse definitions are read from their source
(never executed).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from help_commands import check_commands, operator_tools

HELP_DIRECTORY = "frontend/src/help"
APP_FILE = "frontend/src/App.tsx"
SOURCE_DIRECTORY = "frontend/src"
FRONT_MATTER_KEYS = ("title", "summary", "audience", "screen", "updated")
AUDIENCES = {"everyone", "steward", "administrator", "operator"}
# Pages that are lists or logs, not task pages, so the task template does not apply.
FREE_FORM_PAGES = {"glossary.md", "whats-new.md"}
REQUIRED_SECTIONS = ("What this is for", "Steps", "What happens next", "If something goes wrong", "Related")
OPTIONAL_SECTIONS = ("Before you start",)
# The page list in docs/plan/help.md; each entry is a path below help/. H3 adds the administrator pages.
# Not yet written: using/my-profile-and-password.md (the app has no screen to change a password).
REQUIRED_PAGES: tuple[str, ...] = (
    "using/signing-in.md",
    "using/finding-your-way.md",
    "using/noticeboard.md",
    "using/replies-and-official-notices.md",
    "using/attaching-files.md",
    "using/reminders-and-upcoming.md",
    "using/whiteboard.md",
    "using/publishing-a-snapshot.md",
    "using/touch-panel.md",
    "using/chat-and-threads.md",
    "using/chat-files.md",
    "using/private-groups.md",
    "using/tasks.md",
    "using/assigning-tasks.md",
    "using/task-from-a-message.md",
    "using/my-day.md",
    "using/my-tasks.md",
    "using/my-notes.md",
    "using/notifications-and-alerts.md",
    "using/my-storage.md",
    "using/my-profile-and-password.md",
    "using/search.md",
    "stewards/what-a-steward-does.md",
    "stewards/members-and-roles.md",
    "stewards/read-only-and-archive.md",
    "stewards/pinning-and-official-notices.md",
    "stewards/removing-a-post.md",
    "stewards/handing-over-stewardship.md",
    "stewards/workspace-storage.md",
    "operator/install.md",
    "operator/upgrade.md",
    "operator/backup.md",
    "operator/restore.md",
    "operator/certificate-renewal.md",
    "operator/site-is-down.md",
    "operator/status-report.md",
    "operator/disk-is-filling.md",
    "operator/moving-to-a-new-server.md",
)
# Routes with no page of their own: redirects, the catch-all, the help centre (which never explains
# itself) and the activation form, which the signing-in page explains from the sign-in screen.
ROUTES_WITHOUT_PAGE = {"*", "/", "/activate", "/operations", "/help/*"}
# Administration routes get their pages from H3.
ROUTE_PAGES_EXEMPT_PREFIX = "/admin"
# H3 turns this on once the event-code catalogue exists to compare against.
EVENT_CODE_CHECK_ENABLED = False

FRONT_MATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)
FRONT_LINE = re.compile(r"^([a-z]+):\s*(.*?)\s*$")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
ROUTE = re.compile(r"""<Route\b[^>]*?\bpath=["']([^"']+)["']""", re.DOTALL)
SOURCE_SUFFIXES = {".ts", ".tsx"}
OPERATOR_SHELF = "operator"


def help_pages(root: Path) -> list[Path]:
    """Return every Markdown help page, sorted."""
    return sorted((root / HELP_DIRECTORY).rglob("*.md"))


def prose_lines(text: str, first_line: int = 1) -> list[tuple[int, str]]:
    """Return (line number, line) pairs outside fenced code blocks."""
    lines = []
    inside_fence = False
    for number, line in enumerate(text.splitlines(), start=first_line):
        if FENCE.match(line):
            inside_fence = not inside_fence
        elif not inside_fence:
            lines.append((number, line))
    return lines


def split_front_matter(text: str) -> tuple[dict[str, str] | None, str, int]:
    """Return (front matter or None, body, line number where the body starts)."""
    match = FRONT_MATTER.match(text)
    if not match:
        return None, text, 1
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        pair = FRONT_LINE.match(line)
        if pair:
            data[pair.group(1)] = pair.group(2).strip('"')
    body_start = match.group(1).count("\n") + 4
    return data, match.group(2), body_start


def app_routes(root: Path) -> set[str]:
    """Return every route path declared in App.tsx."""
    return set(ROUTE.findall((root / APP_FILE).read_text(encoding="utf-8")))


def source_text(root: Path) -> str:
    """Return the application source that on-screen words come from (tests and help excluded)."""
    parts = []
    for path in sorted((root / SOURCE_DIRECTORY).rglob("*")):
        relative = path.relative_to(root / SOURCE_DIRECTORY).parts
        skipped = relative[0] in {"help"} or "generated" in relative or ".test." in path.name
        if path.suffix in SOURCE_SUFFIXES and not skipped:
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def check_front_matter(name: str, data: dict[str, str] | None, routes: set[str]) -> list[str]:
    """Return a problem for each missing or invalid front matter value."""
    if data is None:
        return [f"{name}:1: the page must start with a front matter block"]
    problems = [
        f"{name}:1: front matter is missing '{key}'" for key in FRONT_MATTER_KEYS if not data.get(key)
    ]
    if data.get("audience") and data["audience"] not in AUDIENCES:
        problems.append(f"{name}:1: audience '{data['audience']}' is not one of {sorted(AUDIENCES)}")
    if data.get("updated") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["updated"]):
        problems.append(f"{name}:1: updated must be a date like 2026-11-11")
    screen = data.get("screen")
    if screen and screen != "none" and screen not in routes:
        problems.append(f"{name}:1: screen '{screen}' is not a route in {APP_FILE}")
    return problems


def check_sections(name: str, body: str, body_start: int) -> list[str]:
    """Return a problem for each missing, unknown or out-of-order template section."""
    found = []
    for number, line in prose_lines(body, body_start):
        match = HEADING.match(line)
        if match and len(match.group(1)) == 2:
            found.append((number, match.group(2)))
    allowed = [*REQUIRED_SECTIONS, *OPTIONAL_SECTIONS]
    problems = [
        f"{name}:{number}: '{title}' is not a template section"
        for number, title in found
        if title not in allowed
    ]
    titles = [title for _, title in found if title in allowed]
    problems += [
        f"{name}: missing the '{title}' section" for title in REQUIRED_SECTIONS if title not in titles
    ]
    template_order = ["What this is for", "Before you start", "Steps", "What happens next"]
    template_order += ["If something goes wrong", "Related"]
    if titles != sorted(titles, key=template_order.index):
        problems.append(f"{name}: sections must follow the order {', '.join(template_order)}")
    return problems


def check_labels(name: str, body: str, body_start: int, source: str) -> list[str]:
    """Return a problem for each bold label that is not on any screen."""
    problems = []
    for number, line in prose_lines(body, body_start):
        for label in BOLD.findall(INLINE_CODE.sub("", line)):
            if label not in source:
                problems.append(f"{name}:{number}: bold label '{label}' does not appear in the application")
    return problems


def check_links(root: Path, page: Path, body: str, body_start: int) -> list[str]:
    """Return a problem for each link that does not reach another help page."""
    problems = []
    name = str(page.relative_to(root))
    for number, line in prose_lines(body, body_start):
        for target in LINK.findall(INLINE_CODE.sub("", line)):
            if not target.endswith(".md") or re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*:|/|#)", target):
                problems.append(f"{name}:{number}: link '{target}' must be a relative path to a help page")
            elif not (page.parent / target).resolve().is_file():
                problems.append(f"{name}:{number}: link target does not exist: {target}")
    return problems


def check_required_pages(root: Path, required: tuple[str, ...]) -> list[str]:
    """Return a problem for each page the plan requires that has no file (HP-06)."""
    return [
        f"{HELP_DIRECTORY}/{path}: required page is missing"
        for path in required
        if not (root / HELP_DIRECTORY / path).is_file()
    ]


def check_route_pages(routes: set[str], screens: set[str]) -> list[str]:
    """Return a problem for each application route outside /admin that no page explains (H2)."""
    return [
        f"{APP_FILE}: route '{route}' has no help page whose screen matches it"
        for route in sorted(routes)
        if route not in ROUTES_WITHOUT_PAGE
        and not route.startswith(ROUTE_PAGES_EXEMPT_PREFIX)
        and route not in screens
    ]


def check_event_codes(root: Path) -> list[str]:
    """Return a problem for each event code without a troubleshooting page, and the reverse (H3)."""
    if not EVENT_CODE_CHECK_ENABLED:
        return []
    raise NotImplementedError("H3 compares the code catalogue with help/troubleshooting here")


def run(root: Path, required: tuple[str, ...] = REQUIRED_PAGES, cover_routes: bool = True) -> list[str]:
    """Return every help problem found below root."""
    routes = app_routes(root)
    source = source_text(root)
    problems = []
    screens: set[str] = set()
    tools = operator_tools(root)
    for page in help_pages(root):
        name = str(page.relative_to(root))
        data, body, body_start = split_front_matter(page.read_text(encoding="utf-8"))
        screens.add((data or {}).get("screen", ""))
        problems += check_front_matter(name, data, routes)
        if page.relative_to(root / HELP_DIRECTORY).as_posix() not in FREE_FORM_PAGES:
            problems += check_sections(name, body, body_start)
        problems += check_labels(name, body, body_start, source)
        problems += check_links(root, page, body, body_start)
        if page.relative_to(root / HELP_DIRECTORY).parts[0] == OPERATOR_SHELF:
            problems += check_commands(page, root, body, body_start, tools)
    problems += check_required_pages(root, required)
    if cover_routes:
        problems += check_route_pages(routes, screens)
    return problems + check_event_codes(root)


def main(arguments: list[str]) -> int:
    root = Path(arguments[1]).resolve() if len(arguments) > 1 else Path(__file__).resolve().parents[1]
    problems = run(root)
    for problem in problems:
        print(problem)
    if problems:
        print(f"check_help: {len(problems)} problem(s)")
        return 1
    print("check_help: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
