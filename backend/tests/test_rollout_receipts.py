"""Regressions for receipt-based backup copies and serialized upgrade recovery."""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.test_deploy_safety import shell

pytest.importorskip("fcntl")
from tests import test_lifecycle as lifecycle_tests

ROOT = Path(__file__).resolve().parents[2]


configured_site = lifecycle_tests.configured
life = lifecycle_tests.life


def test_backup_copy_uses_returned_bundle_and_digest(tmp_path):
    kit = tmp_path / "kit"
    (kit / "lib").mkdir(parents=True)
    shutil.copy2(ROOT / "deploy/backup-now.sh", kit)
    backups = tmp_path / "backups"
    bundle = backups / "20261123T100000Z-0123456789abcdef0123456789abcdef"
    bundle.mkdir(parents=True)
    (bundle / "manifest.json").write_text("fixture")
    (backups / "retired").mkdir()
    (tmp_path / "site.json").touch()
    digest = "e" * 64
    receipt = json.dumps({"backup": str(bundle), "manifest_sha256": digest})
    (kit / "lib/common.sh").write_text(
        f'BACKUP_ROOT="{backups}"\nSITE_JSON="{tmp_path}/site.json"\nPYTHON="{sys.executable}"\n'
        f'INSTANCE_ROOT="{tmp_path}"\nDRY_RUN=0\n'
        "set_paths() { :; }; need_root() { :; }; load_site_identity() { :; }\n"
        'step() { :; }; ok() { :; }; say() { echo "$*"; }; die() { exit 1; }\n'
        f"lifecycle() {{ printf '%s\\n' '{receipt}'; }}\n"
        "is_user_scope() { return 1; }\n"
        f'with_env() {{ [[ "${{*: -1}}" == "{digest}" && '
        f'"${{*: -3:1}}" == "{tmp_path}/offsite/{bundle.name}" ]]; }}\n'
    )
    result = shell(tmp_path, f'bash "{kit}/backup-now.sh" --copy-to "{tmp_path}/offsite"')
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "offsite" / bundle.name / "manifest.json").read_text() == "fixture"
    assert digest in result.stdout


@pytest.mark.parametrize("unchanged", [True, False])
def test_locked_upgrade_recovery_requires_compatible_schema(request, unchanged):
    site = request.getfixturevalue("configured_site")
    root = Path(site["root"])
    actions = []

    def service(_site, action, *_args):
        actions.append(action)
        return "MainPID=0\nActiveState=inactive"

    def cli(_target, _env, action, *args):
        if action == "backup":
            args[0].mkdir()
            (args[0] / "manifest.json").write_text("{}")
        elif action == "migrate":
            raise life.operations.OperationsError("fixture interrupted migration")

    with (
        patch.object(life.release, "validate_installed"),
        patch.object(life, "systemctl", side_effect=service),
        patch.object(life, "cli", side_effect=cli),
        patch.object(life, "schema", side_effect=["0048", "0048" if unchanged else "0049"]),
        patch.object(life, "wait_ready", return_value=True),
        patch.object(life.operations, "probe", return_value={"passed": True}),
        pytest.raises(life.operations.OperationsError) as error,
    ):
        life.maintenance(
            site,
            "upgrade",
            "old",
            candidate="next",
            expected_schema="0048",
            apply=True,
            external_writers_stopped=True,
            recover=True,
        )
    assert isinstance(error.value, life.UpgradeRolledBack) == unchanged
    assert ("start" in actions) == unchanged
    assert (root / "traffic/maintenance").exists() != unchanged


def test_contended_upgrade_leaves_other_operation_in_control(request):
    site = request.getfixturevalue("configured_site")
    root = Path(site["root"])
    marker = root / "traffic/maintenance"
    marker.touch()
    with (
        life.locked(root),
        patch.object(life.release, "validate_installed"),
        patch.object(life, "systemctl") as service,
        pytest.raises(life.operations.OperationsError, match="Another site operation"),
    ):
        life.maintenance(
            site,
            "upgrade",
            "old",
            candidate="next",
            expected_schema="0048",
            apply=True,
            external_writers_stopped=True,
            recover=True,
        )
    assert marker.exists()
    service.assert_not_called()


@pytest.mark.parametrize("public_ready", [True, False])
def test_compatible_rollback_after_candidate_restart_checks_public_route(tmp_path, public_ready):
    root = tmp_path
    marker = root / "maintenance"
    marker.touch()
    log = root / "operation.jsonl"
    plan = {"current": "old", "candidate": "next", "expected_schema": "0048"}
    site = {"root": str(root), "instance": "staging"}
    with (
        patch.object(life, "current_release", return_value=("next", root / "releases/next")),
        patch.object(life, "stop_writers") as stop,
        patch.object(life, "schema", return_value="0048"),
        patch.object(life.release, "switch") as switch,
        patch.object(life, "systemctl"),
        patch.object(life, "wait_ready", return_value=True),
        patch.object(life.operations, "probe", return_value={"passed": public_ready}),
    ):
        if public_ready:
            assert life.recover_compatible(site, plan, {}, marker, log)
        else:
            with pytest.raises(life.operations.OperationsError, match="readiness failed"):
                life.recover_compatible(site, plan, {}, marker, log)
    stop.assert_called_once()
    switch.assert_called_once_with(root, "old", "0048", rollback=True)
    assert marker.exists() != public_ready
