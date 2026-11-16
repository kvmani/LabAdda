"""Tests for voluntary membership application and admin review."""

from labadda.models import JoinRequest, User, Workspace


def test_public_units_list(make_client):
    """Prospective applicants can query available org units and groups without signing in."""
    anon = make_client()
    res = anon.get("/join-requests/units")
    assert res.status_code == 200
    data = res.json()
    assert "units" in data
    assert len(data["units"]) > 0
    assert all(u["kind"] in ("org", "group") for u in data["units"])


def test_submit_voluntary_join_request(make_client, db_factory):
    """A user can submit a voluntary application with profile details."""
    with db_factory() as db:
        unit = db.query(Workspace).filter(Workspace.kind == "org", Workspace.parent_id.is_(None)).first()
        assert unit is not None
        unit_id = str(unit.id)
        unit_name = unit.name

    anon = make_client()
    payload = {
        "full_name": "Dr. Sunita Sharma",
        "username": "sunita.sharma",
        "employee_no": "EMP-4102",
        "contact_email": "sunita.sharma@nmrl.res.in",
        "contact_phone": "Ext 4412",
        "designation": "Senior Scientist",
        "unit_id": unit_id,
        "statement_of_interest": "Collaborating on corrosion trial analysis with the Tejas team.",
    }

    res = anon.post("/join-requests", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"
    assert "Thank you" in data["message"]

    # Verify persisted in database
    with db_factory() as db:
        req = db.query(JoinRequest).filter_by(username="sunita.sharma").first()
        assert req is not None
        assert req.full_name == "Dr. Sunita Sharma"
        assert req.employee_no == "EMP-4102"
        assert req.status == "pending"
        assert str(req.unit_id) == unit_id
        assert req.unit_name == unit_name


def test_submit_duplicate_username_conflicts(make_client):
    """Submitting an existing username is refused with 409 username_taken."""
    anon = make_client()
    payload = {
        "full_name": "Duplicate Admin",
        "username": "admin",
        "employee_no": "EMP-9999",
    }
    res = anon.post("/join-requests", json=payload)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "username_taken"


def test_submit_pending_duplicate_conflicts(make_client):
    """Submitting twice with same username while pending is refused."""
    anon = make_client()
    payload = {
        "full_name": "Priya Nair",
        "username": "priya.nair",
        "employee_no": "EMP-4888",
    }
    res1 = anon.post("/join-requests", json=payload)
    assert res1.status_code == 200

    res2 = anon.post("/join-requests", json=payload)
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "already_applied"


def test_admin_join_requests_authorization(make_client, as_user):
    """Regular members or signed-out users cannot access admin join-request endpoints."""
    # Signed out -> 401
    anon = make_client()
    res = anon.get("/admin/join-requests")
    assert res.status_code == 401

    # Regular user -> 403
    bharat = as_user("bharat")
    res = bharat.get("/admin/join-requests")
    assert res.status_code == 403


def test_admin_approve_join_request(make_client, as_user, db_factory):
    """Admin can approve a join request, creating user and generating activation code."""
    with db_factory() as db:
        unit = db.query(Workspace).filter(Workspace.kind == "org").first()
        req = JoinRequest(
            full_name="Rajesh Verma",
            username="rajesh.verma",
            employee_no="EMP-5555",
            contact_email="rajesh.verma@nmrl.res.in",
            contact_phone="Ext 4880",
            designation="Technical Officer",
            unit_id=unit.id,
            unit_name=unit.name,
            statement_of_interest="Material testing equipment operation",
            status="pending",
        )
        db.add(req)
        db.commit()
        req_id = str(req.id)
        unit_id = unit.id

    admin = as_user("admin")
    res = admin.post(f"/admin/join-requests/{req_id}/approve")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "approved"
    assert "activation" in data
    assert "code" in data["activation"]
    assert "expires_at" in data["activation"]
    assert data["user"]["username"] == "rajesh.verma"

    # Verify user created in DB
    with db_factory() as db:
        created = db.query(User).filter_by(username="rajesh.verma").first()
        assert created is not None
        assert created.status == "invited"
        assert created.must_set_password is True
        assert created.employee_no == "EMP-5555"
        assert created.home_workspace_id == unit_id

        # Verify join request updated
        r = db.get(JoinRequest, req.id)
        assert r.status == "approved"
        assert r.created_user_id == created.id


def test_admin_reject_join_request(as_user, db_factory):
    """Admin can reject a join request with a note."""
    with db_factory() as db:
        req = JoinRequest(
            full_name="Unknown Person",
            username="unknown.person",
            employee_no="EMP-0000",
            status="pending",
        )
        db.add(req)
        db.commit()
        req_id = str(req.id)

    admin = as_user("admin")
    res = admin.post(
        f"/admin/join-requests/{req_id}/reject",
        json={"reason": "Staff record could not be verified with lab HR list"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    with db_factory() as db:
        r = db.get(JoinRequest, req.id)
        assert r.status == "rejected"
        assert r.review_note == "Staff record could not be verified with lab HR list"


def test_submit_with_custom_unit_and_admin_approval_creates_unit(make_client, as_user, db_factory):
    """User can submit an unlisted division/section; admin approval registers it in DB."""
    anon = make_client()
    payload = {
        "full_name": "Dr. Manisha Roy",
        "username": "manisha.roy",
        "employee_no": "EMP-6601",
        "contact_email": "manisha.roy@nmrl.res.in",
        "designation": "Research Fellow",
        "unit_id": None,
        "custom_unit_name": "Advanced Composites Section",
        "statement_of_interest": "Polymer matrix composite evaluation",
    }
    res = anon.post("/join-requests", json=payload)
    assert res.status_code == 200
    req_id = res.json()["id"]

    with db_factory() as db:
        req = db.query(JoinRequest).filter_by(username="manisha.roy").first()
        assert req is not None
        assert req.unit_id is None
        assert req.unit_name == "Advanced Composites Section"

    # Admin approves
    admin = as_user("admin")
    approve_res = admin.post(f"/admin/join-requests/{req_id}/approve", json={})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # Verify unit and user created
    with db_factory() as db:
        created_ws = db.query(Workspace).filter_by(name="Advanced Composites Section").first()
        assert created_ws is not None
        assert created_ws.kind == "org"

        user = db.query(User).filter_by(username="manisha.roy").first()
        assert user is not None
        assert user.home_workspace_id == created_ws.id

        r = db.get(JoinRequest, req.id)
        assert r.unit_id == created_ws.id
        assert r.unit_name == "Advanced Composites Section"


def test_admin_approve_with_corrections(as_user, db_factory):
    """Admin can correct applicant details (e.g. employee_no, unit) upon review."""
    with db_factory() as db:
        unit = db.query(Workspace).filter(Workspace.kind == "org").first()
        req = JoinRequest(
            full_name="Kavita Sen",
            username="kavita.sen",
            employee_no="TEMP-01",
            designation="Junior Analyst",
            unit_id=None,
            unit_name="Unverified Unit",
            status="pending",
        )
        db.add(req)
        db.commit()
        req_id = str(req.id)
        unit_id = str(unit.id)

    admin = as_user("admin")
    res = admin.post(
        f"/admin/join-requests/{req_id}/approve",
        json={
            "employee_no": "EMP-8802",
            "designation": "Senior Scientific Officer",
            "unit_id": unit_id,
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    with db_factory() as db:
        user = db.query(User).filter_by(username="kavita.sen").first()
        assert user is not None
        assert user.employee_no == "EMP-8802"
        assert user.designation == "Senior Scientific Officer"
        assert str(user.home_workspace_id) == unit_id
