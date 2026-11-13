"""D2: every `labadda doctor` check passes and fails correctly, and no secret is ever printed."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from labadda import backup_status, doctor
from labadda.cli import main
from labadda.doctor_host import DatabaseState, FetchState, TlsState

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
SECRET = "s3cr3t-pw-do-not-print"
GIB = 1024**3


@pytest.fixture
def assets(tmp_path):
    directory = tmp_path / "assets"
    directory.mkdir()
    return directory


@pytest.fixture
def status_dir(tmp_path):
    directory = tmp_path / "status"
    directory.mkdir()
    backup_status.write_status(directory, good_backup(NOW - timedelta(hours=3)))
    return directory


def good_backup(finished_at: datetime) -> backup_status.BackupStatus:
    return backup_status.BackupStatus(finished_at, "success", 5 * 1024**2, "passed", "local", "0025", "r1")


def site_environ(assets: Path, status_dir: Path, **changes) -> dict:
    values = {
        "LABADDA_ENV": "pilot",
        "LABADDA_INSTANCE": "demo",
        "LABADDA_PORT": "8102",
        "LABADDA_BASE_PATH": "/labadda-demo",
        "LABADDA_DATABASE_URL": f"postgresql+psycopg://labadda:{SECRET}@localhost:5432/labadda_demo",
        "LABADDA_COOKIE_NAME": "labadda_demo",
        "LABADDA_COOKIE_SECURE": "true",
        "LABADDA_TRUSTED_ORIGINS": "https://labadda.intranet.example",
        "LABADDA_ASSET_DIR": str(assets),
        "LABADDA_STATUS_DIR": str(status_dir),
        "LABADDA_TIMEZONE": "Europe/London",
    }
    values.update(changes)
    return {key: value for key, value in values.items() if value is not None}


def healthy_host(assets, status_dir, **changes) -> doctor.Host:
    """A host where every check passes; tests replace one thing at a time."""
    environ = changes.pop("environ", None) or site_environ(assets, status_dir)
    values = {
        "environ": environ,
        "now": lambda: NOW,
        "database": lambda url: DatabaseState(True, "0025"),
        "release_schema": lambda: "0025",
        "free_bytes": lambda path: 50 * GIB,
        "can_write": lambda path: True,
        "fetch": lambda url, expected: FetchState("ok"),
        "certificate": lambda hostname, port, now: TlsState("ok", 200),
    }
    values.update(changes)
    return doctor.Host(**values)


def result_for(results, check_id):
    return next(result for result in results if result.id == check_id)


def test_healthy_site_passes_every_check_and_exits_zero(assets, status_dir):
    results = doctor.run_checks(healthy_host(assets, status_dir))

    # Feedback e-mail is optional: not set up reads as skipped, never as a failure.
    assert [result.status for result in results] == ["pass"] * 7 + ["skip", "pass"]
    assert doctor.passed(results)


# --- configuration -------------------------------------------------------------------------


def test_configuration_passes_with_valid_settings(assets, status_dir):
    _, result = doctor.check_configuration(healthy_host(assets, status_dir))

    assert result.status == "pass"


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"LABADDA_ENV": "production"}, "LABADDA_ENV"),
        ({"LABADDA_COOKIE_NAME": "labadda_session"}, "LABADDA_COOKIE_NAME"),
        ({"LABADDA_TRUSTED_ORIGINS": None}, "LABADDA_TRUSTED_ORIGINS"),
        ({"LABADDA_DATABASE_URL": None}, "LABADDA_DATABASE_URL"),
        ({"LABADDA_ASSET_DIR": "relative/assets"}, "LABADDA_ASSET_DIR"),
        ({"LABADDA_TIMEZONE": "Mars/Base"}, "LABADDA_TIMEZONE"),
        ({"LABADDA_SESSION_IDLE_MINUTES": "soon"}, "wrong kind"),
        ({"LABADDA_LOGIN_WINDOW_SECONDS": "0"}, "LABADDA_LOGIN_WINDOW_SECONDS"),
    ],
)
def test_configuration_fails_with_a_named_setting_and_a_fix(assets, status_dir, change, fragment):
    environ = site_environ(assets, status_dir, **change)

    _, result = doctor.check_configuration(healthy_host(assets, status_dir, environ=environ))

    assert result.status == "fail"
    assert fragment in result.summary
    assert result.fix


def test_bad_configuration_blocks_dependent_checks_but_not_the_time_zone(assets, status_dir):
    environ = site_environ(assets, status_dir, LABADDA_SESSION_IDLE_MINUTES="soon")

    results = doctor.run_checks(healthy_host(assets, status_dir, environ=environ))

    statuses = {result.id: result.status for result in results}
    assert statuses["configuration"] == "fail"
    assert statuses["database"] == statuses["backup"] == "skip"
    assert statuses["timezone"] == "pass"
    assert not doctor.passed(results)


# --- database ------------------------------------------------------------------------------


def test_database_passes_when_reachable_and_matching(assets, status_dir):
    host = healthy_host(assets, status_dir)

    assert doctor.check_database(host, doctor.load_settings(host.environ)).status == "pass"


@pytest.mark.parametrize(
    ("state", "fragment"),
    [
        (DatabaseState(False), "did not answer"),
        (DatabaseState(True, None), "not been set up"),
        (DatabaseState(True, "0019"), "does not match"),
    ],
)
def test_database_fails_when_unreachable_unmigrated_or_mismatched(assets, status_dir, state, fragment):
    host = healthy_host(assets, status_dir, database=lambda url: state)

    result = doctor.check_database(host, doctor.load_settings(host.environ))

    assert result.status == "fail"
    assert fragment in result.summary
    assert result.fix


# --- uploaded files ------------------------------------------------------------------------


def test_assets_pass_when_writable_with_room(assets, status_dir):
    host = healthy_host(assets, status_dir)

    result = doctor.check_assets(host, doctor.load_settings(host.environ))

    assert result.status == "pass"
    assert "50.0 GB" in result.summary


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"free_bytes": lambda path: None}, "does not exist"),
        ({"can_write": lambda path: False}, "cannot be written"),
        ({"free_bytes": lambda path: GIB // 2}, "Only 512.0 MB is free"),
    ],
)
def test_assets_fail_when_missing_unwritable_or_nearly_full(assets, status_dir, changes, fragment):
    host = healthy_host(assets, status_dir, **changes)

    result = doctor.check_assets(host, doctor.load_settings(host.environ))

    assert result.status == "fail"
    assert fragment in result.summary


def test_real_asset_probes_see_a_directory_and_a_missing_one(tmp_path):
    from labadda import doctor_host

    assert doctor_host.can_write(tmp_path)
    assert not doctor_host.can_write(tmp_path / "missing")
    assert doctor_host.free_bytes(tmp_path) > 0
    assert doctor_host.free_bytes(tmp_path / "missing") is None


# --- service and proxy ---------------------------------------------------------------------


def test_service_and_proxy_use_the_configured_address_and_prefix(assets, status_dir):
    asked = []

    def fetch(url, expected):
        asked.append((url, expected))
        return FetchState("ok")

    host = healthy_host(assets, status_dir, fetch=fetch)
    settings = doctor.load_settings(host.environ)

    assert doctor.check_service(host, settings).status == "pass"
    assert doctor.check_proxy(host, settings).status == "pass"
    assert asked == [
        ("http://127.0.0.1:8102/labadda-demo/healthz", "ok"),
        ("http://127.0.0.1:8102/labadda-demo/readyz", "ready"),
        ("https://labadda.intranet.example/labadda-demo/healthz", "ok"),
        ("https://labadda.intranet.example/labadda-demo/readyz", "ready"),
    ]


@pytest.mark.parametrize("kind", ["unreachable", "bad_response"])
def test_service_fails_when_it_does_not_answer_properly(assets, status_dir, kind):
    host = healthy_host(assets, status_dir, fetch=lambda url, expected: FetchState(kind))

    result = doctor.check_service(host, doctor.load_settings(host.environ))

    assert result.status == "fail"
    assert "systemctl start" in result.fix


def test_service_is_skipped_when_its_port_is_unknown(assets, status_dir):
    environ = site_environ(assets, status_dir, LABADDA_PORT=None)
    host = healthy_host(assets, status_dir, environ=environ)

    result = doctor.check_service(host, doctor.load_settings(host.environ))

    assert result.status == "skip"
    assert "--port" in result.summary


@pytest.mark.parametrize("kind", ["unreachable", "bad_response", "untrusted"])
def test_proxy_fails_when_the_public_address_does_not_work(assets, status_dir, kind):
    def fetch(url, expected):
        return FetchState(kind) if url.startswith("https://") else FetchState("ok")

    host = healthy_host(assets, status_dir, fetch=fetch)

    result = doctor.check_proxy(host, doctor.load_settings(host.environ))

    assert result.status == "fail"
    assert result.fix


def test_proxy_is_skipped_without_a_configured_address(assets, status_dir):
    environ = site_environ(assets, status_dir, LABADDA_ENV="development", LABADDA_TRUSTED_ORIGINS=None)
    host = healthy_host(assets, status_dir, environ=environ)

    assert doctor.check_proxy(host, doctor.load_settings(host.environ)).status == "skip"


# --- secure connection ---------------------------------------------------------------------


def test_tls_passes_with_a_trusted_certificate(assets, status_dir):
    host = healthy_host(assets, status_dir)

    result = doctor.check_tls(host, doctor.load_settings(host.environ))

    assert result.status == "pass"
    assert "200 more days" in result.summary


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"certificate": lambda h, p, n: TlsState("untrusted")}, "not trusted"),
        ({"certificate": lambda h, p, n: TlsState("unreachable")}, "could not be reached"),
        ({"certificate": lambda h, p, n: TlsState("ok", 12)}, "expires in 12 days"),
        ({"certificate": lambda h, p, n: TlsState("ok", -3)}, "expires in 0 days"),
    ],
)
def test_tls_fails_for_untrusted_unreachable_or_expiring_certificates(assets, status_dir, changes, fragment):
    host = healthy_host(assets, status_dir, **changes)

    result = doctor.check_tls(host, doctor.load_settings(host.environ))

    assert result.status == "fail"
    assert fragment in result.summary


def test_tls_fails_when_cookies_are_not_secure_over_https(assets, status_dir):
    environ = site_environ(assets, status_dir, LABADDA_COOKIE_SECURE="false")
    host = healthy_host(assets, status_dir, environ=environ)

    result = doctor.check_tls(host, doctor.load_settings(host.environ))

    assert result.status == "fail"
    assert "LABADDA_COOKIE_SECURE" in result.fix


def test_tls_is_required_on_a_pilot_site_but_optional_in_development(assets, status_dir):
    http_only = site_environ(assets, status_dir, LABADDA_TRUSTED_ORIGINS="http://labadda.intranet.example")
    pilot = healthy_host(assets, status_dir, environ=http_only)
    development = healthy_host(assets, status_dir, environ={**http_only, "LABADDA_ENV": "development"})

    assert doctor.check_tls(pilot, doctor.load_settings(pilot.environ)).status == "fail"
    assert doctor.check_tls(development, doctor.load_settings(development.environ)).status == "skip"


# --- backups -------------------------------------------------------------------------------


def backup_result(assets, status_dir, **changes):
    host = healthy_host(assets, status_dir, **changes)
    return doctor.check_backup(host, doctor.load_settings(host.environ))


def test_backup_passes_when_recent_and_verified(assets, status_dir):
    result = backup_result(assets, status_dir)

    assert result.status == "pass"
    assert "3 hours ago" in result.summary
    assert "5.0 MB" in result.summary


def test_backup_fails_when_no_status_file_exists(assets, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    result = backup_result(assets, empty)

    assert result.status == "fail"
    assert "No backup has been recorded" in result.summary


def test_backup_fails_when_the_status_directory_is_not_configured(assets, status_dir):
    environ = site_environ(assets, status_dir, LABADDA_STATUS_DIR=None)

    result = backup_result(assets, status_dir, environ=environ)

    assert result.status == "fail"
    assert "LABADDA_STATUS_DIR" in result.fix


def test_backup_fails_when_the_status_file_is_damaged(assets, status_dir):
    (status_dir / backup_status.STATUS_FILENAME).write_text("{not json")

    assert "cannot be read" in backup_result(assets, status_dir).summary


def test_backup_fails_when_the_last_run_failed(assets, status_dir):
    failed = backup_status.BackupStatus(
        NOW - timedelta(hours=1), "failure", None, "not_run", "local", None, None
    )
    backup_status.write_status(status_dir, failed)

    result = backup_result(assets, status_dir)

    assert result.status == "fail"
    assert "failed" in result.summary


def test_backup_fails_when_older_than_a_day_and_a_bit(assets, status_dir):
    backup_status.write_status(status_dir, good_backup(NOW - timedelta(hours=27)))

    result = backup_result(assets, status_dir)

    assert result.status == "fail"
    assert "27 hours ago" in result.summary


def test_backup_fails_when_dated_in_the_future(assets, status_dir):
    backup_status.write_status(status_dir, good_backup(NOW + timedelta(hours=2)))

    assert "future" in backup_result(assets, status_dir).summary


def test_backup_is_not_required_for_development(assets, tmp_path):
    environ = site_environ(assets, tmp_path, LABADDA_ENV="development", LABADDA_STATUS_DIR=None)

    result = backup_result(assets, tmp_path, environ=environ)

    assert result.status == "skip"


# --- time zone -----------------------------------------------------------------------------


def test_timezone_passes_for_a_real_zone_and_defaults_to_utc(assets, status_dir):
    assert doctor.check_timezone(healthy_host(assets, status_dir)).status == "pass"
    no_zone = healthy_host(
        assets, status_dir, environ=site_environ(assets, status_dir, LABADDA_TIMEZONE=None)
    )
    assert doctor.check_timezone(no_zone).status == "pass"


@pytest.mark.parametrize("name", ["Mars/Base", "", "../../etc/passwd"])
def test_timezone_fails_for_an_unknown_zone(assets, status_dir, name):
    environ = site_environ(assets, status_dir, LABADDA_TIMEZONE=name)

    result = doctor.check_timezone(healthy_host(assets, status_dir, environ=environ))

    assert result.status == "fail"
    assert result.fix


# --- output, exit codes and secrets --------------------------------------------------------


def failing_hosts(assets, status_dir, tmp_path):
    """Hosts that fail in different ways, all carrying the seeded secret in their settings."""
    empty = tmp_path / "empty"
    empty.mkdir()
    return [
        healthy_host(assets, status_dir, database=lambda url: DatabaseState(False)),
        healthy_host(assets, status_dir, database=lambda url: DatabaseState(True, "0001")),
        healthy_host(assets, status_dir, environ=site_environ(assets, empty)),
        healthy_host(
            assets,
            status_dir,
            environ=site_environ(assets, status_dir, LABADDA_SESSION_IDLE_MINUTES=f"bad-{SECRET}"),
        ),
        healthy_host(assets, status_dir, environ=site_environ(assets, status_dir, LABADDA_TIMEZONE=SECRET)),
        healthy_host(assets, status_dir, fetch=lambda url, expected: FetchState("unreachable")),
    ]


def test_no_secret_appears_in_any_text_or_json_report(assets, status_dir, tmp_path):
    hosts = [healthy_host(assets, status_dir), *failing_hosts(assets, status_dir, tmp_path)]

    for host in hosts:
        results = doctor.run_checks(host)
        text = doctor.format_report(results)
        report = json.dumps(doctor.as_report(results, NOW))
        assert SECRET not in text
        assert SECRET not in report
        assert "postgresql" not in text + report


def test_report_text_gives_a_fix_for_each_failure(assets, status_dir):
    host = healthy_host(assets, status_dir, database=lambda url: DatabaseState(False))

    text = doctor.format_report(doctor.run_checks(host))

    assert "[FAIL] Database:" in text
    assert "To fix:" in text
    assert "1 check(s) need attention." in text


def test_json_report_has_a_stable_shape(assets, status_dir):
    report = doctor.as_report(doctor.run_checks(healthy_host(assets, status_dir)), NOW)

    assert report["format"] == 1
    assert report["passed"] is True
    assert report["checked_at"] == "2026-11-11T12:00:00Z"
    assert [check["id"] for check in report["checks"]] == [
        "configuration",
        "database",
        "assets",
        "service",
        "proxy",
        "tls",
        "backup",
        "mail",
        "timezone",
    ]
    assert set(report["checks"][0]) == {"id", "title", "status", "summary", "fix"}


def test_env_file_reader_accepts_settings_and_rejects_anything_else(tmp_path):
    good = tmp_path / "good.env"
    good.write_text("# comment\n\nLABADDA_ENV=pilot\nPGSSLMODE=verify-full\n")
    bad = tmp_path / "bad.env"
    bad.write_text("LABADDA_ENV=pilot\nPATH=/evil\n")

    assert doctor.read_env_file(good) == {"LABADDA_ENV": "pilot", "PGSSLMODE": "verify-full"}
    with pytest.raises(ValueError):
        doctor.read_env_file(bad)


def test_command_exits_one_and_prints_json_for_a_broken_site(tmp_path, capsys, monkeypatch):
    env_file = tmp_path / "site.env"
    env_file.write_text(
        "LABADDA_ENV=pilot\n"
        f"LABADDA_DATABASE_URL=postgresql+psycopg://u:{SECRET}@127.0.0.1:1/none\n"
        "LABADDA_COOKIE_NAME=labadda_demo\n"
        "LABADDA_TRUSTED_ORIGINS=http://127.0.0.1:1\n"
        f"LABADDA_ASSET_DIR={tmp_path}/missing-assets\n"
    )
    monkeypatch.delenv("LABADDA_STATUS_DIR", raising=False)

    code = main(["doctor", "--json", "--env-file", str(env_file), "--port", "1"])

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert code == 1
    assert report["passed"] is False
    assert SECRET not in captured.out + captured.err


def test_command_rejects_an_unreadable_environment_file(tmp_path, capsys):
    code = main(["doctor", "--env-file", str(tmp_path / "missing.env")])

    assert code == 2
    assert "could not be read" in capsys.readouterr().err
