"""Tests for Google-grade Central & Hierarchical Calendar API.

Verifies:
- Personal events isolation and strict administrator content blindness.
- Upward-only hierarchy inheritance (Section members see Division events,
  Division-only members cannot see Section events).
- Sibling section privacy (Section A cannot see Section B).
- Site-wide events visibility for all active users and permission gates.
- Date range filtering and sources filtering.
- Panel-session denial (401).
- Single event retrieval, patch, and delete permissions.
"""


def test_personal_calendar_isolation_and_admin_blindness(as_user, ids):
    """Personal calendar events are strictly private to the user and blind to admins."""
    bharat = as_user("bharat")
    admin = as_user("admin")
    chitra = as_user("chitra")

    # 1. Bharat creates a personal event
    ev_payload = {
        "scope_kind": "personal",
        "title": "Private Research Review",
        "description": "Prepare XRD spectrum analysis notes",
        "location": "Lab Bench 4",
        "starts_at": "2026-11-20T10:00:00Z",
        "ends_at": "2026-11-20T11:00:00Z",
        "all_day": False,
        "color": "#d81b60",
    }
    r_create = bharat.post("/calendar/events", json=ev_payload)
    assert r_create.status_code == 200, r_create.text
    event = r_create.json()
    event_id = event["id"]
    assert event["title"] == "Private Research Review"
    assert event["scope_kind"] == "personal"
    assert event["can_edit"] is True
    assert event["can_delete"] is True

    # 2. Bharat sees it in calendar range query
    r_list = bharat.get("/calendar/events?start=2026-11-20T00:00:00Z&end=2026-11-20T23:59:59Z")
    assert r_list.status_code == 200
    b_events = r_list.json()
    assert any(e["id"] == event_id for e in b_events)

    # 3. Chitra (another normal user) cannot see it in range query
    r_chitra_list = chitra.get("/calendar/events?start=2026-11-20T00:00:00Z&end=2026-11-20T23:59:59Z")
    assert r_chitra_list.status_code == 200
    assert not any(e["id"] == event_id for e in r_chitra_list.json())

    # 4. Chitra directly accessing event gets uniform 404
    assert chitra.get(f"/calendar/events/{event_id}").status_code == 404
    assert chitra.patch(f"/calendar/events/{event_id}", json={"title": "Hacked"}).status_code == 404
    assert chitra.delete(f"/calendar/events/{event_id}").status_code == 404

    # 5. ADMIN BLINDNESS: Administrator cannot see it in range query or single fetch
    r_admin_list = admin.get("/calendar/events?start=2026-11-20T00:00:00Z&end=2026-11-20T23:59:59Z")
    assert r_admin_list.status_code == 200
    assert not any(e["id"] == event_id for e in r_admin_list.json())

    # Administrator directly attempting to inspect or mutate gets uniform 404
    assert admin.get(f"/calendar/events/{event_id}").status_code == 404
    assert admin.patch(f"/calendar/events/{event_id}", json={"title": "Admin Override"}).status_code == 404
    assert admin.delete(f"/calendar/events/{event_id}").status_code == 404

    # 6. Bharat updates their event
    r_update = bharat.patch(
        f"/calendar/events/{event_id}",
        json={"title": "Updated Research Review", "location": "Seminar Hall A"},
    )
    assert r_update.status_code == 200
    assert r_update.json()["title"] == "Updated Research Review"
    assert r_update.json()["location"] == "Seminar Hall A"

    # 7. Bharat deletes their event
    r_del = bharat.delete(f"/calendar/events/{event_id}")
    assert r_del.status_code == 200
    assert bharat.get(f"/calendar/events/{event_id}").status_code == 404


def test_hierarchy_and_upward_only_calendar_events(as_user, ids):
    """Section members see Division events; Division-only members cannot see Section events."""
    bharat = as_user("bharat")  # in section_a
    deepa = as_user("deepa")  # steward in division (parent of section_a)
    chitra = as_user("chitra")  # in section_b (sibling of section_a)

    sec_a_id = ids["workspaces"]["section_a"]
    div_id = ids["workspaces"]["division"]

    # 1. Bharat creates an event in Section A
    r_sec = bharat.post(
        "/calendar/events",
        json={
            "scope_kind": "workspace",
            "workspace_id": sec_a_id,
            "title": "Section A Lab Cleanliness Drive",
            "starts_at": "2026-11-21T09:00:00Z",
            "ends_at": "2026-11-21T12:00:00Z",
        },
    )
    assert r_sec.status_code == 200, r_sec.text
    sec_ev_id = r_sec.json()["id"]

    # 2. Deepa creates an event in Surface Engineering Division
    r_div = deepa.post(
        "/calendar/events",
        json={
            "scope_kind": "workspace",
            "workspace_id": div_id,
            "title": "Division Quarterly Review",
            "starts_at": "2026-11-21T14:00:00Z",
            "ends_at": "2026-11-21T16:00:00Z",
        },
    )
    assert r_div.status_code == 200, r_div.text
    div_ev_id = r_div.json()["id"]

    # 3. Range query by Bharat (in Section A):
    # Upward inheritance: Bharat sees Section A event AND Division event!
    b_events = bharat.get("/calendar/events?start=2026-11-21T00:00:00Z&end=2026-11-21T23:59:59Z").json()
    b_ev_ids = {e["id"] for e in b_events}
    assert sec_ev_id in b_ev_ids
    assert div_ev_id in b_ev_ids

    # 4. Range query by Deepa (in Division only):
    # Hierarchy is upward-only: Deepa sees Division event, but NOT Section A event!
    d_events = deepa.get("/calendar/events?start=2026-11-21T00:00:00Z&end=2026-11-21T23:59:59Z").json()
    d_ev_ids = {e["id"] for e in d_events}
    assert div_ev_id in d_ev_ids
    assert sec_ev_id not in d_ev_ids
    # Deepa direct fetch of Section A event gets 404
    assert deepa.get(f"/calendar/events/{sec_ev_id}").status_code == 404

    # 5. Range query by Chitra (in sibling Section B):
    # Sibling privacy: Chitra sees Division event, but NOT Section A event!
    c_events = chitra.get("/calendar/events?start=2026-11-21T00:00:00Z&end=2026-11-21T23:59:59Z").json()
    c_ev_ids = {e["id"] for e in c_events}
    assert div_ev_id in c_ev_ids
    assert sec_ev_id not in c_ev_ids
    assert chitra.get(f"/calendar/events/{sec_ev_id}").status_code == 404


