"""`labadda doctor`: read-only installation checks with a plain-language result and fix hint.

Every check returns a `CheckResult`; none changes anything, and no result ever contains a
setting's value, so the output is safe to paste into a support request. The outside world
(database, disk, network, clock) is reached only through `Host`, which tests replace.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import backup_status, doctor_host
from .config import Settings, load_settings
from .doctor_host import DatabaseState, FetchState, TlsState

RESERVE_FREE_BYTES = 1024**3
CERTIFICATE_WARN_DAYS = 30
SITE_ENVIRONMENTS = ("staging", "pilot")
KNOWN_ENVIRONMENTS = ("development", "test", *SITE_ENVIRONMENTS)
DEFAULT_COOKIE_NAME = "labadda_session"
ENV_FILE_KEYS = ("LABADDA_", "PGSSL")

Status = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class CheckResult:
    """One line of the report."""

    id: str
    title: str
    status: Status
    summary: str
    fix: str | None = None

    def as_record(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "fix": self.fix,
        }


def utc_now() -> datetime:
    """The current time in UTC."""
    return datetime.now(UTC)


@dataclass
class Host:
    """Everything a check may look at or ask; replace the fields to test without a real site."""

    environ: Mapping[str, str]
    now: Callable[[], datetime] = utc_now
    database: Callable[[str], DatabaseState] = doctor_host.database_state
    release_schema: Callable[[], str] = doctor_host.release_schema_head
    free_bytes: Callable[[Path], int | None] = doctor_host.free_bytes
    can_write: Callable[[Path], bool] = doctor_host.can_write
    fetch: Callable[[str, str], FetchState] = doctor_host.fetch_health
    certificate: Callable[[str, int, datetime], TlsState] = doctor_host.inspect_certificate
    reserve_bytes: int = RESERVE_FREE_BYTES


def read_env_file(path: Path) -> dict[str, str]:
    """Read `KEY=value` lines for LABADDA_ and PGSSL settings; raises ValueError on a bad line."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.startswith(ENV_FILE_KEYS):
            raise ValueError("The environment file has a line that is not a LABADDA_ setting")
        values[key] = value
    return values


def human_size(count: int) -> str:
    """Format a byte count for office staff."""
    size = float(count)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _skipped(check_id: str, title: str, reason: str) -> CheckResult:
    return CheckResult(check_id, title, "skip", reason)


def _blocked(check_id: str, title: str) -> CheckResult:
    return _skipped(check_id, title, "Not checked until the configuration problem above is fixed.")


def configuration_problems(settings: Settings) -> list[str]:
    """Plain-language problems with otherwise parseable settings."""
    problems = []
    if settings.environment not in KNOWN_ENVIRONMENTS:
        problems.append("LABADDA_ENV must be development, test, staging or pilot")
    if settings.environment in SITE_ENVIRONMENTS:
        if settings.database_url == Settings.database_url:
            problems.append("LABADDA_DATABASE_URL still has the development default")
        if settings.cookie_name == DEFAULT_COOKIE_NAME:
            problems.append("LABADDA_COOKIE_NAME must be unique to this site")
        if not settings.trusted_origins:
            problems.append("LABADDA_TRUSTED_ORIGINS must list the address people use")
        if not settings.asset_dir.is_absolute():
            problems.append("LABADDA_ASSET_DIR must be a full path")
    return problems


def check_configuration(host: Host) -> tuple[Settings | None, CheckResult]:
    """Load the settings the way the service does and report anything unusable."""
    title = "Settings"
    try:
        settings = load_settings(host.environ)
    except ValueError as error:
        message = str(error)
        # Our own messages name only a setting; a number-parsing message would echo its value.
        named = (
            message if message.startswith("LABADDA_") else "A LABADDA_ setting has a value of the wrong kind"
        )
        return None, CheckResult(
            "configuration", title, "fail", named, "Correct the setting in the site's environment file."
        )
    problems = configuration_problems(settings)
    if problems:
        return settings, CheckResult(
            "configuration",
            title,
            "fail",
            "; ".join(problems) + ".",
            "Edit the site's environment file (see deploy/labadda.env.example) and restart the service.",
        )
    return settings, CheckResult("configuration", title, "pass", "All settings are present and valid.")


def check_database(host: Host, settings: Settings) -> CheckResult:
    """The database answers and its schema is the one this release expects."""
    title = "Database"
    state = host.database(settings.database_url)
    if not state.reachable:
        return CheckResult(
            "database",
            title,
            "fail",
            "The database did not answer.",
            "Check that PostgreSQL is running and that the address, name, user and password in "
            "LABADDA_DATABASE_URL are right.",
        )
    if state.revision is None:
        return CheckResult(
            "database",
            title,
            "fail",
            "The database answers but has not been set up for LabAdda.",
            "Run `labadda migrate` for a new site, or point LABADDA_DATABASE_URL at the right database.",
        )
    expected = host.release_schema()
    if state.revision != expected:
        return CheckResult(
            "database",
            title,
            "fail",
            "The database layout does not match this release.",
            "Finish the upgrade (`labadda migrate`) or switch back to the matching release; "
            "see the upgrade steps in docs/OPERATOR-QUICKSTART.md.",
        )
    return CheckResult("database", title, "pass", "The database answers and matches this release.")


