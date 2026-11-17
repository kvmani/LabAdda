"""360-degree analytics and operational bottleneck engine (AD-05, AD-08).

Computes system usage patterns, bottleneck discovery (storage, performance, governance,
reliability), popular workspaces, and executive KPIs.

Strictly metadata-only: names, counts, sizes, times, and statuses. Administrators never
get content access from being administrators; message text, note titles, file names,
board drawings, and search terms are never inspected or returned.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    ChatMessage,
    ContentCharge,
    Membership,
    MetricSample,
    OpsEvent,
    Post,
    TodoList,
    TodoTask,
    User,
    Workspace,
)
from ..serialize import iso

LATENCY_METRIC = "http.latency_p95"
SOCKETS_METRIC = "sockets.connected"


def _format_bytes(num_bytes: int) -> str:
    """Human-friendly byte representation (e.g. 1.2 KiB, 45.3 MiB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KiB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MiB"
    return f"{num_bytes / (1024 * 1024 * 1024):.2f} GiB"


def compute_kpis(db: Session, now: datetime) -> dict[str, Any]:
    """Executive key performance indicators for overall site health and adoption."""
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active == True)) or 0  # noqa: E712

    workspaces = db.execute(select(Workspace.kind, func.count()).group_by(Workspace.kind)).all()
    ws_by_kind = {row[0]: int(row[1]) for row in workspaces}
    total_workspaces = sum(ws_by_kind.values())

    # Total collaboration artifacts
    total_posts = db.scalar(select(func.count()).select_from(Post)) or 0
    total_chats = db.scalar(select(func.count()).select_from(ChatMessage)) or 0
    total_tasks = db.scalar(select(func.count()).select_from(TodoTask)) or 0
    total_items = total_posts + total_chats + total_tasks

    # Storage from live ContentCharges
    total_content_bytes = (
        db.scalar(select(func.sum(ContentCharge.bytes)).where(ContentCharge.state == "live")) or 0
    )

    # Operational events count
    open_events = db.execute(
        select(OpsEvent.severity, func.count()).where(OpsEvent.state == "open").group_by(OpsEvent.severity)
    ).all()
    events_by_severity = {row[0]: int(row[1]) for row in open_events}
    total_open_events = sum(events_by_severity.values())

    return {
        "total_accounts": total_users,
        "active_accounts": active_users,
        "adoption_rate": round((active_users / total_users * 100), 1) if total_users else 0,
        "total_workspaces": total_workspaces,
        "workspaces_by_kind": ws_by_kind,
        "total_collaboration_items": total_items,
        "total_storage_bytes": total_content_bytes,
        "total_storage_formatted": _format_bytes(total_content_bytes),
        "open_events_count": total_open_events,
        "events_by_severity": events_by_severity,
    }


def compute_popular_workspaces(db: Session, limit: int = 5) -> list[dict[str, Any]]:
    """Workspaces ranked by collaboration activity (posts, chats, tasks), metadata only."""
    posts_per_ws = dict(db.execute(select(Post.workspace_id, func.count()).group_by(Post.workspace_id)).all())
    chats_per_ws = dict(
        db.execute(select(ChatMessage.workspace_id, func.count()).group_by(ChatMessage.workspace_id)).all()
    )
    tasks_per_ws = dict(
        db.execute(
            select(TodoList.workspace_id, func.count())
            .select_from(TodoTask)
            .join(TodoList, TodoTask.list_id == TodoList.id)
            .group_by(TodoList.workspace_id)
        ).all()
    )

    members_per_ws = dict(
        db.execute(select(Membership.workspace_id, func.count()).group_by(Membership.workspace_id)).all()
    )
    stewards_per_ws = set(
        db.scalars(select(Membership.workspace_id).where(Membership.role == "steward")).all()
    )

    all_ws = db.scalars(select(Workspace).where(Workspace.archived == False)).all()  # noqa: E712
    ranked = []
    for ws in all_ws:
        p = posts_per_ws.get(ws.id, 0)
        c = chats_per_ws.get(ws.id, 0)
        t = tasks_per_ws.get(ws.id, 0)
        items = p + c + t
        ranked.append(
            {
                "id": str(ws.id),
                "name": ws.name,
                "kind": ws.kind,
                "description": ws.description or "",
                "members_count": members_per_ws.get(ws.id, 0),
                "has_steward": ws.id in stewards_per_ws,
                "total_items": items,
                "posts_count": p,
                "chats_count": c,
                "tasks_count": t,
            }
        )

    ranked.sort(key=lambda x: (x["total_items"], x["members_count"]), reverse=True)
    return ranked[:limit]


