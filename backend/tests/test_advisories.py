"""Advisory checks fail closed and retain active advisory identifiers."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("advisories", SCRIPTS / "check_advisories.py")
advisories = importlib.util.module_from_spec(spec)
spec.loader.exec_module(advisories)


def test_unknown_python_metadata_is_not_a_clean_result(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(advisories.urllib.request, "urlopen", unavailable)
    assert advisories.python_advisories(("pillow", "13.0.0"))["state"] == "unknown"


def test_active_advisories_are_reported_and_withdrawn_ones_are_excluded(monkeypatch):
    import io

    metadata = {
        "vulnerabilities": [
            {"id": "GHSA-fixture-active", "fixed_in": ["2"], "withdrawn": None},
            {"id": "GHSA-fixture-withdrawn", "withdrawn": "2026-01-01"},
        ]
    }
    monkeypatch.setattr(
        advisories.urllib.request, "urlopen", lambda *args, **kwargs: io.StringIO(json.dumps(metadata))
    )
    result = advisories.python_advisories(("fictional", "1"))
    assert result["state"] == "checked"
    assert [row["id"] for row in result["advisories"]] == ["GHSA-fixture-active"]
