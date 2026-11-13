"""P3 review findings closed in P5: expiry attention, hub revalidation, successor locks, plan honesty."""

from datetime import timedelta

from sqlalchemy import event, select

from labadda import positions
from labadda.changes import service
from labadda.changes.requests import Leave, Retire
from labadda.models import AuditEvent, Membership, UnitPosition, User
from labadda.security import utcnow
from tests.test_changes_authority import apply, change, make_head, site_today
from tests.test_changes_transfer import preview


class RecordingHub:
    def __init__(self, db_factory):
        self.calls = []
        self.db_factory = db_factory

    def revalidate_user(self, user_id):
        self.calls.append(("user", user_id, self.ended()))

    def revalidate_workspace(self, workspace_id):
        self.calls.append(("workspace", workspace_id, self.ended()))

    def ended(self):
        with self.db_factory() as db:
            return all(row.ended_at is not None for row in db.scalars(select(UnitPosition)))


def acting_chitra(db_factory, ids, settings):
    """Chitra is acting Head of Corrosion until today and goes back to member when it ends."""
    with db_factory() as db:
        row = db.scalar(
            select(Membership).where(
                Membership.user_id == ids["users"]["chitra"],
                Membership.workspace_id == ids["workspaces"]["section_b"],
            )
        )
        row.role = "steward"
        db.commit()
    make_head(
        db_factory,
        ids,
        username="chitra",
        unit="section_b",
        acting=True,
        ends_on=site_today(settings),
        revert_role="member",
    )


def staff_other_units(db_factory, ids):
    with db_factory() as db:
        for unit in ("root", "group"):
            db.add(
                Membership(user_id=ids["users"]["asha"], workspace_id=ids["workspaces"][unit], role="steward")
            )
        db.commit()


def test_expiry_that_leaves_a_unit_without_a_steward_raises_an_attention_item(
    as_user, ids, db_factory, settings
):
    admin = as_user("admin")
    staff_other_units(db_factory, ids)
    acting_chitra(db_factory, ids, settings)
    assert "people:units-without-steward" not in {
        i["id"] for i in admin.get("/admin/org/attention").json()["items"]
    }
    with db_factory() as db:
        assert positions.expire_due(db, settings, now=utcnow() + timedelta(days=1)) == 1
    items = {i["id"]: i for i in admin.get("/admin/org/attention").json()["items"]}
    assert "Corrosion Section" in items["people:units-without-steward"]["detail"]
    assert "Corrosion Section" in items["people:acting-expired"]["detail"]


def test_expiry_revalidates_delivery_after_commit(ids, db_factory, settings):
    acting_chitra(db_factory, ids, settings)
    hub = RecordingHub(db_factory)
    with db_factory() as db:
        assert positions.expire_due(db, settings, now=utcnow() + timedelta(days=1), hub=hub) == 1
    assert [(kind, done) for kind, _, done in hub.calls] == [("user", True), ("workspace", True)]
    assert str(hub.calls[0][1]) == ids["users"]["chitra"]
    assert str(hub.calls[1][1]) == ids["workspaces"]["section_b"]
    with db_factory() as db:
        assert positions.expire_due(db, settings, now=utcnow() + timedelta(days=1), hub=hub) == 0
    assert len(hub.calls) == 2


def locking_statements(db_factory, request):
    seen = []

    def record(_conn, _cursor, statement, parameters, *_rest):
        if "FOR UPDATE" in statement and "FROM users" in statement:
            seen.append((statement, str(parameters)))

    with db_factory() as db:
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", record)
        try:
            service.lock_targets(db, request)
        finally:
            event.remove(engine, "before_cursor_execute", record)
            db.rollback()
    return seen


def test_retire_locks_the_successor_row_in_the_same_ordered_statement(ids, db_factory):
    request = Retire.model_validate(
        {
            "kind": "retire",
            "person_id": ids["users"]["deepa"],
            "status": "retired",
            "successors": [
                {"workspace_id": ids["workspaces"]["project"], "successor_id": ids["users"]["esha"]}
            ],
        }
    )
    [(statement, params)] = locking_statements(db_factory, request)
    assert "ORDER BY users.id" in statement
    assert ids["users"]["esha"] in params and ids["users"]["deepa"] in params


def test_leave_locks_the_acting_replacement_row(ids, db_factory):
    row = make_head(db_factory, ids)
    request = Leave.model_validate(
        {
            "kind": "leave",
            "person_id": ids["users"]["deepa"],
            "expected_return_on": (site_today_plus(30)).isoformat(),
            "acting": [{"position_id": row, "successor_id": ids["users"]["asha"]}],
        }
    )
    [(_statement, params)] = locking_statements(db_factory, request)
    assert ids["users"]["asha"] in params and ids["users"]["deepa"] in params


def site_today_plus(days):
    return utcnow().date() + timedelta(days=days)


def test_demoting_the_outgoing_head_shows_the_other_position_it_ends(as_user, ids, db_factory):
    admin = as_user("admin")
    make_head(db_factory, ids)
    make_head(db_factory, ids, position="deputy")
    request = change(
        ids,
        "change_authority",
        workspace_id="division",
        position="head",
        successor_id="asha",
        outgoing_role="member",
    )
    plan = preview(admin, request)
    summaries = [step["summary"] for step in plan["steps"]]
    assert summaries[:3] == [
        "End the position of Deepa Nair as Head of Surface Engineering Division",
        "End the position of Deepa Nair as Deputy of Surface Engineering Division",
        "Set the role of Deepa Nair in Surface Engineering Division to member",
    ]
    apply(admin, request)
    with db_factory() as db:
        ended = list(db.scalars(select(AuditEvent).where(AuditEvent.action == "position.end")))
        assert len(ended) == 2 and all(row.actor_id is not None for row in ended)
        assert db.scalar(select(User).where(User.username == "deepa")) is not None
    assert [row for row in positions_current(db_factory) if row[0] == ids["users"]["deepa"]] == []


def positions_current(db_factory):
    with db_factory() as db:
        return [(str(r.user_id), r.position) for r in positions.current(db)]


def test_keeping_the_outgoing_role_adds_no_extra_step(as_user, ids, db_factory):
    admin = as_user("admin")
    make_head(db_factory, ids)
    make_head(db_factory, ids, position="deputy")
    plan = preview(
        admin,
        change(ids, "change_authority", workspace_id="division", position="head", successor_id="asha"),
    )
    assert not any("Deputy" in step["summary"] for step in plan["steps"])