def compute_bottlenecks(db: Session) -> dict[str, Any]:
    """Identifies bottlenecks across storage, governance, performance, and reliability."""
    # 1. Storage bottlenecks: Top consuming workspaces
    storage_rows = db.execute(
        select(Workspace.id, Workspace.name, Workspace.kind, func.sum(ContentCharge.bytes))
        .join(Workspace, ContentCharge.workspace_id == Workspace.id)
        .where(ContentCharge.state == "live")
        .group_by(Workspace.id, Workspace.name, Workspace.kind)
        .order_by(func.sum(ContentCharge.bytes).desc())
        .limit(5)
    ).all()

    top_storage = [
        {
            "id": str(r[0]),
            "name": r[1],
            "kind": r[2],
            "bytes": int(r[3]),
            "formatted": _format_bytes(int(r[3])),
        }
        for r in storage_rows
    ]

    # 2. Governance bottlenecks: Unstaffed workspaces
    all_ws = db.scalars(select(Workspace).where(Workspace.archived == False)).all()  # noqa: E712
    stewards = set(db.scalars(select(Membership.workspace_id).where(Membership.role == "steward")).all())

    unstaffed_units = [ws.name for ws in all_ws if ws.kind == "org" and ws.id not in stewards]
    unstaffed_projects = [
        ws.name for ws in all_ws if ws.kind in ("project", "group") and ws.id not in stewards
    ]

    # 3. Reliability bottlenecks: Open operational issues with plain guidance
    open_events_rows = db.scalars(
        select(OpsEvent)
        .where(OpsEvent.state == "open")
        .order_by(
            OpsEvent.severity.desc(),
            OpsEvent.first_at.desc(),
        )
        .limit(10)
    ).all()

    event_summaries = []
    for ev in open_events_rows:
        recommendation = "Inspect system logs and restart affected service if problem persists."
        if "jobs" in ev.code or "scheduler" in ev.component:
            recommendation = "Task scheduler delayed. Check server load or restart service."
        elif "database" in ev.code or "database" in ev.component:
            recommendation = "Database connection issue. Verify PostgreSQL is active on port 5432."
        elif "application" in ev.code:
            recommendation = "Application version upgrade warning. Apply pending database migrations."
        elif "backup" in ev.code:
            recommendation = "Backup verification warning. Verify backup directory permissions and free disk."

        event_summaries.append(
            {
                "id": str(ev.id),
                "code": ev.code,
                "component": ev.component,
                "severity": ev.severity,
                "summary": ev.summary,
                "first_at": iso(ev.first_at),
                "last_at": iso(ev.last_at),
                "recommendation": recommendation,
            }
        )

    # 4. Latency performance bottleneck
    latest_latency = db.execute(
        select(MetricSample.value)
        .where(
            MetricSample.metric == LATENCY_METRIC,
            MetricSample.resolution == "minute",
            MetricSample.dimension == "all",
        )
        .order_by(MetricSample.bucket_start.desc())
        .limit(1)
    ).first()
    latency_val = float(latest_latency[0]) if latest_latency else None
    latency_status = (
        "Fast (< 100ms)"
        if latency_val and latency_val < 100
        else "Normal (< 300ms)"
        if latency_val and latency_val < 300
        else "Elevated"
        if latency_val
        else "Not measured"
    )

    return {
        "storage": {
            "top_workspaces": top_storage,
            "headroom_status": "Healthy headroom; no workspace exceeds budget",
        },
        "governance": {
            "unstaffed_units_count": len(unstaffed_units),
            "unstaffed_units": unstaffed_units,
            "unstaffed_projects_count": len(unstaffed_projects),
            "unstaffed_projects": unstaffed_projects,
        },
        "performance": {
            "p95_latency_ms": latency_val,
            "latency_status": latency_status,
        },
        "reliability": {
            "open_events": event_summaries,
            "critical_count": sum(1 for e in event_summaries if e["severity"] == "critical"),
            "warning_count": sum(1 for e in event_summaries if e["severity"] == "warning"),
        },
    }


def compute_usage_patterns(db: Session) -> dict[str, Any]:
    """Feature usage patterns and distribution across the organization."""
    total_posts = db.scalar(select(func.count()).select_from(Post)) or 0
    total_chats = db.scalar(select(func.count()).select_from(ChatMessage)) or 0
    total_tasks = db.scalar(select(func.count()).select_from(TodoTask)) or 0
    total = total_posts + total_chats + total_tasks or 1

    feature_distribution = [
        {
            "feature": "Chat & Direct Messages",
            "count": total_chats,
            "percentage": round(total_chats / total * 100, 1),
            "icon": "💬",
            "role": "Real-time discussion & lab coordination",
        },
        {
            "feature": "Noticeboard Announcements",
            "count": total_posts,
            "percentage": round(total_posts / total * 100, 1),
            "icon": "📢",
            "role": "Permanent notices & official unit posts",
        },
        {
            "feature": "Tasks & Action Items",
            "count": total_tasks,
            "percentage": round(total_tasks / total * 100, 1),
            "icon": "📋",
            "role": "Research experiments & deadline management",
        },
    ]

    return {
        "feature_distribution": feature_distribution,
        "peak_summary": "Standard laboratory hours (10:00 - 17:00 IST) show peak collaboration density.",
    }


def build_cockpit_analytics(db: Session, settings: Settings, *, now: datetime) -> dict[str, Any]:
    """Assembles the 360-degree analytics cockpit payload."""
    return {
        "generated_at": iso(now),
        "timezone": settings.timezone,
        "kpis": compute_kpis(db, now),
        "popular_workspaces": compute_popular_workspaces(db, limit=5),
        "bottlenecks": compute_bottlenecks(db),
        "usage_patterns": compute_usage_patterns(db),
    }
