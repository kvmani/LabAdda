"""Filtered, stable, metadata-only reads of the audit trail (AD-09)."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from . import audit_catalog
from .errors import Invalid
from .models import AuditEvent, User, Workspace
from .serialize import iso

# Contact details are never needed to understand who changed what.
HIDDEN_DETAIL = {"contact_email", "contact_phone", "extension", "residence_phone"}
MAX_TEXT = 200


@dataclass(frozen=True)
class AuditFilters:
    start: date | None = None
    end: date | None = None
    actor_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    group: str | None = None
    outcome: str | None = None
    q: str = ""


def audit_query(filters: AuditFilters, timezone: str):
    """Build newest-first predicates; `id` breaks ties so paging order never wobbles."""
    query = select(AuditEvent)
    zone = ZoneInfo(timezone)
    if filters.start:
        query = query.where(AuditEvent.created_at >= datetime.combine(filters.start, time.min, zone))
    if filters.end:
        after = datetime.combine(filters.end + timedelta(days=1), time.min, zone)
        query = query.where(AuditEvent.created_at < after)
    if filters.actor_id:
        query = query.where(AuditEvent.actor_id == filters.actor_id)
    if filters.person_id:
        query = query.where(AuditEvent.target_id == str(filters.person_id))
    if filters.unit_id:
        query = query.where(AuditEvent.scope_id == str(filters.unit_id))
    if filters.group:
        query = query.where(AuditEvent.action.in_(audit_catalog.actions_in_group(filters.group)))
    if filters.outcome:
        query = query.where(AuditEvent.outcome == filters.outcome)
    if filters.q.strip():
        pattern = filters.q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(AuditEvent.reason.ilike("%" + pattern + "%", escape="\\"))
    return query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())


def _fingerprint(filters: AuditFilters) -> str:
    payload = json.dumps(asdict(filters), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _encode(event: AuditEvent, filters: AuditFilters) -> str:
    payload = {"t": event.created_at.isoformat(), "id": event.id, "f": _fingerprint(filters)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def _decode(cursor: str, filters: AuditFilters) -> tuple[datetime, int]:
    try:
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if set(payload) != {"t", "id", "f"} or payload["f"] != _fingerprint(filters):
            raise ValueError
        if not isinstance(payload["id"], int) or isinstance(payload["id"], bool):
            raise ValueError
        moment = datetime.fromisoformat(payload["t"])
        if moment.tzinfo is None:
            raise ValueError
        return moment, payload["id"]
    except (ValueError, TypeError, KeyError):
        raise Invalid("invalid_cursor", "Reload the audit trail after changing its filters.") from None


def audit_page(db: Session, filters: AuditFilters, timezone: str, limit: int, cursor: str | None) -> dict:
    query = audit_query(filters, timezone)
    if cursor:
        moment, identity = _decode(cursor, filters)
        query = query.where(tuple_(AuditEvent.created_at, AuditEvent.id) < tuple_(moment, identity))
    rows = list(db.scalars(query.limit(limit + 1).execution_options(populate_existing=True)))
    page = rows[:limit]
    return {
        "events": shape_events(db, page),
        "next_cursor": _encode(page[-1], filters) if len(rows) > limit else None,
    }


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def _clean(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items() if k not in HIDDEN_DETAIL}
    if isinstance(value, list):
        return [_clean(v) for v in value[:50]]
    if isinstance(value, str):
        return value[:MAX_TEXT]
    return value


def _text(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True)


def changes(detail: dict) -> list[dict]:
    """Pair recorded before/after values so the drawer can show what changed."""
    found: list[dict] = []
    before, after = detail.get("before"), detail.get("after")
    if isinstance(before, dict) or isinstance(after, dict):
        before, after = before or {}, after or {}
        for field in sorted(set(before) | set(after)):
            if before.get(field) != after.get(field):
                found.append(
                    {"field": field, "before": _text(before.get(field)), "after": _text(after.get(field))}
                )
    elif "before" in detail or "after" in detail:
        found.append({"field": "value", "before": _text(before), "after": _text(after)})
    for key in sorted(detail):
        if key.endswith("_before") and key[:-7] + "_after" in detail:
            found.append(
                {"field": key[:-7], "before": _text(detail[key]), "after": _text(detail[key[:-7] + "_after"])}
            )
    return found


class _Words(defaultdict):
    def __missing__(self, key):
        return "unknown"


def _names(db: Session, rows: list[AuditEvent]):
    user_ids = {u for e in rows for u in (e.actor_id, _uuid(e.target_id)) if u}
    unit_ids = {u for e in rows for u in (_uuid(e.scope_id), _uuid(e.target_id)) if u}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    units = (
        {w.id: w for w in db.scalars(select(Workspace).where(Workspace.id.in_(unit_ids)))} if unit_ids else {}
    )
    return users, units


def _unit_words(unit: Workspace | None) -> str:
    if unit is None:
        return "an unknown space"
    # Projects and groups are private, so only their kind is ever named.
    return unit.name if unit.kind == "org" else f"a {unit.kind}"


def shape_events(db: Session, rows: list[AuditEvent]) -> list[dict]:
    users, units = _names(db, rows)
    items = []
    for e in rows:
        actor = users.get(e.actor_id) if e.actor_id else None
        target_user = users.get(_uuid(e.target_id))
        unit = units.get(_uuid(e.scope_id)) or units.get(_uuid(e.target_id))
        detail = _clean(e.detail or {})
        entry = audit_catalog.entry(e.action)
        words = _Words(
            str, {k: _text(v) or "unknown" for k, v in detail.items() if not isinstance(v, (dict, list))}
        )
        words.update(
            actor=actor.display_name if actor else "Operator tooling",
            target=target_user.display_name if target_user else "an unknown person",
            unit=_unit_words(unit),
        )
        items.append(
            {
                "id": e.id,
                "created_at": iso(e.created_at),
                "actor_id": str(e.actor_id) if e.actor_id else None,
                "actor": {"id": str(actor.id), "display_name": actor.display_name} if actor else None,
                "action": e.action,
                "group": entry.group,
                "group_label": audit_catalog.GROUPS[entry.group],
                "sentence": entry.sentence.format_map(words),
                "scope_type": e.scope_type,
                "scope_id": e.scope_id,
                "target_id": e.target_id,
                "target": (
                    {"id": str(target_user.id), "display_name": target_user.display_name}
                    if target_user
                    else None
                ),
                "unit": (
                    {"id": str(unit.id), "name": _unit_words(unit), "kind": unit.kind} if unit else None
                ),
                "outcome": e.outcome,
                "reason": e.reason,
                "changes": changes(detail) if isinstance(detail, dict) else [],
                "detail": detail,
            }
        )
    return items


def export_ids(db: Session, filters: AuditFilters, timezone: str, cap: int) -> list[int]:
    query = audit_query(filters, timezone).with_only_columns(AuditEvent.id)
    return list(db.scalars(query.limit(cap + 1)))


def rows_by_id(db: Session, ids: list[int]) -> list[AuditEvent]:
    found = {
        e.id: e
        for e in db.scalars(
            select(AuditEvent).where(AuditEvent.id.in_(ids)).execution_options(populate_existing=True)
        )
    }
    return [found[i] for i in ids if i in found]
