"""Runtime configuration read from environment variables.

Every setting has a disposable development default. Staging and pilot
instances supply their own values through an operator-owned environment file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _normalize_base(path: str) -> str:
    path = (path or "").strip()
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql+psycopg://labadd:labadd-dev@localhost:5432/labadd_dev"
    base_path: str = ""
    instance: str = "dev"
    environment: str = "development"  # development | test | staging | pilot
    cookie_name: str = "labadd_session"
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
    extra: dict = field(default_factory=dict)

    @property
    def api_prefix(self) -> str:
        return f"{self.base_path}/api/v1"

    @property
    def cookie_path(self) -> str:
        return self.base_path or "/"

    @property
    def fixtures_allowed(self) -> bool:
        return self.environment in {"development", "test"}


def load_settings() -> Settings:
    env = os.environ.get
    dist = env("LABADD_FRONTEND_DIST")
    default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    origins = tuple(o.strip().rstrip("/") for o in (env("LABADD_TRUSTED_ORIGINS") or "").split(",") if o.strip())
    return Settings(
        database_url=env("LABADD_DATABASE_URL", Settings.database_url),
        base_path=_normalize_base(env("LABADD_BASE_PATH", "")),
        instance=env("LABADD_INSTANCE", "dev"),
        environment=env("LABADD_ENV", "development"),
        cookie_name=env("LABADD_COOKIE_NAME", "labadd_session"),
        cookie_secure=_bool(env("LABADD_COOKIE_SECURE"), False),
        trusted_origins=origins,
        asset_dir=Path(env("LABADD_ASSET_DIR", "var/assets")),
        frontend_dist=Path(dist) if dist else (default_dist if default_dist.exists() else None),
        timezone=env("LABADD_TIMEZONE", "UTC"),
        session_idle_minutes=int(env("LABADD_SESSION_IDLE_MINUTES", "120")),
        session_absolute_hours=int(env("LABADD_SESSION_ABSOLUTE_HOURS", "12")),
        max_attachments=int(env("LABADD_MAX_ATTACHMENTS", "5")),
        max_attachment_bytes=int(env("LABADD_MAX_ATTACHMENT_BYTES", str(20 * 1024 * 1024))),
        user_quota_bytes=int(env("LABADD_USER_QUOTA_BYTES", str(500 * 1024 * 1024))),
        run_scheduler=_bool(env("LABADD_RUN_SCHEDULER"), True),
        reminder_interval_seconds=int(env("LABADD_REMINDER_INTERVAL_SECONDS", "30")),
        max_groups_per_user=int(env("LABADD_MAX_GROUPS_PER_USER", "20")),
        max_group_members=int(env("LABADD_MAX_GROUP_MEMBERS", "200")),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
