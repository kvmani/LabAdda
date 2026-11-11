"""D3: scheduled backups record their outcome, and retention is count-based and plan-first."""

import json
import re
from argparse import Namespace
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from labadda import backup_status
from tests.test_lifecycle import configured, life  # noqa: F401 — the shared site fixture, used below

NOW = datetime(2026, 11, 11, 2, 30, 7, tzinfo=UTC)
BUNDLE_PAYLOAD = b"fictional-dump-bytes"


@pytest.fixture
def site(configured, tmp_path):  # noqa: F811 — builds on the shared fixture
    status = tmp_path / "status"
    status.mkdir()
    status.chmod(0o755)
    with Path(configured["env_file"]).open("a") as env_file:
        env_file.write(f"LABADDA_STATUS_DIR={status}\n")
    configured["status_dir"] = status
    return configured


def arguments(**changes) -> Namespace:
    values = {
        "expected_current": "old",
        "expected_schema": "0025",
        "apply": True,
        "external_writers_stopped": True,
        "resume_after_backup": False,
        "unattended": False,
        "destination_alias": "local",
    }
    values.update(changes)
    return Namespace(**values)


class FakeHost:
    """Replace every host interaction; record the order of service and CLI actions."""

    def __init__(self, failing_action=None):
        self.failing_action = failing_action
        self.events = []

    def command(self, argv, **kwargs):
        self.events.append(argv[1])
        if argv[1] == "show":
            return "MainPID=0\nActiveState=inactive"
        return ""

    def cli(self, target, env, action, *args):
        self.events.append(action)
        if action == self.failing_action:
            raise life.operations.OperationsError("synthetic failure")
        if action == "backup":
            bundle = args[0]
            bundle.mkdir()
            (bundle / "manifest.json").write_text("{}")
            (bundle / "database.dump").write_bytes(BUNDLE_PAYLOAD)

    def probe(self, site, direct=False):
        self.events.append("direct" if direct else "tls")
        return {"passed": True}

    def __enter__(self):
        self.stack = ExitStack()
        patches = [
            patch.object(life.release, "validate_installed"),
            patch.object(life, "schema", return_value="0025"),
            patch.object(life, "command", side_effect=self.command),
            patch.object(life, "cli", side_effect=self.cli),
            patch.object(life.operations, "probe", side_effect=self.probe),
            patch.object(
                life, "wait_ready", side_effect=lambda site: self.probe(site, direct=True)["passed"]
            ),
        ]
        for item in patches:
            self.stack.enter_context(item)
        return self

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)


def read_back(site) -> backup_status.StatusReading:
    return backup_status.read_status(site["status_dir"])


def test_successful_backup_writes_a_valid_status_file(site):
    with FakeHost():
        result = life.scheduled_backup(site, arguments(), now=NOW)

    reading = read_back(site)

    assert result["status_file"] == "written"
    assert reading.state == "ok"
    assert reading.status.result == "success"
    assert reading.status.verification == "passed"
    assert reading.status.size_bytes == len(BUNDLE_PAYLOAD) + len("{}")
    assert reading.status.schema == "0025"
    assert reading.status.release == "old"
    assert reading.status.destination == "local"
    assert reading.status.finished_at == NOW.replace(microsecond=0)


def test_status_file_holds_no_path_host_or_secret(site):
    with FakeHost():
        life.scheduled_backup(site, arguments(), now=NOW)

    text = (site["status_dir"] / backup_status.STATUS_FILENAME).read_text()

    assert set(json.loads(text)) == backup_status.FIELDS
    assert str(Path(site["root"]).parent) not in text
    assert site["server_name"] not in text
    assert "secret" not in text


@pytest.mark.parametrize(
    ("failing_action", "verification"),
    [("backup", "not_run"), ("verify-backup", "failed")],
)
def test_failed_backup_writes_a_failure_status_and_keeps_maintenance(site, failing_action, verification):
    backup_status.write_status(
        site["status_dir"],
        backup_status.BackupStatus(NOW, "success", 1, "passed", "local", "0025", "old"),
    )

    with FakeHost(failing_action), pytest.raises(life.operations.OperationsError):
        life.scheduled_backup(site, arguments(), now=NOW)

    reading = read_back(site)

    assert reading.state == "ok"
    assert reading.status.result == "failure"
    assert reading.status.verification == verification
    assert reading.status.size_bytes is None
    assert (Path(site["root"]) / "traffic/maintenance").exists()


def test_failure_before_the_backup_starts_is_also_recorded(site):
    with (
        FakeHost("stop"),
        patch.object(life, "command", side_effect=life.operations.OperationsError("stop failed")),
        pytest.raises(life.operations.OperationsError),
    ):
        life.scheduled_backup(site, arguments(), now=NOW)

    assert read_back(site).status.result == "failure"


def test_plan_only_run_writes_no_status(site):
    with FakeHost():
        result = life.scheduled_backup(site, arguments(apply=False), now=NOW)

    assert not result["applied"]
    assert read_back(site).state == "unknown"