def check_assets(host: Host, settings: Settings) -> CheckResult:
    """The asset directory exists, can be written by this account, and has room to grow."""
    title = "Uploaded files"
    directory = settings.asset_dir
    create_hint = "Create the folder, give the service account write access, and set LABADDA_ASSET_DIR to it."
    free = host.free_bytes(directory)
    if free is None:
        return CheckResult(
            "assets", title, "fail", "The folder for uploaded files does not exist.", create_hint
        )
    if not host.can_write(directory):
        return CheckResult(
            "assets",
            title,
            "fail",
            "The folder for uploaded files cannot be written by this account.",
            "Run doctor as the service account, or give that account write access to the folder.",
        )
    if free < host.reserve_bytes:
        return CheckResult(
            "assets",
            title,
            "fail",
            f"Only {human_size(free)} is free; at least {human_size(host.reserve_bytes)} is needed.",
            "Free disk space or move the folder to a larger disk before people upload more.",
        )
    return CheckResult(
        "assets",
        title,
        "pass",
        f"The folder can be written and {human_size(free)} is free.",
    )


def _port(host: Host) -> int | None:
    try:
        port = int(host.environ.get("LABADDA_PORT", ""))
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


def _health_answer(host: Host, origin: str, prefix: str) -> FetchState:
    """Ask both the liveness and readiness addresses; the first problem is the answer."""
    for endpoint, expected in (("healthz", "ok"), ("readyz", "ready")):
        state = host.fetch(f"{origin}{prefix}/{endpoint}", expected)
        if state.kind != "ok":
            return state
    return FetchState("ok")


def check_service(host: Host, settings: Settings) -> CheckResult:
    """The application answers on its own port at the configured prefix."""
    title = "Service"
    port = _port(host)
    if port is None:
        return _skipped(
            "service", title, "Not checked: the service port is unknown. Run again with --port <port>."
        )
    state = _health_answer(host, f"http://127.0.0.1:{port}", settings.base_path)
    if state.kind == "ok":
        return CheckResult("service", title, "pass", "The service is running and ready.")
    return CheckResult(
        "service",
        title,
        "fail",
        "The service did not give a healthy answer on its own port.",
        "Start it with `systemctl start labadda-<site-name>`, then read its log with "
        "`journalctl -u labadda-<site-name>`. Check LABADDA_BASE_PATH matches the proxy.",
    )


def check_proxy(host: Host, settings: Settings) -> CheckResult:
    """The address people use reaches the service at the configured prefix."""
    title = "Address people use"
    if not settings.trusted_origins:
        return _skipped("proxy", title, "Not checked: no address is configured in LABADDA_TRUSTED_ORIGINS.")
    state = _health_answer(host, settings.trusted_origins[0], settings.base_path)
    if state.kind == "ok":
        return CheckResult("proxy", title, "pass", "The address people use reaches the service.")
    if state.kind == "untrusted":
        return CheckResult(
            "proxy",
            title,
            "fail",
            "The address people use did not complete a secure connection.",
            "See the Secure connection result below.",
        )
    return CheckResult(
        "proxy",
        title,
        "fail",
        "The address people use did not reach a healthy service.",
        "Check the web server (proxy) is running, its prefix matches LABADDA_BASE_PATH, and that "
        "maintenance mode is not switched on.",
    )


def check_tls(host: Host, settings: Settings) -> CheckResult:
    """When the site uses HTTPS: cookies are secure and the certificate is trusted and not expiring."""
    title = "Secure connection"
    secure = [origin for origin in settings.trusted_origins if origin.startswith("https://")]
    if not secure:
        if settings.environment in SITE_ENVIRONMENTS:
            return CheckResult(
                "tls",
                title,
                "fail",
                "The site address does not use HTTPS.",
                "Set up a certificate and list the https:// address in LABADDA_TRUSTED_ORIGINS.",
            )
        return _skipped("tls", title, "Not in use: no https:// address is configured.")
    if not settings.cookie_secure:
        return CheckResult(
            "tls",
            title,
            "fail",
            "The site uses HTTPS but sign-in cookies are not marked secure.",
            "Set LABADDA_COOKIE_SECURE=true and restart the service.",
        )
    parts = urlsplit(secure[0])
    state = host.certificate(parts.hostname or "", parts.port or 443, host.now())
    if state.kind != "ok" or state.days_left is None:
        reason = "is not trusted by this computer" if state.kind == "untrusted" else "could not be reached"
        return CheckResult(
            "tls",
            title,
            "fail",
            f"The site's certificate {reason}.",
            "Install the site's certificate authority on this computer and check the web server "
            "is running with the certificate files in place.",
        )
    if state.days_left < CERTIFICATE_WARN_DAYS:
        return CheckResult(
            "tls",
            title,
            "fail",
            f"The certificate expires in {max(state.days_left, 0)} days.",
            "Renew the certificate and reload the web server.",
        )
    return CheckResult(
        "tls", title, "pass", f"The certificate is trusted and valid for {state.days_left} more days."
    )


