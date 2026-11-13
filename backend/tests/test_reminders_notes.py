"""T07: reminder timing, duplicate ticks, removed members, private notes."""

import threading
from datetime import timedelta

from labadda.scheduler import process_due_reminders
from labadda.security import utcnow


def iso(dt):
    return dt.isoformat()


def test_one_notification_per_occurrence_and_recipient(as_user, ids, db_factory):
    ws = ids["workspaces"]["section_a"]
    now = utcnow()
    as_user("bharat").post(
        f"/workspaces/{ws}/posts",
        json={
            "body": "Beamtime application due",
            "due_at": iso(now + timedelta(hours=2)),
            "remind_at": iso(now - timedelta(minutes=1)),
        },
    )
    with db_factory() as db:
        first = process_due_reminders(db)
    with db_factory() as db:
        second = process_due_reminders(db)
    assert first == 2 and second == 0  # asha and bharat; farhan disabled
    items = as_user("asha").get("/notifications").json()["items"]
    assert [i["kind"] for i in items] == ["reminder"]


def test_concurrent_ticks_do_not_duplicate(as_user, ids, db_factory):
    ws = ids["workspaces"]["division"]
    as_user("deepa").post(f"/workspaces/{ws}/posts", json={"body": "Seminar", "remind_at": iso(utcnow())})
    results = []
    barrier = threading.Barrier(3)

    def tick():
        barrier.wait()
        with db_factory() as db:
            results.append(process_due_reminders(db))

    threads = [threading.Thread(target=tick) for _ in range(3)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(results) == 4  # asha, bharat, chitra, deepa


def test_member_removed_before_delivery_gets_nothing(as_user, ids, db_factory):
    ws = ids["workspaces"]["section_a"]
    as_user("asha").post(
        f"/workspaces/{ws}/posts", json={"body": "Later", "remind_at": iso(utcnow() + timedelta(minutes=5))}
    )
    as_user("admin").delete(f"/admin/workspaces/{ws}/memberships/{ids['users']['bharat']}")
    with db_factory() as db:
        process_due_reminders(db, now=utcnow() + timedelta(minutes=6))
    assert as_user("bharat").get("/notifications").json()["items"] == []


def test_notification_rechecked_on_open(as_user, ids, db_factory):
    ws = ids["workspaces"]["section_a"]
    as_user("asha").post(f"/workspaces/{ws}/posts", json={"body": "Hi @bharat"})
    bharat = as_user("bharat")
    nid = bharat.get("/notifications").json()["items"][0]["id"]
    as_user("admin").delete(f"/admin/workspaces/{ws}/memberships/{ids['users']['bharat']}")
    assert bharat.get("/notifications").json()["items"] == []
    assert bharat.post(f"/notifications/{nid}/open").status_code == 404


def test_rescheduled_reminder_is_a_new_occurrence(as_user, ids, db_factory):
    ws = ids["workspaces"]["section_a"]
    asha = as_user("asha")
    pid = asha.post(f"/workspaces/{ws}/posts", json={"body": "Calibrate", "remind_at": iso(utcnow())}).json()[
        "id"
    ]
    with db_factory() as db:
        assert process_due_reminders(db) == 2
    asha.patch(
        f"/posts/{pid}", json={"update_schedule": True, "remind_at": iso(utcnow() + timedelta(seconds=1))}
    )
    with db_factory() as db:
        assert process_due_reminders(db, now=utcnow() + timedelta(seconds=5)) == 2


def test_notes_are_owner_only(as_user, db_factory):
    bharat, asha, admin = as_user("bharat"), as_user("asha"), as_user("admin")
    note = bharat.post(
        "/notes",
        json={
            "title": "Order argon",
            "body": "two cylinders",
            "due_at": iso(utcnow() + timedelta(days=1)),
            "remind_at": iso(utcnow() - timedelta(seconds=1)),
        },
    ).json()
    for other in (asha, admin):
        assert other.get(f"/notes/{note['id']}").status_code == 404
        assert other.put(f"/notes/{note['id']}", json={"title": "x"}).status_code == 404
        assert other.delete(f"/notes/{note['id']}").status_code == 404
        assert other.get("/notes").json()["notes"] == []
    assert bharat.get("/notes/upcoming").json()["items"][0]["title"] == "Order argon"
    with db_factory() as db:
        assert process_due_reminders(db) == 1
    assert bharat.get("/notifications").json()["items"][0]["title"] == "Order argon"
    assert asha.get("/notifications").json()["items"] == []
    assert (
        bharat.put(f"/notes/{note['id']}", json={"title": "Order argon gas"}).json()["title"]
        == "Order argon gas"
    )
    assert bharat.delete(f"/notes/{note['id']}").status_code == 200


def test_notes_never_in_workspace_search(as_user, ids):
    bharat = as_user("bharat")
    bharat.post("/notes", json={"title": "secret-note-token"})
    r = bharat.get(
        f"/workspaces/{ids['workspaces']['section_a']}/search", params={"q": "secret-note-token"}
    ).json()
    assert r["counts"] == {"posts": 0, "chat": 0}
