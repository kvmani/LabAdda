"""A2 every audit action written by the code has a plain-English catalogue entry."""

import ast
from pathlib import Path

import labadda
from labadda import audit_catalog

SOURCE = Path(labadda.__file__).parent
WRITERS = {"record", "AuditEvent"}


def _name(call: ast.Call) -> str:
    func = call.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")


def _fragments(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _recorded_actions() -> tuple[set[str], list[tuple[str, str]]]:
    exact: set[str] = set()
    partial: list[tuple[str, str]] = []
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call) or _name(node) not in WRITERS:
                continue
            for keyword in node.keywords:
                if keyword.arg != "action":
                    continue
                if isinstance(keyword.value, ast.Constant):
                    exact.add(keyword.value.value)
                    continue
                pieces = _fragments(keyword.value)
                if not pieces:
                    # Only the recorder itself may forward a caller-supplied name.
                    assert path.name == "audit.py", f"{path.name}: action name cannot be checked"
                    continue
                if isinstance(keyword.value, ast.IfExp):
                    exact.update(_fragments(keyword.value.body) + _fragments(keyword.value.orelse))
                else:
                    partial.append((pieces[0], pieces[-1] if len(pieces) > 1 else ""))
    return exact, partial


def test_scan_finds_the_known_writers():
    exact, partial = _recorded_actions()
    assert {"identity.create", "people.change_step", "panel.end", "post.unpin"} <= exact
    assert partial, "dynamic action names must be scanned too"


def test_every_recorded_action_is_catalogued():
    exact, partial = _recorded_actions()
    missing = sorted(a for a in exact if a not in audit_catalog.CATALOG)
    assert not missing, f"add these audit actions to audit_catalog.CATALOG: {missing}"
    for prefix, suffix in partial:
        assert [a for a in audit_catalog.CATALOG if a.startswith(prefix) and a.endswith(suffix)], (
            prefix,
            suffix,
        )


def test_dynamic_names_are_fully_listed():
    for purpose in ("activation", "reset"):
        assert f"auth.{purpose}_redeemed" in audit_catalog.CATALOG
    for step in ("request", "claim", "finish", "cancel"):
        assert f"inventory_job.{step}" in audit_catalog.CATALOG


def test_entries_use_known_groups_and_render_without_detail():
    words = {"actor": "A", "target": "B", "unit": "U"}

    class Words(dict):
        def __missing__(self, key):
            return "unknown"

    for action, item in audit_catalog.CATALOG.items():
        assert item.group in audit_catalog.GROUPS, action
        assert item.sentence.format_map(Words(words)).strip().endswith("."), action
    assert set(audit_catalog.GROUPS) >= {item.group for item in audit_catalog.CATALOG.values()}
    assert audit_catalog.entry("not.recorded").sentence
