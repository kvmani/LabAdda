"""Documentation gate: links, anchors, instruction size limits and plan consistency."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_docs", ROOT / "scripts/check_docs.py")
check_docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_docs)

PLAN_HEADER = "| # | ID | Package | Depends on | Status | Card |\n| --- | --- | --- | --- | --- | --- |\n"


def write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repository(
    root: Path, plan_row: str = "| 1 | Q1 | Lint | — | next | [quality](quality.md#q1--lint) |\n"
) -> None:
    write(root, "AGENTS.md", "# Rules\n\nSee [the plan](docs/plan/README.md).\n")
    write(root, "backend/AGENTS.md", "# Backend\n")
    write(root, "frontend/AGENTS.md", "# Frontend\n")
    write(root, "docs/plan/README.md", "# Plan\n\n" + PLAN_HEADER + plan_row)
    write(root, "docs/plan/quality.md", "# Quality\n\n### Q1 · Lint\n\nBody.\n")


def test_repository_documentation_passes():
    assert check_docs.run(ROOT) == []


def test_consistent_repository_has_no_problems(tmp_path):
    make_repository(tmp_path)
    assert check_docs.run(tmp_path) == []


def test_missing_link_target_is_reported(tmp_path):
    make_repository(tmp_path)
    write(tmp_path, "docs/guide.md", "See [missing](absent.md).\n")
    problems = check_docs.run(tmp_path)
    assert problems == ["docs/guide.md:1: link target does not exist: absent.md"]


def test_missing_anchor_is_reported(tmp_path):
    make_repository(tmp_path)
    write(tmp_path, "docs/guide.md", "See [rules](../AGENTS.md#no-such-heading).\n")
    problems = check_docs.run(tmp_path)
    assert problems == ["docs/guide.md:1: no heading for anchor: ../AGENTS.md#no-such-heading"]


def test_links_in_code_and_external_links_are_ignored(tmp_path):
    make_repository(tmp_path)
    text = "`[x](absent.md)` and [site](https://example.invalid/a)\n\n```\n[y](absent.md)\n```\n"
    write(tmp_path, "docs/guide.md", text)
    assert check_docs.run(tmp_path) == []


def test_slug_matches_github_anchor_rules():
    assert check_docs.slug("Q5 · Documentation gate") == "q5--documentation-gate"
    assert check_docs.slug("H4 · Operator handbook, first-use welcome, what's new") == (
        "h4--operator-handbook-first-use-welcome-whats-new"
    )
    assert check_docs.slug("3. Backend (`Python` 3.12)") == "3-backend-python-312"


def test_duplicate_headings_get_numbered_anchors():
    assert check_docs.anchors("# Same\n\n## Same\n") == {"same", "same-1"}


def test_oversized_agent_instructions_are_reported(tmp_path):
    make_repository(tmp_path)
    write(tmp_path, "AGENTS.md", "# Rules\n" + "line\n" * 200)
    problems = check_docs.run(tmp_path)
    assert len(problems) == 1
    assert problems[0].startswith("AGENTS.md: 201 lines exceeds the limit of 160")


def test_unknown_plan_status_is_reported(tmp_path):
    make_repository(tmp_path, "| 1 | Q1 | Lint | — | started | [quality](quality.md#q1--lint) |\n")
    assert check_docs.run(tmp_path) == ["docs/plan/README.md:5: Q1 has unknown status 'started'"]


def test_unknown_plan_dependency_is_reported(tmp_path):
    make_repository(tmp_path, "| 1 | Q1 | Lint | Z9 | next | [quality](quality.md#q1--lint) |\n")
    assert check_docs.run(tmp_path) == ["docs/plan/README.md:5: Q1 depends on unknown package 'Z9'"]


def test_plan_package_without_card_is_reported(tmp_path):
    make_repository(tmp_path)
    write(tmp_path, "docs/plan/quality.md", "# Quality\n\n### Q1 lint\n")
    problems = check_docs.run(tmp_path)
    assert "docs/plan/README.md:5: Q1 has no card heading in quality.md" in problems
