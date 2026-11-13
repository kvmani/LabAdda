"""A2 audit explorer: filters, stable paging, audited formula-safe export, denial, no content."""

import csv
import io
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from labadda.api import audit as audit_api
from labadda.models import AuditEvent
from labadda.security import utcnow
from tests.test_capabilities import grant
from tests.test_panel import pair


def seed(db_factory, rows):
    with db_factory() as db:
        for row in rows:
            db.add(AuditEvent(detail={}, **row))
        db.commit()


def events(client, query=""):
    response = client.get("/admin/audit?" + query)
    assert response.status_code == 200, response.text
    return response.json()


def test_filters_combine(as_user, ids, db_factory):
    admin, asha, bharat = ids["users"]["admin"], ids["users"]["asha"], ids["users"]["bharat"]
    unit = ids["workspaces"]["section_a"]
    day = datetime(2026, 3, 10, 12, tzinfo=UTC)
    seed(
        db_factory,
        [
            {"actor_id": admin, "action": "membership.set", "scope_type": "workspace",
             "scope_id": str(unit), "target_id": str(bharat), "reason": "Joined the lab", "created_at": day},
            {"actor_id": admin, "action": "membership.remove", "scope_type": "workspace",
             "scope_id": str(unit), "target_id": str(asha), "reason": "100% moved", "created_at": day},
            {"actor_id": asha, "action": "auth.login", "scope_type": "identity", "outcome": "denied",
             "target_id": str(asha), "created_at": day + timedelta(days=2)},
            {"actor_id": admin, "action": "identity.update", "scope_type": "identity",
             "target_id": str(bharat), "created_at": day - timedelta(days=30)},
        ],
    )  # fmt: skip
    client = as_user("admin")
    actions = lambda q: {e["action"] for e in events(client, q)["events"]}  # noqa: E731
    assert actions("group=access&start=2026-03-10&end=2026-03-10") == {"membership.set", "membership.remove"}
    assert actions(f"group=access&person_id={bharat}") == {"membership.set"}
    assert actions(f"unit_id={unit}&q=joined") == {"membership.set"}
    assert actions("q=100%25") == {"membership.remove"}
    assert actions("q=%25") == {"membership.remove"}  # a literal percent, not a wildcard
    assert actions(f"actor_id={asha}&outcome=denied") == {"auth.login"}
    assert actions(f"actor_id={asha}&outcome=success") == set()
    assert actions("group=sign_in&start=2026-03-11") == {"auth.login"}
    assert actions(f"person_id={bharat}&end=2026-03-01") == {"identity.update"}
    assert client.get("/admin/audit?group=nonsense").status_code == 422
    assert client.get("/admin/audit?start=2026-03-12&end=2026-03-10").status_code == 422


def test_events_carry_sentence_and_before_after(as_user, ids, db_factory):
    admin, bharat = ids["users"]["admin"], ids["users"]["bharat"]
    with db_factory() as db:
        db.add(
            AuditEvent(
                actor_id=admin, action="membership.set", scope_type="workspace",
                scope_id=str(ids["workspaces"]["section_a"]), target_id=str(bharat),
                detail={"before": "reader", "after": "member", "contact_email": "x@y.example"},
            )
        )  # fmt: skip
        db.commit()
    event = events(as_user("admin"), "group=access")["events"][0]
    assert event["group_label"] == "Access"
    assert "set the role" in event["sentence"] and event["sentence"].endswith("member.")
    assert event["changes"] == [{"field": "value", "before": "reader", "after": "member"}]
    assert "contact_email" not in event["detail"]
    assert event["actor"]["display_name"] and event["target"]["display_name"]


def test_projects_and_groups_are_named_by_kind_only(as_user, ids, db_factory):
    project = ids["workspaces"]["project"]
    seed(db_factory, [{"actor_id": ids["users"]["admin"], "action": "group.create",
                       "scope_type": "workspace", "scope_id": str(project)}])  # fmt: skip
    event = events(as_user("admin"), "group=organisation")["events"][0]
    assert event["unit"]["kind"] == "project" and event["unit"]["name"] == "a project"


