"""Help gate: front matter, template sections, screen routes, on-screen labels and links."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_help", ROOT / "scripts/check_help.py")
check_help = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_help)

FRONT = (
    "---\ntitle: Test page\nsummary: A page for tests.\naudience: everyone\n"
    "screen: /today\nupdated: 2026-11-11\n---\n"
)
BODY = """## What this is for

Text.

## Steps

1. Choose **Save changes**.

## What happens next

Done.

## If something goes wrong

Ask.

## Related

- [Other](other.md)
"""


def write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repository(root: Path, page: str = FRONT + BODY) -> None:
    write(
        root,
        "frontend/src/App.tsx",
        '<Route path="/today" element={<A />} />\n<Route path="/w/:id" element={<B />} />\n',
    )
    write(root, "frontend/src/pages/Screen.tsx", "<button>Save changes</button>\n")
    write(root, "frontend/src/help/using/test.md", page)
    write(
        root,
        "frontend/src/help/using/other.md",
        FRONT + BODY.replace("- [Other](other.md)", "- [Test](test.md)"),
    )


def problems_for(tmp_path: Path, page: str) -> list[str]:
    make_repository(tmp_path, page)
    return check_help.run(tmp_path)


def test_repository_help_passes():
    assert check_help.run(ROOT) == []


def test_valid_page_has_no_problems(tmp_path):
    assert problems_for(tmp_path, FRONT + BODY) == []


def test_missing_front_matter_is_reported(tmp_path):
    problems = problems_for(tmp_path, BODY)
    assert "frontend/src/help/using/test.md:1: the page must start with a front matter block" in problems


def test_missing_and_invalid_front_matter_values_are_reported(tmp_path):
    page = FRONT.replace("summary: A page for tests.\n", "").replace("everyone", "visitors") + BODY
    problems = problems_for(tmp_path, page)
    assert "frontend/src/help/using/test.md:1: front matter is missing 'summary'" in problems
    assert any("audience 'visitors'" in problem for problem in problems)


def test_unknown_screen_route_is_reported(tmp_path):
    problems = problems_for(tmp_path, FRONT.replace("/today", "/nowhere") + BODY)
    assert problems == [
        "frontend/src/help/using/test.md:1: screen '/nowhere' is not a route in frontend/src/App.tsx"
    ]


def test_page_without_a_screen_may_say_none(tmp_path):
    assert problems_for(tmp_path, FRONT.replace("/today", "none") + BODY) == []


def test_bold_label_missing_from_the_application_is_reported(tmp_path):
    problems = problems_for(tmp_path, FRONT + BODY.replace("**Save changes**", "**Send it off**"))
    assert problems == [
        "frontend/src/help/using/test.md:14: bold label 'Send it off' does not appear in the application"
    ]


def test_bold_text_in_code_is_not_a_label(tmp_path):
    assert problems_for(tmp_path, FRONT + BODY.replace("Text.", "Run `**x**` now.")) == []


def test_broken_and_outside_links_are_reported(tmp_path):
    page = FRONT + BODY.replace("- [Other](other.md)", "- [A](missing.md)\n- [B](https://example.invalid/x)")
    problems = problems_for(tmp_path, page)
    assert "frontend/src/help/using/test.md:26: link target does not exist: missing.md" in problems
    assert any("link 'https://example.invalid/x' must be a relative path" in problem for problem in problems)


def test_missing_unknown_and_misordered_sections_are_reported(tmp_path):
    problems = problems_for(tmp_path, FRONT + BODY.replace("## Related\n", "## Extras\n"))
    assert any("'Extras' is not a template section" in problem for problem in problems)
    assert "frontend/src/help/using/test.md: missing the 'Related' section" in problems
    swapped = BODY.replace("## Steps", "## TMP").replace("## What happens next", "## Steps")
    swapped = swapped.replace("## TMP", "## What happens next")
    assert any(
        "sections must follow the order" in problem for problem in problems_for(tmp_path, FRONT + swapped)
    )


def test_free_form_pages_skip_the_template(tmp_path):
    make_repository(tmp_path)
    write(
        tmp_path, "frontend/src/help/glossary.md", FRONT.replace("/today", "none") + "## Words\n\n- *Unit*.\n"
    )
    assert check_help.run(tmp_path) == []


def test_required_pages_are_enforced_when_listed(tmp_path):
    make_repository(tmp_path)
    assert check_help.check_required_pages(tmp_path, ("using/test.md",)) == []
    assert check_help.check_required_pages(tmp_path, ("using/absent.md",)) == [
        "frontend/src/help/using/absent.md: required page is missing"
    ]


def test_event_code_rule_is_off_until_h3(tmp_path):
    assert check_help.EVENT_CODE_CHECK_ENABLED is False
    assert check_help.check_event_codes(tmp_path) == []
