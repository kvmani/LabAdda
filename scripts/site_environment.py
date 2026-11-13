"""Read and validate the operator-owned runtime environment file of an installed site.

Only a strict allowlist of unquoted `KEY=value` lines is accepted, and the values must match the
reviewed site configuration. Standard library only.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

import operations

TLS_ENV = {"PGSSLMODE", "PGSSLROOTCERT", "PGSSLCERT", "PGSSLKEY"}

ALLOWED_ENV = {
    "PORT",
    "FRONTEND_DIST",
    "TRUSTED_ORIGINS",
    "DATABASE_URL",
    "BASE_PATH",
    "INSTANCE",
    "ENV",
    "COOKIE_NAME",
    "COOKIE_SECURE",
    "ASSET_DIR",
    "TIMEZONE",
    "SESSION_IDLE_MINUTES",
    "SESSION_ABSOLUTE_HOURS",
    "MAX_ATTACHMENTS",
    "MAX_ATTACHMENT_BYTES",
    "USER_QUOTA_BYTES",
    "RUN_SCHEDULER",
    "REMINDER_INTERVAL_SECONDS",
    "MAX_GROUPS_PER_USER",
    "MAX_GROUP_MEMBERS",
    "LOGIN_ATTEMPTS_PER_WINDOW",
    "LOGIN_WINDOW_SECONDS",
    "BOARD_COMPACT_THRESHOLD",
    "PANEL_IDLE_SECONDS",
    "PANEL_ABSOLUTE_MINUTES",
    "PANEL_PAIRING_SECONDS",
    "BOARD_KEEP_REVISIONS",
    "STATUS_DIR",
    "BULK_CHANGE_SECONDS",
    "EMAIL_DOMAIN",
    "METRICS_FLUSH_SECONDS",
    "METRICS_MINUTE_RETENTION_HOURS",
    "METRICS_HOUR_RETENTION_DAYS",
    "METRICS_DAY_RETENTION_DAYS",
    "ACTIVITY_RETENTION_DAYS",
    "HEALTH_SAMPLE_SECONDS",
    "HEALTH_STALE_SECONDS",
    "HEALTH_DB_SLOW_MS",
    "HEALTH_DB_CONNECTIONS_PERCENT",
    "HEALTH_DISK_RESERVE_BYTES",
    "HEALTH_INODE_RESERVE_PERCENT",
    "HEALTH_QUEUE_BACKLOG",
    "HEALTH_JOB_STALL_DEGRADED_SECONDS",
    "HEALTH_JOB_STALL_UNAVAILABLE_SECONDS",
    "HEALTH_JOB_FAILURES_PER_HOUR",
    "HEALTH_RESPONSE_P95_MS",
    "HEALTH_ERROR_RATE_PERCENT",
    "HEALTH_SIGNIN_FAILURE_PERCENT",
    "HEALTH_BACKUP_FRESH_HOURS",
    "HEALTH_BACKUP_STALE_HOURS",
    "HEALTH_CERTIFICATE_DEGRADED_DAYS",
    "HEALTH_CERTIFICATE_UNAVAILABLE_DAYS",
    "HEALTH_CERTIFICATE_FRESH_HOURS",
    "HEALTH_PROCESS_MEMORY_MB",
    "HEALTH_LOAD_PER_CPU_X10",
    "HEALTH_HOST_MEMORY_PERCENT",
    "FEEDBACK_EMAIL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_STARTTLS",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_PASSWORD_FILE",
    "SMTP_FROM",
}


def runtime_environment(site: dict) -> dict:
    path = Path(site["env_file"])
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid not in (0, os.geteuid()):
        raise operations.OperationsError(
            "Environment file must be operator-owned regular mode0600 or stricter"
        )
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if (
            not sep
            or (key not in TLS_ENV and (not key.startswith("LABADDA_") or key[8:] not in ALLOWED_ENV))
            or key in values
            or any(c.isspace() or c in "'\"\\" or ord(c) < 32 for c in value)
        ):
            raise operations.OperationsError(
                "Environment requires unique allowlisted unquoted KEY=value lines"
            )
        values[key] = value
    required = {
        "LABADDA_INSTANCE": site["instance"],
        "LABADDA_PORT": str(site["port"]),
        "LABADDA_BASE_PATH": site["base_path"],
        "LABADDA_ASSET_DIR": site["root"] + "/assets",
        "LABADDA_FRONTEND_DIST": site["root"] + "/current/frontend/dist",
        "LABADDA_COOKIE_SECURE": "true",
        "LABADDA_TRUSTED_ORIGINS": "https://" + site["server_name"],
    }
    # The generated unit passes the port explicitly; the environment need not repeat it.
    if "LABADDA_PORT" not in values:
        required.pop("LABADDA_PORT")
    if (
        any(values.get(k) != v for k, v in required.items())
        or values.get("LABADDA_ENV") not in ("staging", "pilot")
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", values.get("LABADDA_COOKIE_NAME", ""))
        or values.get("LABADDA_COOKIE_NAME") == "labadda_session"
        or not values.get("LABADDA_DATABASE_URL", "").startswith("postgresql+psycopg://")
    ):
        raise operations.OperationsError(
            "Runtime environment does not match the reviewed site/TLS/storage contract"
        )
    if any(key in values for key in TLS_ENV):
        if values.get("PGSSLMODE") != "verify-full" or not values.get("PGSSLROOTCERT", "").startswith("/"):
            raise operations.OperationsError("PostgreSQL TLS requires verify-full and an explicit CA file")
        for key in TLS_ENV - {"PGSSLMODE"}:
            if key in values and not Path(values[key]).is_absolute():
                raise operations.OperationsError("PostgreSQL TLS files require absolute paths")
        if ("PGSSLCERT" in values) != ("PGSSLKEY" in values):
            raise operations.OperationsError(
                "PostgreSQL client certificate and key must be configured together"
            )
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", **values}
