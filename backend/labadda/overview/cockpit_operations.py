"""Operational cockpit facts, separate from privacy-protected collaboration activity."""

from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import ContentCharge, Membership, MetricSample, OpsEvent, User, Workspace
from ..serialize import iso
from .attention import SEVERITIES


def format_bytes(value: int) -> str:
    """Format recorded logical bytes without claiming filesystem headroom."""
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("Unreachable byte unit")


def active_steward_units(db: Session) -> set:
    """Inactive accounts never satisfy steward coverage."""
    return set(
        db.scalars(
            select(Membership.workspace_id)
            .join(User)
            .where(Membership.role == "steward", User.is_active.is_(True))
        )
    )


def event_counts(db: Session) -> dict[str, int]:
    """Count the entire open queue, independently of the bounded detail list."""
    return dict(
        db.execute(
            select(OpsEvent.severity, func.count())
            .where(OpsEvent.state == "open")
            .group_by(OpsEvent.severity)
        ).all()
    )


def reliability(db: Session) -> dict:
    """Return the worst ten events and complete severity totals."""
    counts = event_counts(db)
    priority = case(
        {severity: index for index, severity in enumerate(SEVERITIES)},
        value=OpsEvent.severity,
        else_=len(SEVERITIES),
    )
    events = db.scalars(
        select(OpsEvent)
        .where(OpsEvent.state == "open")
        .order_by(priority, OpsEvent.first_at.desc(), OpsEvent.id)
        .limit(10)
    ).all()
    return {
        "critical_count": counts.get("critical", 0),
        "warning_count": counts.get("warning", 0),
        "open_events": [
            {
                "id": str(event.id),
                "code": event.code,
                "component": event.component,
                "severity": event.severity,
                "summary": event.summary,
                "first_at": iso(event.first_at),
                "last_at": iso(event.last_at),
                "recommendation": "Open the events and health pages to review this recorded condition.",
            }
            for event in events
        ],
    }


def performance(db: Session, now: datetime) -> dict:
    """Do not present missing, future or old latency readings as current."""
    reading = db.execute(
        select(MetricSample.value, MetricSample.bucket_start)
        .where(
            MetricSample.metric == "http.latency_p95",
            MetricSample.resolution == "minute",
            MetricSample.dimension == "all",
            MetricSample.bucket_start <= now,
        )
        .order_by(MetricSample.bucket_start.desc())
        .limit(1)
    ).first()
    if reading is None:
        return {"p95_latency_ms": None, "latency_status": "Not measured"}
    if now - reading.bucket_start > timedelta(minutes=5):
        return {"p95_latency_ms": None, "latency_status": "Stale reading"}
    value = float(reading.value)
    word = "Fast (< 100ms)" if value < 100 else "Normal (< 300ms)" if value < 300 else "Elevated"
    return {"p95_latency_ms": value, "latency_status": word}


def bottlenecks(db: Session, now: datetime) -> dict:
    """Expose capacity observations and governance metadata without invented conclusions."""
    sizes = db.execute(
        select(Workspace.id, Workspace.name, Workspace.kind, func.sum(ContentCharge.bytes).label("size"))
        .join(Workspace, ContentCharge.workspace_id == Workspace.id)
        .where(ContentCharge.state == "live")
        .group_by(Workspace.id, Workspace.name, Workspace.kind)
        .order_by(func.sum(ContentCharge.bytes).desc(), Workspace.id)
        .limit(5)
    ).all()
    stewarded = active_steward_units(db)
    spaces = db.scalars(select(Workspace).where(Workspace.archived.is_(False))).all()
    units = [space.name for space in spaces if space.kind == "org" and space.id not in stewarded]
    projects = [space.name for space in spaces if space.kind != "org" and space.id not in stewarded]
    return {
        "storage": {
            "top_workspaces": [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "kind": row.kind,
                    "bytes": int(row.size),
                    "formatted": format_bytes(int(row.size)),
                }
                for row in sizes
            ],
            "headroom_status": "Headroom is not measured here; workspace budgets are observation-only.",
        },
        "governance": {
            "unstaffed_units_count": len(units),
            "unstaffed_units": units,
            "unstaffed_projects_count": len(projects),
            "unstaffed_projects": projects,
        },
        "performance": performance(db, now),
        "reliability": reliability(db),
    }
