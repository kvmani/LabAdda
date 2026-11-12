"""The six Overview tiles and the two 7-day charts, each with its state word (AD-03, AD-04).

People figures follow the Activity page's floor: fewer than five is ``suppressed`` and the number
is never sent, so this page can never reveal what the Activity page hides. Missing readings are
``unknown`` and old ones ``stale``, never zero.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import backup_report
from ..analytics import samples
from ..analytics.features import CONNECTIONS, STORAGE
from ..analytics.periods import Window
from ..analytics.protect import MIN_GROUP
from ..config import Settings
from ..models import MetricSample, OpsEvent

SESSIONS = "sessions.active"
LATENCY = "http.latency_p95"
# The collector writes gauges every minute; a reading this old no longer describes "now".
LIVE_FRESH = timedelta(minutes=5)
SIZE_FRESH = timedelta(minutes=15)


def _latest(db: Session, metric: str) -> tuple[float, datetime] | None:
    row = db.execute(
        select(MetricSample.value, MetricSample.bucket_start)
        .where(
            MetricSample.metric == metric,
            MetricSample.resolution == "minute",
            MetricSample.dimension == "",
        )
        .order_by(MetricSample.bucket_start.desc())
        .limit(1)
    ).first()
    return None if row is None else (float(row[0]), row[1])


def _tile(key: str, label: str, unit: str, link: str, *, state: str, value, trend, at=None, **more) -> dict:
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "link": link,
        "state": state,
        "value": value,
        "trend": trend,
        "updated_at": at.isoformat() if at else None,
        **more,
    }


def _days(window: Window) -> list[date]:
    return [window.first + timedelta(days=n) for n in range(window.days)]


def _trend(found: dict, window: Window, metrics: tuple[str, ...], *, floor: bool = False) -> list:
    """One value per day, null where the day was not measured (or, with ``floor``, was under five)."""
    out = []
    for day in _days(window):
        values = [found.get((day, metric, "")) for metric in metrics]
        total = None if any(v is None for v in values) else sum(values)
        out.append(None if total is None or (floor and total < MIN_GROUP) else total)
    return out


def _live(reading, now: datetime, fresh: timedelta) -> tuple[str, float | None, datetime | None]:
    if reading is None:
        return "unknown", None, None
    value, at = reading
    return ("measured" if now - at <= fresh else "stale"), value, at


def build_tiles(
    db: Session, settings: Settings, window: Window, summary: dict, *, health: dict[str, dict], now: datetime
) -> list[dict]:
    gauges = (SESSIONS, CONNECTIONS, *(metric for metric, _ in STORAGE))
    found = samples.daily(db, gauges, window, peak=True)
    charts = summary.get("charts")
    active = next((tile for tile in summary["tiles"] if tile["key"] == "active_day"), None)
    people_trend = [point["value"] for point in charts["active_per_day"]] if charts else [None] * window.days

    word, sessions, at = _live(_latest(db, SESSIONS), now, LIVE_FRESH)
    if sessions is not None and sessions < MIN_GROUP:
        word, sessions = "suppressed", None
    word_c, sockets, at_c = _live(_latest(db, CONNECTIONS), now, LIVE_FRESH)
    sizes = [_latest(db, metric) for metric, _ in STORAGE]
    if any(size is None for size in sizes):
        word_s, total, at_s = "unknown", None, None
    else:
        word_s, _, at_s = _live(min(sizes, key=lambda pair: pair[1]), now, SIZE_FRESH)
        total = sum(size[0] for size in sizes)

    report = backup_report.backup_report(settings, now)
    last = report["last_backup"]
    backup_word = health["backups"]["status"] if "backups" in health else report["status"]

    return [
        _tile(
            "active_today",
            "People active today",
            "people",
            "/admin/activity",
            state=active["state"] if active else "unknown",
            value=active["value"] if active else None,
            trend=people_trend,
        ),
        _tile(
            "signed_in_now",
            "Signed in now",
            "people",
            "/admin/activity",
            state=word,
            value=sessions,
            trend=_trend(found, window, (SESSIONS,), floor=True),
            at=at,
        ),
        _tile(
            "connected_now",
            "Connected now",
            "connections",
            "/admin/health",
            state=word_c,
            value=sockets,
            trend=_trend(found, window, (CONNECTIONS,)),
            at=at_c,
        ),
        _tile(
            "storage_used",
            "Storage used",
            "bytes",
            "/admin/storage",
            state=word_s,
            value=total,
            trend=_trend(found, window, tuple(metric for metric, _ in STORAGE)),
            at=at_s,
        ),
        _tile(
            "last_backup",
            "Last backup",
            "seconds",
            "/admin/backups",
            state=backup_word,
            value=last["age_seconds"] if last else None,
            trend=None,
            finished_at=last["finished_at"] if last else None,
        ),
        _open_events_tile(db, settings.timezone, window),
    ]


def _open_events_tile(db: Session, timezone: str, window: Window) -> dict:
    by_severity = dict(
        db.execute(
            select(OpsEvent.severity, func.count())
            .where(OpsEvent.state == "open")
            .group_by(OpsEvent.severity)
        ).all()
    )
    day = samples.site_day(OpsEvent.first_at, timezone)
    raised = dict(
        db.execute(
            select(day, func.count())
            .where(OpsEvent.first_at >= window.start, OpsEvent.first_at < window.end)
            .group_by(day)
        ).all()
    )
    return _tile(
        "open_events",
        "Open events",
        "events",
        "/admin/events?state=open",
        state="measured",
        value=sum(by_severity.values()),
        trend=[raised.get(day, 0) for day in _days(window)],
        by_severity={name: by_severity.get(name, 0) for name in ("critical", "error", "warning", "info")},
    )


def build_charts(db: Session, window: Window, summary: dict) -> dict:
    """Daily people active (already floored by the Activity page) and the slowest p95 each day."""
    points = summary["charts"]["active_per_day"] if summary.get("charts") else []
    states = {point["state"] for point in points}
    shown = "measured" if "measured" in states else "suppressed" if "suppressed" in states else "unknown"
    activity = {"state": shown, "points": points}
    latency = samples.daily(db, (LATENCY,), window, peak=True)
    slow = []
    for day in _days(window):
        value = latency.get((day, LATENCY, "all"))
        slow.append(
            {"day": day.isoformat(), "state": "unknown" if value is None else "measured", "value": value}
        )
    word = "measured" if any(point["value"] is not None for point in slow) else "unknown"
    return {"activity": activity, "response_time": {"state": word, "unit": "ms", "points": slow}}
