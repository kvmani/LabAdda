"""The read-only settings page (AD-10, A7): effective non-secret limits in plain words.

Only values that are safe to show are listed, one explicit row at a time. Paths, host names,
database addresses, cookie names and anything credential-like are never read here, so a new
setting cannot appear on screen by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings

CHANGED_BY = "Changed by the operator in the site configuration file."


@dataclass(frozen=True)
class Row:
    field: str
    label: str
    unit: str
    explanation: str


@dataclass(frozen=True)
class Group:
    key: str
    title: str
    summary: str
    rows: tuple[Row, ...]


GROUPS = (
    Group(
        "site",
        "This site",
        "How this installation tells time and what kind of installation it is.",
        (
            Row("timezone", "Site time zone", "", "Days, reports and schedules follow this time zone."),
            Row("environment", "Kind of installation", "", "Development, test, staging or pilot."),
        ),
    ),
    Group(
        "sign_in",
        "Signing in",
        "How long people stay signed in and how many wrong attempts are allowed.",
        (
            Row(
                "session_idle_minutes",
                "Sign out after being idle",
                "minutes",
                "Idle time before sign-in is needed again.",
            ),
            Row(
                "session_absolute_hours",
                "Longest sign-in",
                "hours",
                "Nobody stays signed in longer than this.",
            ),
            Row(
                "activation_hours",
                "Activation and reset link lifetime",
                "hours",
                "How long a new link works.",
            ),
            Row(
                "login_attempts_per_window",
                "Sign-in attempts allowed",
                "attempts",
                "Attempts per waiting period before a pause.",
            ),
            Row(
                "login_window_seconds",
                "Sign-in waiting period",
                "seconds",
                "The period in which attempts are counted.",
            ),
        ),
    ),
    Group(
        "panels",
        "Shared board screens",
        "Limits for whiteboard screens that are not signed in as a person.",
        (
            Row(
                "panel_idle_seconds",
                "Lock after being idle",
                "seconds",
                "A shared screen locks when nobody touches it.",
            ),
            Row(
                "panel_absolute_minutes",
                "Longest session",
                "minutes",
                "A shared screen session always ends after this.",
            ),
            Row(
                "panel_pairing_seconds",
                "Pairing code lifetime",
                "seconds",
                "How long a one-time pairing code works.",
            ),
        ),
    ),
    Group(
        "files",
        "Files and storage",
        "How much each person may upload.",
        (
            Row(
                "max_attachments",
                "Files per message or post",
                "files",
                "The most files that can be attached at once.",
            ),
            Row("max_attachment_bytes", "Largest single file", "bytes", "Bigger files are refused."),
            Row("user_quota_bytes", "Storage per person", "bytes", "The most one person can keep."),
            Row(
                "provisional_upload_hours",
                "Unattached upload lifetime",
                "hours",
                "Uploads not used in this time are set aside.",
            ),
        ),
    ),
    Group(
        "work",
        "Groups and whiteboards",
        "Limits that keep shared work quick.",
        (
            Row(
                "max_groups_per_user",
                "Groups per person",
                "groups",
                "Private groups one person may belong to.",
            ),
            Row("max_group_members", "People per group", "people", "The largest private group."),
            Row(
                "board_compact_threshold",
                "Whiteboard tidy-up point",
                "changes",
                "Whiteboard history is tidied after this many changes.",
            ),
            Row(
                "board_keep_revisions",
                "Whiteboard changes kept for undo",
                "changes",
                "Recent changes kept so undo and restore work.",
            ),
            Row(
                "reminder_interval_seconds",
                "Reminder check interval",
                "seconds",
                "How often due reminders are looked for.",
            ),
        ),
    ),
    Group(
        "history",
        "Usage history",
        "How long figures behind the console charts are kept.",
        (
            Row(
                "metrics_flush_seconds",
                "Figures saved every",
                "seconds",
                "How often new figures are written.",
            ),
            Row(
                "metrics_minute_retention_hours",
                "Minute figures kept",
                "hours",
                "Detailed figures are kept this long.",
            ),
            Row(
                "metrics_hour_retention_days",
                "Hourly figures kept",
                "days",
                "Hourly summaries are kept this long.",
            ),
            Row(
                "metrics_day_retention_days",
                "Daily figures kept",
                "days",
                "Daily summaries are kept this long.",
            ),
            Row(
                "activity_retention_days",
                "Daily activity kept",
                "days",
                "Counts of active days per person are kept this long.",
            ),
        ),
    ),
)


def settings_groups(settings: Settings) -> list[dict]:
    """Return the grouped, explained settings; every row says who changes it."""
    groups = [
        {
            "key": group.key,
            "title": group.title,
            "summary": group.summary,
            "items": [
                {
                    "key": row.field,
                    "label": row.label,
                    "value": getattr(settings, row.field),
                    "unit": row.unit,
                    "explanation": row.explanation,
                    "changed_by": CHANGED_BY,
                }
                for row in group.rows
            ],
        }
        for group in GROUPS
    ]
    groups[0]["items"].append(
        {
            "key": "backup_status",
            "label": "Backup receipts available",
            "value": "configured" if settings.status_dir is not None else "not configured",
            "unit": "",
            "explanation": "Whether the server has been told where backup receipts are kept.",
            "changed_by": CHANGED_BY,
        }
    )
    return groups
