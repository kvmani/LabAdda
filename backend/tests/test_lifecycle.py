"""Operational sequencing and fail-closed behavior without touching host services."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
# CLI modules share a directory at runtime; make that explicit for importlib tests.
sys.path.insert(0, str(ROOT / "scripts"))
import lifecycle as life


@pytest.fixture
def configured(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "traffic").mkdir()
    for name in ("old", "next"):
        (root / "releases" / name).mkdir(parents=True)
    (root / "current").symlink_to("releases/old")
    site = json.loads((ROOT / "deploy/site.example.json").read_text())
    site.update(root=str(root), backup_root=str(tmp_path / "backups"), env_file=str(tmp_path / "site.env"))
    values = {
        "LABADDA_INSTANCE": site["instance"],
        "LABADDA_BASE_PATH": site["base_path"],
        "LABADDA_ENV": "staging",
        "LABADDA_COOKIE_NAME": "unique_staging",
        "LABADDA_COOKIE_SECURE": "true",
        "LABADDA_TRUSTED_ORIGINS": "https://" + site["server_name"],
        "LABADDA_FRONTEND_DIST": str(root / "current/frontend/dist"),
        "LABADDA_ASSET_DIR": str(root / "assets"),
        "LABADDA_DATABASE_URL": "postgresql+psycopg://fiction:secret@localhost:5432/fiction",
    }
    path = Path(site["env_file"])
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    path.chmod(0o600)
    return site


@pytest.mark.parametrize(
    "extra",
    ["PATH=/evil", "PYTHONPATH=/evil", "LABADDA_UNKNOWN=x", "LABADDA_ENV=pilot", 'LABADDA_TIMEZONE="UTC"'],
)
def test_reject_environment_ambiguity(configured, extra):
    with Path(configured["env_file"]).open("a") as out:
        out.write(extra + "\n")
    with pytest.raises(life.operations.OperationsError):
        life.runtime_environment(configured)


def test_environment_permissions_and_sanitization(configured):
    env = life.runtime_environment(configured)
    assert env["PATH"] == "/usr/bin:/bin" and "HOME" not in env
    Path(configured["env_file"]).chmod(0o644)
    with pytest.raises(life.operations.OperationsError):
        life.runtime_environment(configured)


def test_plan_is_read_only_and_stale_current_denied(configured):
    with patch.object(life.release, "validate_installed"):
        plan = life.maintenance(configured, "upgrade", "old", candidate="next", expected_schema="0025")
        assert not plan["applied"]
        assert not (Path(configured["root"]) / "operations").exists()
        with pytest.raises(life.operations.OperationsError, match="changed"):
            life.maintenance(configured, "backup", "outdated")


@pytest.mark.parametrize("failure", ["stop", "still_running", "backup", "migrate", "direct", "tls", None])
def test_upgrade_fail_closed_and_order(configured, failure):
    root = Path(configured["root"])
    events = []

    def command(argv, **kwargs):
        verb = argv[1]
        events.append(verb)
        if verb == "stop" and failure == "stop":
            raise life.operations.OperationsError("stopping failed")
        if verb == "show":
            return (
                "MainPID=4\nActiveState=active"
                if failure == "still_running"
                else "MainPID=0\nActiveState=inactive"
            )
        return ""

    def cli(target, env, action, *args):
        events.append(action)
        assert (root / "traffic/maintenance").exists()
        if action == failure:
            raise life.operations.OperationsError("synthetic failure")
        if action == "backup":
            args[0].mkdir()
            (args[0] / "manifest.json").write_text("{}")

    def probe(site, direct=False):
        events.append("direct" if direct else "tls")
        return {"passed": failure != ("direct" if direct else "tls")}

    with (
        patch.object(life.release, "validate_installed"),
        patch.object(life, "schema", return_value="0025"),
        patch.object(life, "command", side_effect=command),
        patch.object(life, "cli", side_effect=cli),
        patch.object(life.operations, "probe", side_effect=probe),
        patch.object(life, "wait_ready", side_effect=lambda site: probe(site, direct=True)["passed"]),
        patch.object(life.release, "switch") as switch,
    ):
        kwargs = dict(candidate="next", expected_schema="0025", apply=True, external_writers_stopped=True)
        if failure:
            with pytest.raises(life.operations.OperationsError):
                life.maintenance(configured, "upgrade", "old", **kwargs)
            assert (root / "traffic/maintenance").exists()
        else:
            result = life.maintenance(configured, "upgrade", "old", **kwargs)
            assert result["applied"] and not result["maintenance"]
            assert not (root / "traffic/maintenance").exists()
            assert events == ["stop", "show", "backup", "migrate", "start", "direct", "tls"]
        if failure in ("stop", "still_running", "backup"):
            switch.assert_not_called()
        logs = list((root / "operations").glob("*.jsonl"))
        last = json.loads(logs[0].read_text().splitlines()[-1])
        assert last["event"] == ("failed" if failure else "completed")
        assert "secret" not in logs[0].read_text()


def test_lock_and_private_directory(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with life.locked(root):
        with pytest.raises(life.operations.OperationsError, match="Another"):
            with life.locked(root):
                pass
    (root / "operations").chmod(0o755)
    with pytest.raises(life.operations.OperationsError, match="private"):
        with life.locked(root):
            pass


def test_command_timeout_and_redaction():
    with pytest.raises(life.operations.OperationsError, match="deadline"):
        life.command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.05)
    with pytest.raises(life.operations.OperationsError) as error:
        life.command([sys.executable, "-c", 'import sys; print("secret"); sys.exit(1)'])
    assert "secret" not in str(error.value)


def test_startup_polling_allows_delayed_readiness():
    with patch.object(life.operations, "probe", side_effect=[{"passed": False}, {"passed": True}]) as probe:
        assert life.wait_ready({}, seconds=1, interval=0)
        assert probe.call_count == 2
    with patch.object(life.operations, "probe", return_value={"passed": False}):
        assert not life.wait_ready({}, seconds=0)


def test_postgres_tls_allowlist(configured):
    path = Path(configured["env_file"])
    with path.open("a") as output:
        output.write("PGSSLMODE=verify-full\nPGSSLROOTCERT=/etc/labadda/postgres-ca.crt\n")
    assert life.runtime_environment(configured)["PGSSLMODE"] == "verify-full"
    path.write_text(path.read_text().replace("verify-full", "require"))
    with pytest.raises(life.operations.OperationsError, match="verify-full"):
        life.runtime_environment(configured)