def test_pagination_is_stable_while_rows_arrive(as_user, ids, db_factory):
    admin = ids["users"]["admin"]
    base = datetime(2026, 5, 1, 9, tzinfo=UTC)
    seed(
        db_factory,
        [
            {"actor_id": admin, "action": "identity.update", "scope_type": "identity",
             "reason": f"row {n}", "created_at": base + timedelta(minutes=n // 2)}
            for n in range(9)
        ],
    )  # fmt: skip
    client = as_user("admin")
    first = events(client, "q=row&limit=4")
    assert first["next_cursor"]
    seed(
        db_factory,
        [{"actor_id": admin, "action": "identity.update", "scope_type": "identity",
          "reason": "row newer", "created_at": utcnow()} for _ in range(3)],
    )  # fmt: skip
    seen = [e["reason"] for e in first["events"]]
    cursor = first["next_cursor"]
    while cursor:
        page = events(client, f"q=row&limit=4&cursor={cursor}")
        seen += [e["reason"] for e in page["events"]]
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 9
    assert seen == [f"row {n}" for n in (8, 7, 6, 5, 4, 3, 2, 1, 0)]  # ties broken by id, newest first


def test_cursor_rejects_changed_filters_and_garbage(as_user, ids, db_factory):
    seed(db_factory, [{"actor_id": ids["users"]["admin"], "action": "identity.update",
                       "scope_type": "identity"} for _ in range(2)])  # fmt: skip
    client = as_user("admin")
    cursor = events(client, "limit=1")["next_cursor"]
    assert cursor
    assert client.get(f"/admin/audit?limit=1&cursor={cursor}&outcome=denied").status_code == 422
    for bad in ("not-a-cursor", "e30"):
        assert client.get(f"/admin/audit?cursor={bad}").json()["error"]["code"] == "invalid_cursor"


def rows_of(response):
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_export_escapes_formulas_and_is_audited(as_user, ids, db_factory):
    admin = ids["users"]["admin"]
    seed(
        db_factory,
        [
            {"actor_id": admin, "action": "identity.update", "scope_type": "identity", "reason": r}
            for r in ("=1+1", "+1", "-1", "@SUM(A1)", "plain")
        ],
    )
    response = as_user("admin").get("/admin/audit/export.csv?q=SUM")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="audit-')
    assert [r["reason"] for r in rows_of(response)] == ["'@SUM(A1)"]
    everything = rows_of(as_user("admin").get("/admin/audit/export.csv"))
    reasons = {r["reason"] for r in everything}
    assert {"'=1+1", "'+1", "'-1", "'@SUM(A1)", "plain"} <= reasons
    assert all(not v.startswith(("=", "+", "-", "@")) for r in everything for v in r.values())
    with db_factory() as db:
        records = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "audit.export").order_by(AuditEvent.id)
        ).all()
        assert records[0].detail["rows"] == "1"
        assert records[0].detail["filters"] == "q"
        assert "SUM" not in str(records[0].detail) and str(records[0].actor_id) == admin


def test_export_cap_refuses_without_partial_file_or_record(as_user, ids, db_factory):
    seed(db_factory, [{"actor_id": ids["users"]["admin"], "action": "identity.update",
                       "scope_type": "identity"} for _ in range(3)])  # fmt: skip
    with patch.object(audit_api, "EXPORT_LIMIT", 2):
        response = as_user("admin").get("/admin/audit/export.csv")
        assert response.status_code == 422 and response.json()["error"]["code"] == "export_limit"
        assert as_user("admin").get("/admin/audit/export.csv?q=nomatch").status_code == 200
    with db_factory() as db:
        recorded = db.scalars(select(AuditEvent).where(AuditEvent.action == "audit.export")).all()
        assert [r.detail["rows"] for r in recorded] == ["0"]  # the refused export left no record


@pytest.mark.parametrize("path", ["/admin/audit", "/admin/audit/export.csv"])
def test_only_current_administrators(as_user, make_client, ids, db_factory, path):
    admin = as_user("admin")
    assert grant(admin, ids["users"]["bharat"]).status_code == 201
    assert as_user("bharat").get(path).status_code == 403  # usage reader
    assert as_user("chitra").get(path).status_code == 403  # plain member
    assert make_client().get(path).status_code == 401
    panel = pair(as_user, make_client, ids)
    assert panel.get(path).status_code == 401
    with db_factory() as db:
        assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "audit.export")) is None


def test_no_private_content_in_explorer_or_export(as_user, ids):
    member = as_user("bharat")
    secrets = ("Synthetic note title zq", "Synthetic post body zq", "synthetic-file-zq.pdf")
    assert member.post("/notes", json={"title": secrets[0], "body": secrets[0]}).status_code == 201
    workspace = ids["workspaces"]["section_a"]
    assert member.post(f"/workspaces/{workspace}/posts", json={"body": secrets[1]}).status_code == 201
    upload = member.post("/uploads", files={"file": (secrets[2], b"%PDF-1.4\n%%EOF", "application/pdf")})
    assert upload.status_code == 201
    admin = as_user("admin")
    for path in ("/admin/audit?limit=500", "/admin/audit/export.csv"):
        for secret in secrets:
            assert secret not in admin.get(path).text, path


def test_deactivated_administrator_loses_the_explorer(as_user, ids, db_factory):
    from labadda.models import User

    client = as_user("admin")
    with db_factory() as db:
        db.get(User, ids["users"]["admin"]).is_active = False
        db.commit()
    assert client.get("/admin/audit").status_code in (401, 403)
