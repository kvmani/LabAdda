"""Managed simulation safety, failed-stage persistence and cleanup contracts."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import simulate


def test_plan_never_starts_stack(tmp_path):
    with patch.object(simulate, "execute") as execute:
        assert simulate.main(["--out", str(tmp_path / "plan")]) == 0
        execute.assert_not_called()
        assert not (tmp_path / "plan").exists()


def test_environment_cannot_select_site_database(tmp_path, monkeypatch):
    monkeypatch.setenv("LABADDA_PG", "production")
    monkeypatch.setenv("LABADDA_RUN_DIR", "/precious")
    monkeypatch.setenv("PGDATABASE", "production")
    env = simulate.environment(tmp_path)
    assert env["LABADDA_PG"].endswith("@localhost:5432")
    assert env["LABADDA_RUN_DIR"].endswith("/var/simulation-stack")
    assert "PGDATABASE" not in env


@pytest.mark.parametrize("failure", [True, False])
def test_aggregate_requires_all_stages_and_cleanup(tmp_path, failure):
    calls = []

    def run(argv, env, log, timeout):
        calls.append([str(x) for x in argv])
        if failure and argv[0] == "node":
            raise simulate.SimulationError("synthetic browser failure")

    out = tmp_path / "evidence"
    with patch.object(simulate, "run", side_effect=run), patch.object(simulate, "confirm_stop"):
        result = simulate.execute("quick", out)
    assert result["passed"] is not failure
    assert result["cleanup_passed"]
    assert calls[-1][-1] == "stop"
    assert (out / "report.json").is_file()
    if failure:
        assert len(result["stages"]) == 2
        assert result["stages"][-1]["name"] == "chat-attachments"
        assert not result["stages"][-1]["passed"]
    with pytest.raises(FileExistsError):
        simulate.execute("quick", out)


def test_cleanup_failure_cannot_pass(tmp_path):
    def run(argv, env, log, timeout):
        if log.name == "cleanup.log":
            raise simulate.SimulationError("cleanup failed")

    with patch.object(simulate, "run", side_effect=run), patch.object(simulate, "confirm_stop"):
        result = simulate.execute("quick", tmp_path / "report")
    assert not result["passed"] and not result["cleanup_passed"]


def test_unconfirmed_shutdown_cannot_pass(tmp_path):
    with (
        patch.object(simulate, "run"),
        patch.object(simulate, "confirm_stop", side_effect=simulate.SimulationError("alive")),
    ):
        result = simulate.execute("quick", tmp_path / "evidence")
    assert not result["cleanup_passed"] and not result["passed"]


def test_termination_becomes_python_interruption():
    with pytest.raises(KeyboardInterrupt):
        simulate.interrupted(15, None)


def test_full_covers_assignment_and_discussion():
    assert {"task-assignment", "task-comments"} <= set(simulate.PROFILES["full"])
