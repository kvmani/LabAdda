"""PO-06 scheduled changes: schedule, list, cancel, the due-time run and its denied cases."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from labadda import people
from labadda.changes import scheduled
from labadda.models import AuditEvent, ScheduledChange, User
from tests.test_changes_authority import change, site_today, start_of
from tests.test_changes_edit import reviewed
from tests.test_changes_transfer import grants, move


def day_after(settings, days=1):
    return site_today(settings) + timedelta(days=days)


def schedule_request(admin, request, day):
    """Preview and confirm a change for a future day, as the screens do."""
    body = {**request, "effective_on": day.isoformat()}
    return admin.post("/admin/changes/apply", json=reviewed_for(admin, body))


def reviewed_for(admin, body):
    preview = admin.post("/admin/changes/preview", json=body)
    assert preview.status_code == 200, preview.text
    plan = preview.json()
    return {
        **body,
        "digest": plan["digest"],
        "revisions": plan["revisions"],
        "reason": "Moves with the new term",
    }


def run(db_factory, settings, day, hour=0):
    with db_factory() as db:
        return scheduled.run_due(db, settings, now=start_of(day, settings) + timedelta(hours=hour))


def rows(db_factory):
    with db_factory() as db:
        return list(db.scalars(select(ScheduledChange)))


def test_schedule_stores_the_change_and_applies_nothing(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings, 3)
    before = grants(db_factory, ids["users"]["bharat"])
    response = schedule_request(admin, move(ids), day)
    assert response.status_code == 200, response.text
    assert response.json()["scheduled"] is True
    assert grants(db_factory, ids["users"]["bharat"]) == before
    [row] = rows(db_factory)
    assert (row.state, row.kind, row.effective_on) == ("pending", "transfer", day)
    assert str(row.subject_id) == ids["users"]["bharat"]
    listing = admin.get("/admin/changes/scheduled").json()["items"]
    assert [(item["id"], item["state"]) for item in listing] == [(str(row.id), "pending")]
    assert admin.get(f"/admin/changes/scheduled?person_id={ids['users']['chitra']}").json()["items"] == []
    with db_factory() as db:
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "people.schedule"))
        assert audit.reason == "Moves with the new term" and audit.detail["effective_on"] == day.isoformat()


@pytest.mark.parametrize("offset", [0, -1, 2000])
def test_schedule_refuses_today_the_past_and_the_far_future(offset, as_user, ids, settings):
    admin = as_user("admin")
    body = {**move(ids), "effective_on": day_after(settings, offset).isoformat()}
    response = admin.post("/admin/changes/preview", json=body)
    assert response.status_code == 422
    assert "invalid_date" in response.text


def test_activation_code_changes_cannot_be_scheduled(as_user, ids, settings):
    admin = as_user("admin")
    request = change(ids, "reinstate", person_id="farhan")
    body = {**request, "effective_on": day_after(settings).isoformat()}
    response = admin.post("/admin/changes/preview", json=body)
    assert "not_schedulable" in response.text


def test_stale_review_is_not_scheduled(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    body = reviewed_for(admin, {**move(ids), "effective_on": day_after(settings).isoformat()})
    edit = change(ids, "edit_person", person_id="bharat", fields={"designation": "Technician"})
    assert admin.post("/admin/changes/apply", json=reviewed(admin, edit)).status_code == 200
    response = admin.post("/admin/changes/apply", json=body)
    assert response.status_code == 409
    assert rows(db_factory) == []


def test_runs_on_the_day_and_is_idempotent(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings, 2)
    assert schedule_request(admin, move(ids), day).status_code == 200
    assert run(db_factory, settings, day - timedelta(days=1), hour=23) == 0
    assert grants(db_factory, ids["users"]["bharat"]).get(ids["workspaces"]["section_b"]) is None
    assert run(db_factory, settings, day) == 1
    assert run(db_factory, settings, day) == 0
    assert run(db_factory, settings, day, hour=5) == 0
    assert grants(db_factory, ids["users"]["bharat"])[ids["workspaces"]["section_b"]] == "member"
    [row] = rows(db_factory)
    assert row.state == "applied" and row.applied_at is not None
    assert admin.get("/admin/changes/scheduled").json()["items"] == []
    with db_factory() as db:
        events = list(db.scalars(select(AuditEvent).where(AuditEvent.action == "people.change")))
        assert len(events) == 1
        assert str(events[0].actor_id) == ids["users"]["admin"]
        assert events[0].reason == "Moves with the new term"
        assert events[0].detail["effective_on"] == day.isoformat()
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "people.schedule_apply"))


def test_a_conflicting_change_in_between_needs_review_and_applies_nothing(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings)
    assert schedule_request(admin, move(ids), day).status_code == 200
    edit = change(ids, "edit_person", person_id="bharat", fields={"designation": "Technician"})
    assert admin.post("/admin/changes/apply", json=reviewed(admin, edit)).status_code == 200
    before = grants(db_factory, ids["users"]["bharat"])
    assert run(db_factory, settings, day) == 0
    assert grants(db_factory, ids["users"]["bharat"]) == before
    [row] = rows(db_factory)
    assert row.state == "needs_review" and "changed after it was scheduled" in row.note
    assert run(db_factory, settings, day) == 0
    item = admin.get("/admin/changes/scheduled").json()["items"][0]
    assert item["state"] == "needs_review"


def test_a_plan_that_became_blocked_gives_its_plain_reason(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings)
    assert schedule_request(admin, move(ids), day).status_code == 200
    with db_factory() as db:
        db.get(User, ids["users"]["bharat"]).status = "retired"
        db.commit()
    assert run(db_factory, settings, day) == 0
    [row] = rows(db_factory)
    assert row.state == "needs_review" and row.note


def test_an_actor_who_lost_administration_cannot_have_it_applied(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings)
    assert schedule_request(admin, move(ids), day).status_code == 200
    with db_factory() as db:
        db.get(User, ids["users"]["admin"]).is_active = False
        db.commit()
    assert run(db_factory, settings, day) == 0
    [row] = rows(db_factory)
    assert row.state == "needs_review" and "can no longer make it" in row.note


def test_cancel_withdraws_and_is_final(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings)
    assert schedule_request(admin, move(ids), day).status_code == 200
    [row] = rows(db_factory)
    path = f"/admin/changes/scheduled/{row.id}"
    assert admin.delete(path).status_code == 422
    assert admin.delete(path, params={"reason": "Plans changed"}).status_code == 200
    assert admin.delete(path, params={"reason": "Plans changed"}).status_code == 409
    assert run(db_factory, settings, day) == 0
    assert rows(db_factory)[0].state == "cancelled"
    assert admin.get("/admin/changes/scheduled").json()["items"] == []
    missing = "00000000-0000-4000-8000-000000000000"
    assert admin.delete(f"/admin/changes/scheduled/{missing}", params={"reason": "x y z"}).status_code == 404
    with db_factory() as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "people.schedule_cancel"))


def test_a_unit_change_can_be_scheduled(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings)
    request = change(ids, "unit_rename", unit_id="section_a", name="Corrosion and Energy")
    response = schedule_request(admin, request, day)
    assert response.status_code == 200, response.text
    assert run(db_factory, settings, day) == 1
    admin_tree = admin.get("/admin/org/tree").text
    assert "Corrosion and Energy" in admin_tree


@pytest.mark.parametrize("username", ["asha", "bharat", "deepa"])
def test_members_cannot_use_scheduled_changes(username, as_user, ids, settings):
    member = as_user(username)
    body = {**move(ids), "effective_on": day_after(settings).isoformat()}
    assert member.post("/admin/changes/apply", json=body).status_code == 403
    assert member.get("/admin/changes/scheduled").status_code == 403
    missing = "00000000-0000-4000-8000-000000000000"
    assert (
        member.delete(f"/admin/changes/scheduled/{missing}", params={"reason": "no way"}).status_code == 403
    )


def test_signed_out_and_panel_sessions_are_refused(as_user, ids, make_client):
    from tests.test_panel import pair

    assert make_client().get("/admin/changes/scheduled").status_code == 401
    assert pair(as_user, make_client, ids).get("/admin/changes/scheduled").status_code == 401


def test_a_scheduled_suspension_ends_sessions_and_sockets_when_it_runs(as_user, ids, db_factory, settings):
    from unittest.mock import MagicMock

    admin, bharat = as_user("admin"), as_user("bharat")
    day = day_after(settings)
    assert schedule_request(admin, change(ids, "suspend", person_id="bharat"), day).status_code == 200
    assert bharat.get("/auth/session").status_code == 200
    hub = MagicMock()
    with db_factory() as db:
        assert scheduled.run_due(db, settings, hub, now=start_of(day, settings)) == 1
    hub.revalidate_user.assert_any_call(uuid.UUID(ids["users"]["bharat"]))
    assert bharat.get("/auth/session").status_code == 401


def test_one_unreviewable_change_does_not_stop_the_others(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings)
    assert schedule_request(admin, move(ids), day).status_code == 200
    assert schedule_request(admin, change(ids, "unit_rename", unit_id="section_a", name="Renamed"), day)
    with db_factory() as db:
        first = db.scalar(select(ScheduledChange).where(ScheduledChange.kind != "unit_rename"))
        first.plan_digest = "0" * 64
        db.commit()
    assert run(db_factory, settings, day) == 1
    assert {row.kind: row.state for row in rows(db_factory)}["unit_rename"] == "applied"
    assert sorted(row.state for row in rows(db_factory)) == ["applied", "needs_review"]


def test_the_effective_day_never_outlives_a_failed_run(as_user, ids, db_factory, settings):
    admin = as_user("admin")
    day = day_after(settings, 3)
    assert schedule_request(admin, move(ids), day).status_code == 200
    with db_factory() as db:
        db.execute(ScheduledChange.__table__.update().values(plan_digest="0" * 64))
        db.commit()
    assert run(db_factory, settings, day) == 0
    assert people.site_date(settings) == site_today(settings)
