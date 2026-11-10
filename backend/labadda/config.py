"""Runtime configuration read from environment variables.

Every setting has a disposable development default. Staging and pilot
instances supply their own values through an operator-owned environment file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _normalize_base(path: str) -> str:
    path = (path or "").strip()
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


def _positive(value: str, name: str) -> int:
    number = int(value)
    if number < 1:
        raise ValueError(f"{name} must be a positive integer")
    return number


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql+psycopg://labadda:labadda-dev@localhost:5432/labadda_dev"
    base_path: str = ""
    instance: str = "dev"
    environment: str = "development"  # development | test | staging | pilot
    cookie_name: str = "labadda_session"
    cookie_secure: bool = False
    trusted_origins: tuple[str, ...] = ()
    asset_dir: Path = Path("var/assets")
    frontend_dist: Path | None = None
    timezone: str = "UTC"
    session_idle_minutes: int = 120
    session_absolute_hours: int = 12
    activation_hours: int = 72
    max_attachments: int = 5
    max_attachment_bytes: int = 20 * 1024 * 1024
    user_quota_bytes: int = 500 * 1024 * 1024
    provisional_upload_hours: int = 6
    login_attempts_per_window: int = 10
    login_window_seconds: int = 300
    reminder_interval_seconds: int = 30
    run_scheduler: bool = True
    max_groups_per_user: int = 20
    max_group_members: int = 200
    panel_idle_seconds: int = 300  # board-only panel locks after this much inactivity
    panel_absolute_minutes: int = 60  # hard expiry of a board-only panel session
    panel_pairing_seconds: int = 120  # lifetime of a one-time panel pairing code
    board_compact_threshold: int = 2000  # compact when a board has this many uncompacted revisions
    board_keep_revisions: int = 500  # recent revisions kept for undo, restore and replay
    extra: dict = field(default_factory=dict)

    @property
    def api_prefix(self) -> str:
        return f"{self.base_path}/api/v1"

    @property
    def panel_cookie_name(self) -> str:
        return f"{self.cookie_name}_panel"

    @property
    def cookie_path(self) -> str:
        return self.base_path or "/"

    @property
    def fixtures_allowed(self) -> bool:
        return self.environment in {"development", "test"}


def _timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError('LABADDA_TIMEZONE must name an installed IANA timezone') from error
    return value


def load_settings() -> Settings:
    env = os.environ.get
    dist = env("LABADDA_FRONTEND_DIST")
    default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    origins = tuple(o.strip().rstrip("/") for o in (env("LABADDA_TRUSTED_ORIGINS") or "").split(",") if o.strip())
    return Settings(
        database_url=env("LABADDA_DATABASE_URL", Settings.database_url),
        base_path=_normalize_base(env("LABADDA_BASE_PATH", "")),
        instance=env("LABADDA_INSTANCE", "dev"),
        environment=env("LABADDA_ENV", "development"),
        cookie_name=env("LABADDA_COOKIE_NAME", "labadda_session"),
        cookie_secure=_bool(env("LABADDA_COOKIE_SECURE"), False),
        trusted_origins=origins,
        asset_dir=Path(env("LABADDA_ASSET_DIR", "var/assets")),
        frontend_dist=Path(dist) if dist else (default_dist if default_dist.exists() else None),
        timezone=_timezone(env("LABADDA_TIMEZONE", "UTC")),
        session_idle_minutes=int(env("LABADDA_SESSION_IDLE_MINUTES", "120")),
        session_absolute_hours=int(env("LABADDA_SESSION_ABSOLUTE_HOURS", "12")),
        max_attachments=int(env("LABADDA_MAX_ATTACHMENTS", "5")),
        max_attachment_bytes=int(env("LABADDA_MAX_ATTACHMENT_BYTES", str(20 * 1024 * 1024))),
        user_quota_bytes=int(env("LABADDA_USER_QUOTA_BYTES", str(500 * 1024 * 1024))),
        run_scheduler=_bool(env("LABADDA_RUN_SCHEDULER"), True),
        reminder_interval_seconds=int(env("LABADDA_REMINDER_INTERVAL_SECONDS", "30")),
        max_groups_per_user=int(env("LABADDA_MAX_GROUPS_PER_USER", "20")),
        max_group_members=int(env("LABADDA_MAX_GROUP_MEMBERS", "200")),
        # Sign-in/activation/pairing attempts per client and window. Operators may raise this
        # temporarily for a supervised load rehearsal; it is never relaxed by web policy.
        login_attempts_per_window=_positive(env("LABADDA_LOGIN_ATTEMPTS_PER_WINDOW", "10"), "LABADDA_LOGIN_ATTEMPTS_PER_WINDOW"),
        login_window_seconds=_positive(env("LABADDA_LOGIN_WINDOW_SECONDS", "300"), "LABADDA_LOGIN_WINDOW_SECONDS"),
        board_compact_threshold=int(env("LABADDA_BOARD_COMPACT_THRESHOLD", "2000")),
        panel_idle_seconds=int(env("LABADDA_PANEL_IDLE_SECONDS", "300")),
        panel_absolute_minutes=int(env("LABADDA_PANEL_ABSOLUTE_MINUTES", "60")),
        panel_pairing_seconds=int(env("LABADDA_PANEL_PAIRING_SECONDS", "120")),
        board_keep_revisions=int(env("LABADDA_BOARD_KEEP_REVISIONS", "500")),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
