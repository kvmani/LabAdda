"""Privacy and operational truthfulness regressions for the cockpit review."""

from datetime import timedelta

from sqlalchemy import select

from labadda.models import Membership, OpsEvent, User, Workspace
from labadda.overview.cockpit import compute_usage_patterns
from labadda.overview.cockpit_operations import active_steward_units, performance, reliability
from labadda.security import utcnow
from tests.analytics_support import fresh_cache, store  # noqa: F401 — reset process-local analytics cache
from tests.test_panel import pair
from tests.test_todos import new_list, task_body

PATH = "/admin/analytics/cockpit"


def test_personal_work_never_changes_cockpit_or_exposes_content(as_user, db_factory):
    admin = as_user("admin")
    before = admin.get(PATH).json()
    member = as_user("bharat")
    personal = new_list(member)
    for number in range(7):
        response = member.post(
            f"/todos/lists/{personal['id']}/tasks",
            json=task_body(title=f"Private tensile notebook {number}"),
        )
        assert response.status_code == 201
    assert (
        member.post("/notes", json={"title": "Private microscopy note", "body": "Private plot"}).status_code
        == 201
    )
    with db_factory() as db:
        unit = db.scalar(select(Workspace).where(Workspace.kind == "org"))
        unit.description = "Unpublished experimental prose"
        db.commit()
    after = admin.get(PATH)
    assert after.status_code == 200
    for key in ("total_collaboration_items", "collaboration_state", "total_storage_bytes"):
        assert after.json()["kpis"][key] == before["kpis"][key]
    assert after.json()["usage_patterns"] == before["usage_patterns"]
    for secret in ("Private tensile", "Private microscopy", "Private plot", "Unpublished experimental prose"):
        assert secret not in after.text


def test_small_group_rankings_and_unmeasured_claims(as_user):
    admin = as_user("admin")
    body = admin.get(PATH).json()
    assert body["popular_workspaces"] == []
    assert body["kpis"]["total_collaboration_items"] is None
    assert body["usage_patterns"]["feature_distribution"] == []
    assert "not measured" in body["usage_patterns"]["peak_summary"]
    assert "not measured" in body["bottlenecks"]["storage"]["headroom_status"]
    assert body["bottlenecks"]["performance"]["p95_latency_ms"] is None


def test_complete_severity_counts_and_critical_first(db_factory, ids):
    now = utcnow()
    with db_factory() as db:
        for number in range(15):
            db.add(
                OpsEvent(
                    code=f"review.warning.{number}",
                    component="review",
                    severity="warning",
                    summary="Synthetic warning",
                    detail={},
                    first_at=now,
                    last_at=now,
                )
            )
        db.add(
            OpsEvent(
                code="review.critical",
                component="review",
                severity="critical",
                summary="Synthetic critical",
                detail={},
                first_at=now - timedelta(days=1),
                last_at=now,
            )
        )
        db.commit()
        value = reliability(db)
    assert value["critical_count"] == 1 and value["warning_count"] == 15
    assert len(value["open_events"]) == 10
    assert value["open_events"][0]["severity"] == "critical"


def test_latency_zero_and_stale_are_distinct(db_factory, ids):
    now = utcnow().replace(second=0, microsecond=0)
    store(db_factory, "minute", (now - timedelta(minutes=6), "http.latency_p95", "all", 25))
    with db_factory() as db:
        assert performance(db, now) == {"p95_latency_ms": None, "latency_status": "Stale reading"}
    store(db_factory, "minute", (now, "http.latency_p95", "all", 0))
    with db_factory() as db:
        assert performance(db, now)["p95_latency_ms"] == 0


def test_inactive_steward_is_not_coverage(db_factory, ids):
    with db_factory() as db:
        unit = db.scalar(
            select(Membership.workspace_id)
            .join(User)
            .where(User.username == "asha", Membership.role == "steward")
        )
        assert unit in active_steward_units(db)
        db.scalar(select(User).where(User.username == "asha")).is_active = False
        db.flush()
        assert unit not in active_steward_units(db)


def test_cockpit_console_denials(as_user, make_client, ids):
    assert make_client().get(PATH).status_code == 401
    for name in ("asha", "bharat", "chitra", "deepa"):
        assert as_user(name).get(PATH).status_code == 403
    assert pair(as_user, make_client, ids).get(PATH).status_code == 401


def test_missing_feature_metrics_are_unknown_not_suppressed():
    summary = {"charts": {"features": {"points": [{"state": "unknown", "values": {}}]}}}
    assert compute_usage_patterns(summary)["state"] == "unknown"
