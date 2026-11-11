"""The common result shape of every health item (AD-03, AD-07) and the context items read from."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..metrics.registry import REGISTRY, Registry
from ..security import utcnow
from .heartbeat import HEARTBEAT, Heartbeat
from .proc import Proc

STATUSES = ("healthy", "degraded", "unavailable", "stale", "unknown", "unsupported")
# The overall state is the worst item state, ignoring "unsupported" (AD-03). Missing or old data
# ranks above healthy so that it is never mistaken for it.
RANK = {"unsupported": -1, "healthy": 0, "unknown": 1, "stale": 2, "degraded": 3, "unavailable": 4}
PROBLEMS = ("degraded", "unavailable", "stale")


@dataclass(frozen=True)
class Result:
    """What one item found: a status word, a headline figure, and a plain sentence."""

    status: str
    value: float | str | None
    unit: str
    detail: str
    checked_at: datetime

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "value": self.value,
            "unit": self.unit,
            "detail": self.detail,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass(frozen=True)
class DiskReading:
    free_bytes: int
    total_bytes: int
    free_inodes: int
    total_inodes: int


def read_disk(path: Path) -> DiskReading:
    """Free space and inodes of the volume that holds ``path``; raises OSError when unreadable."""
    usage = shutil.disk_usage(path)
    stats = os.statvfs(path)
    return DiskReading(usage.free, usage.total, stats.f_favail, stats.f_files)


@dataclass
class Context:
    """Everything an item may read; tests replace the readers with injected figures."""

    settings: Settings
    factory: sessionmaker[Session]
    started: datetime
    expected_schema: Callable[[], str]
    now: Callable[[], datetime] = utcnow
    sockets: Callable[[], int] = lambda: 0
    backlog: Callable[[], int] = lambda: 0
    registry: Registry = REGISTRY
    heartbeat: Heartbeat = HEARTBEAT
    proc: Proc = field(default_factory=Proc)
    disk: Callable[[Path], DiskReading] = read_disk


def worst(statuses: list[str]) -> str:
    """The overall word for a set of item words; unknown when nothing can be judged."""
    judged = [status for status in statuses if status != "unsupported"]
    return max(judged, key=RANK.__getitem__) if judged else "unknown"


def human_bytes(number: float) -> str:
    size = float(number)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_duration(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    if seconds < 90:
        return f"{seconds} seconds"
    if seconds < 5400:
        return f"{round(seconds / 60)} minutes"
    if seconds < 172800:
        return f"{round(seconds / 3600)} hours"
    return f"{round(seconds / 86400)} days"


def make(ctx: Context, status: str, value: float | str | None, unit: str, detail: str) -> Result:
    return Result(status, value, unit, detail, ctx.now())
