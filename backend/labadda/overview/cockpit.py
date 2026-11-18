"""Cockpit uses the same protected activity figures as AD-08, never personal content tables."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import analytics
from ..config import Settings
from ..models import ContentCharge, User, Workspace
from ..serialize import iso
from .cockpit_operations import active_steward_units, bottlenecks, event_counts, format_bytes


def compute_kpis(db: Session, summary: dict) -> dict:
    """Enabled accounts are an inventory count, not a measure of adoption."""
    accounts = db.scalar(select(func.count()).select_from(User)) or 0
    enabled = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    kinds = dict(db.execute(select(Workspace.kind, func.count()).group_by(Workspace.kind)).all())
    item = next((tile for tile in summary["tiles"] if tile["key"] == "items_created"), None)
    size = (
        db.scalar(
            select(func.sum(ContentCharge.bytes)).where(
                ContentCharge.state == "live", ContentCharge.workspace_id.is_not(None)
            )
        )
        or 0
    )
    events = event_counts(db)
    return {
        "total_accounts": accounts,
        "active_accounts": enabled,
        "adoption_rate": round(enabled / accounts * 100, 1) if accounts else 0,
        "total_workspaces": sum(kinds.values()),
        "workspaces_by_kind": kinds,
        "total_collaboration_items": item["value"] if item else None,
        "collaboration_state": item["state"] if item else "unknown",
        "total_storage_bytes": size,
        "total_storage_formatted": format_bytes(size),
        "open_events_count": sum(events.values()),
        "events_by_severity": events,
    }


def compute_popular_workspaces(db: Session, protected: dict) -> list[dict]:
    """Rank only organisational figures already published with complementary suppression."""
    stewards = active_steward_units(db)
    rows = []
    for unit in protected["units"]:
        items = unit["items_created"]
        if unit["archived"] or items is None or items["state"] != "shown":
            continue
        rows.append(
            {
                "id": unit["id"],
                "name": unit["name"],
                "kind": "org",
                "active_people": unit["active_people"]["value"],
                "has_steward": any(str(steward) == unit["id"] for steward in stewards),
                "total_items": items["value"],
            }
        )
    rows.sort(key=lambda row: (-row["total_items"], row["name"]))
    return rows[:5]


def compute_usage_patterns(summary: dict) -> dict:
    """Use only published feature buckets; unmeasured/suppressed buckets contribute no numbers."""
    charts = summary.get("charts")
    points = charts["features"]["points"] if charts else []
    visible = [point for point in points if point["state"] == "measured"]
    definitions = [
        ("Noticeboard", ("posts.created", "replies.created"), "📢"),
        ("Chat messages", ("chat.messages",), "💬"),
        ("Tasks created", ("tasks.created",), "📋"),
        ("Whiteboard changes", ("board.operations",), "✏️"),
    ]
    values = [
        sum(point["values"].get(metric, 0) for point in visible for metric in metrics)
        for _, metrics, _ in definitions
    ]
    total = sum(values)
    patterns = (
        [
            {
                "feature": name,
                "count": value,
                "percentage": round(value / total * 100, 1) if total else 0,
                "icon": icon,
                "role": "Published activity in the last 7 days",
            }
            for (name, _, icon), value in zip(definitions, values, strict=True)
        ]
        if visible
        else []
    )
    return {
        "feature_distribution": patterns,
        "state": (
            "measured"
            if visible
            else "suppressed"
            if any(point["state"] == "suppressed" for point in points)
            else "unknown"
        ),
        "peak_summary": (
            "Peak hours are not measured in this view. Open Activity for protected time patterns."
        ),
    }


def build_cockpit_analytics(
    db: Session, settings: Settings, *, now: datetime, summary: dict | None = None
) -> dict:
    """Keep cockpit privacy, period and unknown-state semantics aligned with Activity."""
    summary = summary if summary is not None else analytics.build_summary(db, settings, "7d", now=now)
    units = analytics.build_units(db, settings, "7d", now=now)
    return {
        "generated_at": iso(now),
        "timezone": settings.timezone,
        "period": "7d",
        "minimum_group": units["minimum_group"],
        "kpis": compute_kpis(db, summary),
        "popular_workspaces": compute_popular_workspaces(db, units),
        "bottlenecks": bottlenecks(db, now),
        "usage_patterns": compute_usage_patterns(summary),
    }