def _hours(age_seconds: float) -> str:
    hours = int(age_seconds // 3600)
    return "less than an hour ago" if hours < 1 else f"{hours} hours ago"


def check_backup(host: Host, settings: Settings) -> CheckResult:
    """A recent, verified backup is recorded in the status file."""
    title = "Backups"
    if settings.environment not in SITE_ENVIRONMENTS:
        return _skipped("backup", title, "Not required for development or test use.")
    setup_hint = "Set up the nightly backup timer (docs/OPERATOR-QUICKSTART.md, step 4)."
    if settings.status_dir is None:
        return CheckResult(
            "backup",
            title,
            "fail",
            "No backup status folder is configured.",
            "Set LABADDA_STATUS_DIR. " + setup_hint,
        )
    reading = backup_status.read_status(settings.status_dir)
    if reading.state == "unknown":
        return CheckResult("backup", title, "fail", "No backup has been recorded yet.", setup_hint)
    if reading.status is None:
        return CheckResult(
            "backup",
            title,
            "fail",
            "The backup status file cannot be read.",
            "Run the backup again; if this persists the file was edited or damaged.",
        )
    status = reading.status
    elapsed = backup_status.age(status, host.now())
    if status.result != "success":
        return CheckResult(
            "backup",
            title,
            "fail",
            f"The last backup, {_hours(elapsed.total_seconds())}, failed.",
            "Read the backup log with `journalctl -u labadda-backup@<site-name>` and run it again.",
        )
    if elapsed < -backup_status.FUTURE_TOLERANCE:
        return CheckResult(
            "backup",
            title,
            "fail",
            "The last backup is dated in the future.",
            "Check this computer's clock and time zone settings.",
        )
    if elapsed > backup_status.FRESH_WITHIN:
        return CheckResult(
            "backup",
            title,
            "fail",
            f"The last good backup is old: {_hours(elapsed.total_seconds())}.",
            "Check the backup timer with `systemctl list-timers` and run a backup now.",
        )
    size = human_size(status.size_bytes or 0)
    return CheckResult(
        "backup",
        title,
        "pass",
        f"The last backup finished {_hours(elapsed.total_seconds())} ({size}, verified).",
    )


def check_timezone(host: Host) -> CheckResult:
    """The configured time zone is a real, installed one."""
    title = "Time zone"
    name = host.environ.get("LABADDA_TIMEZONE", "UTC")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return CheckResult(
            "timezone",
            title,
            "fail",
            "LABADDA_TIMEZONE is not an installed time zone.",
            "Use a name such as Europe/London or UTC, exactly as listed by `timedatectl list-timezones`.",
        )
    return CheckResult("timezone", title, "pass", "The time zone is valid.")


def run_checks(host: Host) -> list[CheckResult]:
    """Run every check in a fixed order; checks that need valid settings are skipped without them."""
    settings, configuration = check_configuration(host)
    results = [configuration]
    needing_settings = (
        ("database", "Database", check_database),
        ("assets", "Uploaded files", check_assets),
        ("service", "Service", check_service),
        ("proxy", "Address people use", check_proxy),
        ("tls", "Secure connection", check_tls),
        ("backup", "Backups", check_backup),
    )
    for check_id, title, check in needing_settings:
        results.append(_blocked(check_id, title) if settings is None else check(host, settings))
    results.append(check_timezone(host))
    return results


def passed(results: list[CheckResult]) -> bool:
    """Doctor succeeds only when nothing failed."""
    return all(result.status != "fail" for result in results)


def as_report(results: list[CheckResult], now: datetime) -> dict:
    """The machine-readable report printed by `--json`."""
    return {
        "format": 1,
        "checked_at": now.astimezone(UTC).strftime(backup_status.TIME_FORMAT),
        "passed": passed(results),
        "checks": [result.as_record() for result in results],
    }


def format_report(results: list[CheckResult]) -> str:
    """The plain-text report for a person at a terminal."""
    labels = {"pass": "OK  ", "fail": "FAIL", "skip": "skip"}
    lines = []
    for result in results:
        lines.append(f"[{labels[result.status]}] {result.title}: {result.summary}")
        if result.status == "fail" and result.fix:
            lines.append(f"       To fix: {result.fix}")
    failed = sum(result.status == "fail" for result in results)
    lines.append("")
    lines.append("Everything checked is healthy." if not failed else f"{failed} check(s) need attention.")
    return "\n".join(lines)


def live_host(environ: Mapping[str, str] | None = None, *, port: int | None = None) -> Host:
    """The host for a real run: the process environment plus an optional port override."""
    values = dict(os.environ if environ is None else environ)
    if port is not None:
        values["LABADDA_PORT"] = str(port)
    return Host(environ=values)
