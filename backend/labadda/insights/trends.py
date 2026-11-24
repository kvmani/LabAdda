"""Feature momentum: weekly use of each feature, how it is changing, and what that suggests.

Built only from the same stored counters and activity days as the Activity page, so it shows
counts, never content. A week in which fewer than ``MIN_GROUP`` people were active is
``suppressed`` and a week with no stored samples is ``unknown``; neither contributes numbers to
the momentum figures, which compare the most recent complete weeks with the ones before.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..analytics import samples
from ..analytics.charts import state
from ..analytics.features import FEATURES, KINDS
from ..analytics.periods import Window
from ..analytics.protect import MIN_GROUP
from ..config import Settings
from ..people import site_date
from ..serialize import iso

HORIZONS = (8, 12, 26, 52)
# Momentum compares the last COMPARE complete weeks with the COMPARE weeks before them.
COMPARE = 4
# Fewer measured weeks than this on either side cannot say whether use is changing.
MIN_MEASURED = 2
# A change smaller than this (as a fraction) is "steady": weekly use is noisy on small sites.
CHANGE_THRESHOLD = 0.2
# A steady feature with at least this share of all activity is a core feature.
CORE_SHARE = 0.25

ADVICE: dict[str, str] = {
    "growing": "Use is rising. Invest here: make it faster and easier to find.",
    "new": "Newly taken up. Watch it and help the first users.",
    "core": "A core feature that many rely on. Keep it reliable.",
    "steady": "Use is stable. No action needed.",
    "declining": "Use is falling. Ask people why, and check for problems or a better alternative.",
    "dormant": "Not used in recent weeks. A candidate to simplify, hide or retire.",
    "unused": "Not used in this period. Promote it, or consider retiring it.",
    "unknown": "Not enough measured weeks yet to judge.",
}


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def horizon_window(settings: Settings, weeks: int, *, now: datetime) -> Window:
    """Whole ISO weeks (Monday first) ending with the current, still running, week."""
    today = site_date(settings, now=now)
    first = week_start(today) - timedelta(weeks=weeks - 1)
    return Window(first, today, settings.timezone)


def _weekly(db: Session, window: Window) -> list[dict]:
    """One point per week: state, active people and per-feature totals when measured."""
    kinds = dict(KINDS)
    daily = samples.daily(db, tuple(metric for metric, _ in FEATURES), window)
    starts = [window.first + timedelta(weeks=n) for n in range((window.days + 6) // 7)]
    sums: dict[date, dict[str, float]] = {start: {} for start in starts}
    for (day, metric, dimension), value in daily.items():
        if dimension in kinds:
            bucket = sums.setdefault(week_start(day), {})
            bucket[metric] = bucket.get(metric, 0.0) + value
    seen = {week_start(day) for day in samples.sampled_days(db, window)}
    people = samples.active_per_bucket(db, window, "week")
    current = week_start(window.last)
    points = []
    for start in starts:
        active = people.get(start, 0)
        word = state(active, start in seen or start in people)
        measured = word == "measured"
        points.append(
            {
                "start": start.isoformat(),
                "partial": start == current,
                "state": word,
                "active_people": active if measured else None,
                "values": {key: sums[start].get(key, 0.0) for key, _ in FEATURES} if measured else None,
            }
        )
    return points


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if len(values) >= MIN_MEASURED else None


def classify(recent: float | None, prior: float | None, share: float) -> str:
    """Name the direction of use from the weekly means of the two compared spans."""
    if recent is None or prior is None:
        return "unknown"
    if prior == 0:
        return "unused" if recent == 0 else "new"
    if recent == 0:
        return "dormant"
    change = (recent - prior) / prior
    if change >= CHANGE_THRESHOLD:
        return "growing"
    if change <= -CHANGE_THRESHOLD:
        return "declining"
    return "core" if share >= CORE_SHARE else "steady"


def _spans(points: list[dict]) -> tuple[list[dict], list[dict]]:
    complete = [point for point in points if not point["partial"]]
    return complete[-COMPARE:], complete[-2 * COMPARE : -COMPARE]


def _momentum(points: list[dict]) -> list[dict]:
    recent_span, prior_span = _spans(points)
    recent_measured = [point for point in recent_span if point["values"] is not None]
    prior_measured = [point for point in prior_span if point["values"] is not None]
    recent_total = sum(sum(point["values"].values()) for point in recent_measured)
    rows = []
    for key, label in FEATURES:
        recent = _mean([point["values"][key] for point in recent_measured])
        prior = _mean([point["values"][key] for point in prior_measured])
        in_recent = sum(point["values"][key] for point in recent_measured)
        share = in_recent / recent_total if recent_total else 0.0
        trend = classify(recent, prior, share)
        people = _mean([float(point["active_people"]) for point in recent_measured])
        rows.append(
            {
                "key": key,
                "label": label,
                "trend": trend,
                "advice": ADVICE[trend],
                "weekly_recent": recent,
                "weekly_prior": prior,
                "change": (recent - prior) / prior if recent is not None and prior else None,
                "share": share if recent is not None else None,
                "per_person": recent / people if recent is not None and people else None,
                "sparkline": [None if point["values"] is None else point["values"][key] for point in points],
            }
        )
    order = list(ADVICE)
    rows.sort(key=lambda row: (order.index(row["trend"]), -(row["share"] or 0.0)))
    return rows


def _people(db: Session, points: list[dict], window: Window) -> dict:
    """Weekly active people, share of enabled accounts and stickiness of recent weeks."""
    accounts = samples.enabled_accounts(db)
    recent_span, prior_span = _spans(points)
    recent = _mean([float(p["active_people"]) for p in recent_span if p["active_people"] is not None])
    prior = _mean([float(p["active_people"]) for p in prior_span if p["active_people"] is not None])
    stickiness = None
    if recent_span and recent is not None:
        span = Window(date.fromisoformat(recent_span[0]["start"]), window.last, window.timezone)
        daily = [count for count in samples.active_per_day(db, span).values() if count >= MIN_GROUP]
        if daily:
            # Average daily active people over weekly active people: how often people return.
            stickiness = min(1.0, (sum(daily) / len(daily)) / recent)
    return {
        "accounts": accounts,
        "weekly_recent": recent,
        "weekly_prior": prior,
        "change": (recent - prior) / prior if recent is not None and prior else None,
        # People active earlier may have been deactivated since, so reach is capped at everyone.
        "reach": min(1.0, recent / accounts) if recent is not None and accounts else None,
        "stickiness": stickiness,
        "trend": classify(recent, prior, 0.0) if recent is not None and prior is not None else "unknown",
    }


def build_trends(db: Session, settings: Settings, weeks: int, *, now: datetime) -> dict:
    window = horizon_window(settings, weeks, now=now)
    payload = {
        "weeks": weeks,
        "timezone": settings.timezone,
        "generated_at": iso(now),
        "first_day": window.first.isoformat(),
        "last_day": window.last.isoformat(),
        "compare_weeks": COMPARE,
        "series": [{"key": key, "label": label} for key, label in FEATURES],
    }
    if not samples.has_samples(db, window) and not samples.has_activity(db, window):
        return {**payload, "state": "unknown", "points": [], "features": [], "people": None}
    points = _weekly(db, window)
    measured = any(point["state"] == "measured" for point in points)
    return {
        **payload,
        "state": "measured" if measured else "suppressed",
        "points": points,
        "features": _momentum(points) if measured else [],
        "people": _people(db, points, window) if measured else None,
    }