def test_site_without_status_directory_still_backs_up_and_says_so(site):
    env_file = Path(site["env_file"])
    kept = [line for line in env_file.read_text().splitlines(True) if "STATUS_DIR" not in line]
    env_file.write_text("".join(kept))
    with FakeHost():
        result = life.scheduled_backup(site, arguments(), now=NOW)

    assert result["status_file"] == "not configured"


def test_unwritable_status_is_reported_after_a_successful_backup(site):
    with FakeHost(), patch.object(life.backup_tools, "record_outcome", side_effect=OSError("full")):
        result = life.scheduled_backup(site, arguments(), now=NOW)

    assert result["applied"]
    assert result["status_file"] == "write failed"


def test_unattended_run_uses_the_installed_release_and_schema(site):
    with FakeHost():
        life.scheduled_backup(
            site, arguments(unattended=True, expected_current=None, expected_schema=None), now=NOW
        )

    status = read_back(site).status

    assert status.release == "old"
    assert status.schema == "0025"


def test_resume_after_backup_restarts_the_service_and_lifts_maintenance(site):
    with FakeHost() as host:
        result = life.scheduled_backup(site, arguments(resume_after_backup=True), now=NOW)

    assert host.events == ["stop", "show", "backup", "verify-backup", "start", "direct", "tls"]
    assert not result["maintenance"]
    assert not (Path(site["root"]) / "traffic/maintenance").exists()


def test_backup_without_resume_leaves_service_stopped(site):
    with FakeHost() as host:
        result = life.scheduled_backup(site, arguments(), now=NOW)

    assert host.events == ["stop", "show", "backup", "verify-backup"]
    assert result["maintenance"]
    assert (Path(site["root"]) / "traffic/maintenance").exists()


def test_failed_resume_keeps_maintenance_and_records_failure(site):
    host = FakeHost()
    with (
        host,
        patch.object(host, "probe", return_value={"passed": False}),
        pytest.raises(life.operations.OperationsError),
    ):
        life.scheduled_backup(site, arguments(resume_after_backup=True), now=NOW)

    assert (Path(site["root"]) / "traffic/maintenance").exists()
    assert read_back(site).status.result == "failure"


def test_upgrade_cannot_resume_on_its_own(site):
    with patch.object(life.release, "validate_installed"), pytest.raises(life.operations.OperationsError):
        life.maintenance(site, "upgrade", "old", candidate="next", expected_schema="0025", resume=True)


@pytest.mark.parametrize(
    "mode",
    [0o777, 0o775, 0o757],
)
def test_writable_status_directory_is_refused(site, mode):
    site["status_dir"].chmod(mode)

    with FakeHost(), pytest.raises(life.operations.OperationsError):
        life.scheduled_backup(site, arguments(), now=NOW)


def test_relative_missing_or_linked_status_directory_is_refused(tmp_path):
    link = tmp_path / "link"
    link.symlink_to(tmp_path)
    for value in ("relative/dir", str(tmp_path / "missing"), str(link)):
        with pytest.raises(life.operations.OperationsError):
            life.backup_tools.status_directory(value)


def test_destination_alias_rejects_paths_and_hosts():
    assert life.backup_tools.destination_alias("offsite-1") == "offsite-1"
    for value in ("/mnt/usb", "host.example.test", "", "UPPER"):
        with pytest.raises(life.operations.OperationsError):
            life.backup_tools.destination_alias(value)


def test_status_directory_setting_is_allowed_in_the_site_environment(site):
    env = life.runtime_environment(site)

    assert env["LABADDA_STATUS_DIR"] == str(site["status_dir"])


def test_backend_settings_read_the_same_directory(monkeypatch, tmp_path):
    from labadda.config import load_settings

    monkeypatch.setenv("LABADDA_STATUS_DIR", str(tmp_path))
    assert load_settings().status_dir == tmp_path
    monkeypatch.delenv("LABADDA_STATUS_DIR")
    assert load_settings().status_dir is None


def test_command_line_requires_expectations_unless_unattended(tmp_path):
    with pytest.raises(SystemExit):
        life.main(["--site", str(tmp_path / "site.json"), "backup"])
    with pytest.raises(SystemExit):
        life.main(["--site", str(tmp_path / "site.json"), "prune-backups"])
    with pytest.raises(SystemExit):
        life.main(["--site", str(tmp_path / "site.json"), "upgrade", "--unattended"])


# --- retention -------------------------------------------------------------------------------


def make_backup(root: Path, stamp: str, *, finished=True) -> str:
    name = f"{stamp}-{'a' * 32}"
    (root / name).mkdir()
    if finished:
        (root / name / "manifest.json").write_text("{}")
    return name


@pytest.fixture
def backups(site):
    root = Path(site["backup_root"])
    root.mkdir(mode=0o700)
    return root


