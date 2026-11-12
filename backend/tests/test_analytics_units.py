"""Activity by unit: small-group protection and differencing attacks (T64)."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from labadda import analytics
from labadda.analytics import protect
from labadda.analytics.units import _chart
from labadda.metrics import catalog
from labadda.models import User
from labadda.people import site_date
from tests.analytics_support import add_people, fresh_cache, mark_active, store, tile

__all__ = ["fresh_cache"]

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 11)


def units(db_factory, settings, period="30d"):
    with db_factory() as db:
        return analytics.build_units(db, settings, period, now=NOW)


def row(found, ids, key):
    return next(unit for unit in found["units"] if unit["id"] == ids["workspaces"][key])


def published(found) -> list:
    """Every per-unit figure the client receives, for comparison before and after a change."""
    rows = [*found["units"], found["no_home_unit"]]
    return [(r.get("id"), r["active_people"], r["items_created"], r["previous_active_people"]) for r in rows]


@pytest.mark.parametrize(
    ("active", "shown"),
    [
        ({"a": 4}, set()),
        ({"a": 5}, {"a"}),
        ({"a": 9, "b": 7}, {"a", "b"}),
        # One hidden person could be found as "total minus a": the next smallest is hidden too.
        ({"a": 9, "b": 1}, set()),
        ({"a": 9, "b": 6, "c": 2}, {"a"}),
        ({"a": 9, "b": 6, "c": 0}, {"a"}),
        ({"a": 9, "b": 3, "c": 2}, {"a"}),
        ({}, set()),
    ],
)
def test_rows_under_five_and_their_complements_are_suppressed(active, shown):
    assert protect.published(active) == shown
    hidden = sum(people for key, people in active.items() if key not in shown)
    assert hidden == 0 or hidden >= protect.MIN_GROUP or not shown


@pytest.mark.parametrize(("exact", "shown"), [(5, 5), (7, 5), (8, 10), (12, 10), (13, 15)])
def test_published_counts_are_rounded_to_fives(exact, shown):
    assert protect.figure(exact, True) == {"state": "shown", "value": shown}
    assert protect.figure(exact, False) == {"state": "suppressed"}
    assert protect.figure(2, True) == {"state": "shown", "value": 0}


def test_units_under_five_people_are_suppressed_on_the_server(db_factory, settings, ids):
    films = add_people(db_factory, ids["workspaces"]["section_a"], 5, "films")
    mark_active(db_factory, films, TODAY)
    mark_active(db_factory, [ids["users"]["chen"], ids["users"]["dana"]], TODAY)
    store(
        db_factory,
        "hour",
        (NOW - timedelta(hours=1), "posts.created", f"unit:{ids['workspaces']['section_b']}", 3),
    )
    found = units(db_factory, settings)
    assert found["state"] == "measured"
    catalysis = row(found, ids, "section_b")
    assert catalysis["active_people"] == {"state": "suppressed"}
    assert catalysis["items_created"] == {"state": "suppressed"}
    # Chen alone in Catalysis: no number, no count of posts, nothing the client must hide.
    assert '"value": 3' not in json.dumps(catalysis)
    names = [bar["label"] for bar in found["chart"]]
    assert "Catalysis Section" not in names
    assert "Surface Science Division" not in names


def test_published_units_show_rounded_counts_and_their_items(db_factory, settings, ids):
    films = add_people(db_factory, ids["workspaces"]["section_a"], 6, "films")
    catalysis = add_people(db_factory, ids["workspaces"]["section_b"], 6, "catalysis")
    visitors = add_people(db_factory, None, 5, "visitor")
    mark_active(db_factory, films + catalysis + visitors, TODAY)
    unit = f"unit:{ids['workspaces']['section_a']}"
    store(
        db_factory,
        "hour",
        (NOW - timedelta(hours=1), "posts.created", unit, 4),
        (NOW - timedelta(hours=1), "chat.messages", unit, 2),
        (NOW - timedelta(hours=1), "board.operations", unit, 50),
        (NOW - timedelta(hours=1), "posts.created", f"unit:{ids['workspaces']['root']}", 3),
        (NOW - timedelta(hours=1), "posts.created", f"unit:{ids['workspaces']['division']}", 4),
    )
    found = units(db_factory, settings)
    films_row = row(found, ids, "section_a")
    assert films_row["active_people"] == {"state": "shown", "value": 5}
    assert films_row["items_created"] == {"state": "shown", "value": 5}
    assert row(found, ids, "root")["items_created"] == {"state": "suppressed"}
    assert row(found, ids, "section_b")["active_people"] == {"state": "shown", "value": 5}
    assert found["chart"] == [
        {"label": "Catalysis Section", "value": 5},
        {"label": "Thin Films Section", "value": 5},
    ]


def test_overlapping_periods_cannot_be_subtracted_to_reveal_one_person(db_factory, settings, ids):
    films = add_people(db_factory, ids["workspaces"]["section_a"], 6, "films")
    # Four in the division and Chen are left out, five together, so Thin Films may be shown.
    division = add_people(db_factory, ids["workspaces"]["division"], 4, "division")
    mark_active(db_factory, [*films[:5], *division, ids["users"]["chen"]], TODAY)
    mark_active(db_factory, films[5:], TODAY - timedelta(days=20))
    month = row(units(db_factory, settings, "30d"), ids, "section_a")["active_people"]
    week = row(units(db_factory, settings, "7d"), ids, "section_a")["active_people"]
    # Exactly 6 and 5 people: rounding hides this difference. Rounding is deterministic, so a
    # window that slides across a rounding boundary can still show a change (see the guide).
    assert month == week == {"state": "shown", "value": 5}


def test_a_suppressed_unit_cannot_be_found_by_subtracting_from_totals(db_factory, settings, ids):
    films = add_people(db_factory, ids["workspaces"]["section_a"], 9, "films")
    mark_active(db_factory, [*films, ids["users"]["chen"]], TODAY)
    with db_factory() as db:
        summary = analytics.build_summary(db, settings, "30d", now=NOW)
    assert tile(summary, "active_month")["value"] == 10
    found = units(db_factory, settings)
    # The site total is exact, so publishing Thin Films (9) would reveal Chen in Catalysis.
    assert row(found, ids, "section_a")["active_people"] == {"state": "suppressed"}
    assert row(found, ids, "section_b")["active_people"] == {"state": "suppressed"}
    assert found["chart"] == []


def test_one_persons_activity_in_a_small_unit_changes_no_published_figure(db_factory, settings, ids):
    films = add_people(db_factory, ids["workspaces"]["section_a"], 7, "films")
    division = add_people(db_factory, ids["workspaces"]["division"], 8, "division")
    nobody = add_people(db_factory, None, 6, "visitor")
    mark_active(db_factory, films + division + nobody, TODAY, TODAY - timedelta(days=31))
    before = units(db_factory, settings)
    assert row(before, ids, "division")["active_people"]["state"] == "shown"
    analytics.CACHE.clear()
    # Chen is the only person in Catalysis, a section of the reported division.
    mark_active(db_factory, [ids["users"]["chen"]], TODAY, TODAY - timedelta(days=31))
    after = units(db_factory, settings)
    assert published(after) == published(before)
    assert after["chart"] == before["chart"]
    assert row(after, ids, "section_b")["active_people"] == {"state": "suppressed"}


def test_people_without_a_home_unit_are_one_protected_row(db_factory, settings, ids):
    mark_active(db_factory, [ids["users"]["eli"], ids["users"]["admin"]], TODAY)
    found = units(db_factory, settings)
    assert found["no_home_unit"]["active_people"] == {"state": "suppressed"}
    assert found["no_home_unit"]["items_created"] is None
    visitors = add_people(db_factory, None, 4, "visitor")
    mark_active(db_factory, visitors, TODAY)
    # Only shown once the people left out elsewhere are at least five together.
    assert units(db_factory, settings)["no_home_unit"]["active_people"] == {"state": "suppressed"}
    others = [ids["users"][name] for name in ("asha", "ben", "chen", "dana")]
    mark_active(db_factory, others + add_people(db_factory, ids["workspaces"]["section_b"], 1, "lab"), TODAY)
    assert units(db_factory, settings)["no_home_unit"]["active_people"] == {"state": "shown", "value": 5}


def test_projects_and_groups_never_appear_by_name(db_factory, settings, ids):
    people = add_people(db_factory, ids["workspaces"]["section_a"], 6, "films")
    mark_active(db_factory, people, TODAY)
    store(
        db_factory,
        "hour",
        (NOW - timedelta(hours=1), "posts.created", "project", 2),
        (NOW - timedelta(hours=1), "chat.messages", "group", 5),
    )
    found = units(db_factory, settings)
    listed = {unit["id"] for unit in found["units"]}
    assert ids["workspaces"]["project"] not in listed
    assert ids["workspaces"]["reading_club"] not in listed
    with db_factory() as db:
        summary = analytics.build_summary(db, settings, "30d", now=NOW)
    totals = {kind["label"]: kind["value"] for kind in summary["charts"]["items_by_kind"]}
    assert totals == {"Organisation units": 0, "Projects": 2, "Groups": 5}


def test_units_chart_keeps_ten_bars_and_folds_the_rest_into_other():
    rows = [
        {"id": str(n), "name": f"Unit {n:02d}", "active_people": {"state": "shown", "value": 5 * (n + 1)}}
        for n in range(12)
    ]
    rows.append({"id": "x", "name": "Small", "active_people": {"state": "suppressed"}})
    bars = _chart(rows)
    assert len(bars) == 11
    assert bars[0] == {"label": "Unit 11", "value": 60}
    assert bars[-1] == {"label": "Other units", "value": 5 + 10}


def test_unit_figures_are_never_served_as_raw_series(as_user, ids):
    params = {
        "metric": "posts.created",
        "dimension": catalog.unit_dimension(ids["workspaces"]["section_a"]),
        "resolution": "hour",
        "from": NOW.isoformat(),
        "to": (NOW + timedelta(hours=1)).isoformat(),
    }
    response = as_user("admin").get("/admin/metrics/series", params=params)
    assert response.json()["error"]["code"] == "unit_series_not_available"


def test_units_api_returns_suppressed_rows_without_numbers(as_user, ids, db_factory, settings):
    mark_active(db_factory, [ids["users"]["asha"]], site_date(settings))
    body = as_user("admin").get("/admin/analytics/units", params={"period": "7d"}).json()
    films = next(unit for unit in body["units"] if unit["name"] == "Thin Films Section")
    assert films["active_people"] == {"state": "suppressed"}
    assert body["minimum_group"] == 5
    assert all("value" not in unit["active_people"] for unit in body["units"])


@pytest.mark.parametrize(
    ("items", "candidates", "shown"),
    [
        ({"a": 9, "b": 4, "empty": 3}, {"a", "b"}, {"a"}),
        ({"a": 9, "b": 4, "empty": 3, "other": 2}, {"a", "b"}, {"a", "b"}),
        ({"a": 9, "b": 4, "empty": 0}, {"a", "b"}, set()),
        ({"a": 9, "b": 6, "c": 1, "d": 4}, {"a", "b"}, {"a", "b"}),
        ({"a": 9}, {"a"}, {"a"}),
    ],
)
def test_hidden_item_counts_cannot_be_isolated(items, candidates, shown):
    assert protect.published_items(items, candidates) == shown


def test_items_of_a_unit_nobody_calls_home_are_not_revealed_by_the_total(db_factory, settings, ids):
    films = add_people(db_factory, ids["workspaces"]["section_a"], 6, "films")
    visitors = add_people(db_factory, None, 5, "visitor")
    mark_active(db_factory, films + visitors, TODAY)
    store(
        db_factory,
        "hour",
        (NOW - timedelta(hours=1), "posts.created", "org", 7),
        (NOW - timedelta(hours=1), "posts.created", f"unit:{ids['workspaces']['section_a']}", 4),
        # One visitor posting in Materials Group, a unit that is nobody's home.
        (NOW - timedelta(hours=1), "posts.created", f"unit:{ids['workspaces']['group']}", 3),
    )
    found = units(db_factory, settings)
    with db_factory() as db:
        summary = analytics.build_summary(db, settings, "30d", now=NOW)
    org_total = next(kind for kind in summary["charts"]["items_by_kind"] if kind["key"] == "org")
    assert org_total["value"] == 7
    assert row(found, ids, "section_a")["active_people"]["state"] == "shown"
    assert row(found, ids, "section_a")["items_created"] == {"state": "suppressed"}
    assert row(found, ids, "group")["items_created"] == {"state": "suppressed"}


def test_home_units_are_read_as_they_are_now(db_factory, settings, ids):
    """Pins the accepted residual risk of transfers (console guide, "Transfers")."""
    films = add_people(db_factory, ids["workspaces"]["section_a"], 6, "films")
    division = add_people(db_factory, ids["workspaces"]["division"], 4, "division")
    mark_active(db_factory, [*films, *division, ids["users"]["chen"]], TODAY - timedelta(days=3))
    assert row(units(db_factory, settings), ids, "section_a")["active_people"] == {
        "state": "shown",
        "value": 5,
    }
    with db_factory() as db:
        moved = db.get(User, uuid.UUID(films[0]))
        moved.home_workspace_id = uuid.UUID(ids["workspaces"]["section_b"])
        db.commit()
    # Past activity follows the person to their new home unit; nothing records the old one.
    after = units(db_factory, settings)
    assert row(after, ids, "section_a")["active_people"] == {"state": "shown", "value": 5}
    assert row(after, ids, "section_b")["active_people"] == {"state": "suppressed"}
