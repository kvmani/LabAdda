"""One software version everywhere, and an honest build stamp."""

import importlib.util
import json
import re
from pathlib import Path

from labadda import __version__, build_info
from labadda.cli import main

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_every_place_agrees_on_the_version():
    pyproject = re.search(r'^version = "([^"]+)"', (ROOT / "backend/pyproject.toml").read_text(), re.M)
    package = json.loads((ROOT / "frontend/package.json").read_text())
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    assert __version__ == "0.0.1-beta"
    assert pyproject.group(1) == __version__
    assert package["version"] == __version__
    assert lock["version"] == lock["packages"][""]["version"] == __version__
    assert release.source_version(ROOT) == __version__


def test_people_see_a_spaced_label():
    assert build_info.version_label("0.0.1-beta") == "0.0.1 beta"
    assert (
        build_info.summary_line("abc1234", "2026-11-13") == "Version 0.0.1 beta · commit abc1234 · 2026-11-13"
    )
    assert build_info.summary_line("", "") == "Version 0.0.1 beta · commit unknown"


def test_bundle_stamp_wins_and_bad_stamp_is_unknown(monkeypatch, tmp_path):
    stamp = tmp_path / "build_info.json"
    monkeypatch.setattr(build_info, "BUILD_FILE", stamp)
    monkeypatch.setattr(build_info, "_git", lambda *args: "")
    stamp.write_text(json.dumps({"commit": "abc1234", "date": "2026-11-13"}))
    build_info.commit_and_date.cache_clear()
    assert build_info.commit_and_date() == ("abc1234", "2026-11-13")
    stamp.write_text(json.dumps({"commit": "not a sha", "date": "x"}))
    build_info.commit_and_date.cache_clear()
    assert build_info.commit_and_date() == ("", "")
    assert build_info.build_info()["commit"] is None
    build_info.commit_and_date.cache_clear()


def test_version_endpoint_and_settings_report_it(as_user, make_client):
    body = make_client().get("/site/version").json()
    assert body["version"] == __version__
    assert body["version_label"] == "0.0.1 beta"
    rows = as_user("admin").get("/admin/settings").json()["groups"][0]["items"]
    assert rows[0]["key"] == "software_version"
    assert rows[0]["value"] == body["summary"]


def test_command_line_reports_it(capsys):
    try:
        main(["--version"])
    except SystemExit as done:
        assert done.code == 0
    assert capsys.readouterr().out.startswith("LabAdda Version 0.0.1 beta")
