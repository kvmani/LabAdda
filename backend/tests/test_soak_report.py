"""T13: rehearsal failures must be reflected in the process outcome."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("soak", Path(__file__).resolve().parents[2] / "scripts/soak.py")
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


def valid():
    return {
        "ops_acknowledged": 10,
        "ops_seen_by_observer": 10,
        "lost": 0,
        "duplicates": 0,
        "revision_gaps": False,
        "error_count": 0,
        "targets": {"update": True, "list": True},
    }


def test_healthy_rehearsal_passes():
    assert soak.report_passes(valid(), enforce_targets=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ops_acknowledged", 0),
        ("ops_seen_by_observer", 9),
        ("lost", 1),
        ("duplicates", 1),
        ("revision_gaps", True),
        ("error_count", 1),
    ],
)
def test_integrity_failures_cannot_pass(field, value):
    report = valid()
    report[field] = value
    assert not soak.report_passes(report, enforce_targets=False)


def test_enforced_latency_failure_fails():
    report = valid()
    report["targets"]["update"] = False
    assert soak.report_passes(report, enforce_targets=False)
    assert not soak.report_passes(report, enforce_targets=True)


def test_missing_samples_have_json_safe_metrics():
    assert soak.metric([], 95) is None
    assert soak.metric([10, 20, 30], 95) == 30