def test_site_wide_events_and_permission_gate(as_user, ids):
    """Site-wide events are visible to all active users, but only admins/root stewards can create."""
    admin = as_user("admin")
    bharat = as_user("bharat")
    esha = as_user("esha")

    # 1. Non-admin Bharat attempts to create a site-wide event -> 403 Forbidden
    r_bad = bharat.post(
        "/calendar/events",
        json={
            "scope_kind": "site",
            "title": "Unauthorized Institute Seminar",
            "starts_at": "2026-11-25T10:00:00Z",
            "ends_at": "2026-11-25T11:00:00Z",
        },
    )
    assert r_bad.status_code == 403

    # 2. Admin creates site-wide event
    r_site = admin.post(
        "/calendar/events",
        json={
            "scope_kind": "site",
            "title": "National Science Day Celebration",
            "description": "Annual keynote address in the main auditorium",
            "location": "Dr. Raman Auditorium",
            "starts_at": "2026-11-25T09:30:00Z",
            "ends_at": "2026-11-25T13:00:00Z",
            "all_day": False,
            "color": "#1565c0",
        },
    )
    assert r_site.status_code == 200, r_site.text
    site_ev = r_site.json()
    site_ev_id = site_ev["id"]
    assert site_ev["scope_kind"] == "site"

    # 3. All users (Bharat, Esha) see the site-wide event in range query
    for client in (bharat, esha):
        events = client.get("/calendar/events?start=2026-11-25T00:00:00Z&end=2026-11-25T23:59:59Z").json()
        assert any(e["id"] == site_ev_id for e in events)

    # 4. Sources filter: sources=site returns it; sources=personal excludes it
    r_only_site = bharat.get(
        "/calendar/events?start=2026-11-25T00:00:00Z&end=2026-11-25T23:59:59Z&sources=site"
    ).json()
    assert any(e["id"] == site_ev_id for e in r_only_site)

    r_only_pers = bharat.get(
        "/calendar/events?start=2026-11-25T00:00:00Z&end=2026-11-25T23:59:59Z&sources=personal"
    ).json()
    assert not any(e["id"] == site_ev_id for e in r_only_pers)


def test_date_range_and_sources_query(as_user, ids):
    """Calendar queries strictly respect time intervals and source selection."""
    bharat = as_user("bharat")

    # Create event on Nov 22
    ev22 = bharat.post(
        "/calendar/events",
        json={
            "scope_kind": "personal",
            "title": "Nov 22 Event",
            "starts_at": "2026-11-22T10:00:00Z",
            "ends_at": "2026-11-22T11:00:00Z",
        },
    ).json()

    # Create event on Nov 24
    ev24 = bharat.post(
        "/calendar/events",
        json={
            "scope_kind": "personal",
            "title": "Nov 24 Event",
            "starts_at": "2026-11-24T10:00:00Z",
            "ends_at": "2026-11-24T11:00:00Z",
        },
    ).json()

    # Query range covering Nov 22 only
    r_range = bharat.get("/calendar/events?start=2026-11-22T00:00:00Z&end=2026-11-22T23:59:59Z").json()
    ids_in_range = {e["id"] for e in r_range}
    assert ev22["id"] in ids_in_range
    assert ev24["id"] not in ids_in_range


def test_calendar_sources_endpoint(as_user, ids):
    """Sources endpoint returns personal, site, and readable workspaces with roles."""
    bharat = as_user("bharat")
    sources = bharat.get("/calendar/sources").json()

    source_ids = {s["id"] for s in sources}
    assert "personal" in source_ids
    assert "site" in source_ids

    # Section A and Division should be in readable sources
    sec_a_id = ids["workspaces"]["section_a"]
    assert sec_a_id in source_ids


def test_panel_session_denial(as_user, ids):
    """Touch panel session cannot access calendar (returns 401)."""
    bharat = as_user("bharat")
    r = bharat.get(
        "/calendar/events?start=2026-11-20T00:00:00Z&end=2026-11-20T23:59:59Z",
        headers={"x-labadda-panel": "true"},
    )
    assert r.status_code == 401
