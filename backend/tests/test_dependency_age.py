"""Dependency age policy: the checker against a fake index (no network) and the release gate."""

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_dependency_age as age  # noqa: E402

NOW = datetime(2026, 11, 13, tzinfo=UTC)


def stamp(days_ago):
    return (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S.000000Z")


def fake_index(pypi=None, npm=None):
    def fetch(kind, name):
        return (pypi if kind == "pypi" else npm).get(name)

    return fetch


def test_python_pins_read_every_transitive_pin_and_ignore_comments():
    text = "# note\nfastapi==0.115.6\nargon2-cffi-bindings==26.1.0  # x\n\nnot a pin\nMako==1.4.3\n"
    assert age.python_pins(text) == [
        ("Mako", "1.4.3"),
        ("argon2-cffi-bindings", "26.1.0"),
        ("fastapi", "0.115.6"),
    ]


def test_npm_pins_use_the_package_name_from_the_node_modules_path():
    lock = {
        "packages": {
            "": {"name": "app", "version": "1.0.0"},
            "node_modules/react": {"version": "18.3.1"},
            "node_modules/@types/react": {"version": "18.3.12"},
            "node_modules/a/node_modules/semver": {"version": "6.3.1"},
            "node_modules/linked": {"version": "1.0.0", "link": True},
        }
    }
    assert age.npm_pins(lock) == [("@types/react", "18.3.12"), ("react", "18.3.1"), ("semver", "6.3.1")]


def test_young_and_unknown_versions_fail_and_old_ones_pass():
    pypi = {
        "old": {"releases": {"1.0": [{"upload_time_iso_8601": stamp(90)}]}},
        "young": {
            "releases": {"2.0": [{"upload_time_iso_8601": stamp(5)}, {"upload_time_iso_8601": stamp(9)}]}
        },
        "nodate": {"releases": {"3.0": []}},
    }
    npm = {"@s/p": {"time": {"1.2.3": stamp(31)}}, "edge": {"time": {"1.0.0": stamp(29)}}}
    pins = {
        "pypi": [("old", "1.0"), ("young", "2.0"), ("nodate", "3.0"), ("missing", "1.0")],
        "npm": [("@s/p", "1.2.3"), ("edge", "1.0.0")],
    }
    too_new, unknown = age.check(pins, fake_index(pypi, npm), now=NOW, min_days=30)
    assert [(k, n) for k, n, *_ in too_new] == [("pypi", "young"), ("npm", "edge")]
    assert too_new[0][3] == NOW - timedelta(days=9)  # the earliest upload counts, not the latest
    assert sorted(n for _, n, *_ in unknown) == ["missing", "nodate"]


def test_minimum_age_is_adjustable():
    pypi = {"p": {"releases": {"1": [{"upload_time_iso_8601": stamp(10)}]}}}
    pins = {"pypi": [("p", "1")]}
    assert age.check(pins, fake_index(pypi), now=NOW, min_days=7) == ([], [])
    assert len(age.check(pins, fake_index(pypi), now=NOW, min_days=30)[0]) == 1


def test_main_reports_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend/requirements.lock").write_text("young==2.0\n")
    (tmp_path / "frontend/package-lock.json").write_text(json.dumps({"packages": {}}))
    index = {"young": {"releases": {"2.0": [{"upload_time_iso_8601": stamp(2)}]}}}
    monkeypatch.setattr(age, "make_fetch", lambda *_: fake_index(index))
    assert age.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "TOO NEW  pypi young==2.0" in out
    assert "1 too new" in out


def test_the_shipped_locks_are_readable_and_nonempty():
    root = SCRIPTS.parent
    assert len(age.python_pins((root / "backend/requirements.lock").read_text())) > 20
    assert len(age.npm_pins(json.loads((root / "frontend/package-lock.json").read_text()))) > 100


def load_release():
    spec = importlib.util.spec_from_file_location("release_for_age", SCRIPTS / "release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_build_stops_before_building_when_a_pin_is_too_new(tmp_path, monkeypatch):
    release = load_release()
    monkeypatch.setattr(release.sys, "version_info", (3, 12, 0))
    monkeypatch.setattr(age, "main", lambda argv: 1)
    with pytest.raises(release.ReleaseError, match="too new"):
        release.build(tmp_path, tmp_path / "out", "0.0.1-beta")
    assert not (tmp_path / "out").exists()


def test_mirror_environment_pins_the_index_and_refuses_the_public_one(monkeypatch):
    release = load_release()
    monkeypatch.delenv("LABADDA_ALLOW_PUBLIC_INDEX", raising=False)
    env = release.mirror_environment("https://mirror.lab.example.in/simple", "mirror.lab.example.in")
    assert env["PIP_INDEX_URL"] == "https://mirror.lab.example.in/simple"
    assert env["PIP_TRUSTED_HOST"] == "mirror.lab.example.in"
    assert "PIP_NO_INDEX" not in env
    for bad in ("https://pypi.org/simple", "https://files.pythonhosted.org/", "ftp://m/simple", "mirror"):
        with pytest.raises(release.ReleaseError):
            release.mirror_environment(bad, None)
    monkeypatch.setenv("LABADDA_ALLOW_PUBLIC_INDEX", "1")
    assert release.mirror_environment("https://pypi.org/simple", None)["PIP_INDEX_URL"]