def test_retention_plan_keeps_newest_and_lists_the_rest(backups):
    names = [make_backup(backups, f"2026110{day}T020000Z") for day in range(1, 6)]

    plan = life.backup_tools.retention_plan(backups, 2)

    assert plan["kept"] == [names[4], names[3]]
    assert plan["remove"] == [names[2], names[1], names[0]]
    assert not plan["applied"]


def test_retention_ignores_unfinished_stray_and_linked_entries(backups, tmp_path):
    make_backup(backups, "20261101T020000Z", finished=False)
    (backups / "notes.txt").write_text("not a backup")
    (backups / f"20261102T020000Z-{'b' * 32}").symlink_to(tmp_path)
    finished = make_backup(backups, "20261103T020000Z")

    plan = life.backup_tools.retention_plan(backups, 1)

    assert plan["kept"] == [finished]
    assert plan["remove"] == []
    assert plan["ignored_entries"] == 3


def test_retention_must_keep_at_least_one(backups):
    with pytest.raises(life.operations.OperationsError):
        life.backup_tools.retention_plan(backups, 0)


def test_prune_without_apply_deletes_nothing(site, backups):
    for day in range(1, 5):
        make_backup(backups, f"2026110{day}T020000Z")

    plan = life.prune_backups(site, 2)

    assert len(plan["remove"]) == 2
    assert len(list(backups.iterdir())) == 4
    assert not (Path(site["root"]) / "operations").exists()


def test_prune_apply_removes_only_planned_backups_and_journals_it(site, backups):
    names = [make_backup(backups, f"2026110{day}T020000Z") for day in range(1, 5)]
    stray = backups / "notes.txt"
    stray.write_text("keep me")

    result = life.prune_backups(site, 2, apply=True)

    assert result["applied"]
    assert sorted(path.name for path in backups.iterdir()) == sorted([names[2], names[3], "notes.txt"])
    journals = list((Path(site["root"]) / "operations").glob("*-prune-*.jsonl"))
    assert len(journals) == 1
    assert json.loads(journals[0].read_text().splitlines()[0])["remove"] == [names[1], names[0]]


def test_prune_refuses_while_another_operation_holds_the_lock(site, backups):
    for day in range(1, 4):
        make_backup(backups, f"2026110{day}T020000Z")

    with life.locked(Path(site["root"])), pytest.raises(life.operations.OperationsError, match="Another"):
        life.prune_backups(site, 1, apply=True)

    assert len(list(backups.iterdir())) == 3


def test_prune_with_missing_backup_directory_is_refused(site):
    with pytest.raises(life.operations.OperationsError):
        life.prune_backups(site, 3)


# --- systemd templates -----------------------------------------------------------------------

SYSTEMD = Path(__file__).resolve().parents[2] / "deploy/systemd"


def test_service_template_runs_the_unattended_backup_then_retention():
    unit = (SYSTEMD / "labadda-backup@.service").read_text()

    assert "Type=oneshot" in unit
    start = re.search(r"^ExecStart=(.*)$", unit, re.M).group(1)
    for flag in ("backup", "--unattended", "--apply", "--external-writers-stopped", "--resume-after-backup"):
        assert flag in start
    post = re.search(r"^ExecStartPost=(.*)$", unit, re.M).group(1)
    assert "prune-backups" in post
    assert "--keep" in post
    assert "--apply" in post
    assert "%i" in start


def test_timer_template_is_persistent_and_staggered():
    timer = (SYSTEMD / "labadda-backup@.timer").read_text()

    assert re.search(r"^OnCalendar=.+$", timer, re.M)
    assert "Persistent=true" in timer
    assert "RandomizedDelaySec=" in timer
    assert "WantedBy=timers.target" in timer
    assert "Unit=" not in timer or "labadda-backup@%i.service" in timer


# --- verify-backup command -------------------------------------------------------------------


@pytest.fixture
def real_bundle(tmp_path):
    from labadda import recovery

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "database.dump").write_bytes(BUNDLE_PAYLOAD)
    recovery.write_manifest(bundle, schema="0025", release="old", recovery_point="2026-11-11T02:30:00Z")
    return bundle, recovery.file_hash(bundle / "manifest.json")


def test_verify_backup_command_accepts_an_intact_bundle(real_bundle, capsys):
    from labadda.cli import main

    bundle, digest = real_bundle

    assert main(["verify-backup", str(bundle), "--manifest-sha256", digest]) == 0
    assert json.loads(capsys.readouterr().out) == {"verified": True, "schema": "0025"}


def test_verify_backup_command_rejects_a_changed_bundle_or_wrong_digest(real_bundle, capsys):
    from labadda.cli import main

    bundle, digest = real_bundle

    assert main(["verify-backup", str(bundle), "--manifest-sha256", "0" * 64]) == 2
    (bundle / "database.dump").write_bytes(b"tampered")
    assert main(["verify-backup", str(bundle), "--manifest-sha256", digest]) == 2
    assert "Backup verification failed" in capsys.readouterr().err
