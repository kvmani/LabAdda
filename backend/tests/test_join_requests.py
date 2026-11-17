"""Tests for voluntary membership application and admin review."""

from labadda.models import JoinRequest, User, Workspace


def test_public_units_list_hides_private_groups_and_projects(make_client, db_factory):
    """Signed-out applicants see organisation units only; private groups and projects stay hidden."""
    with db_factory() as db:
        private = [w.name for w in db.query(Workspace).filter(Workspace.kind != "org").all()]
    assert private
    anon = make_client()
    res = anon.get("/join-requests/units")
    assert res.status_code == 200
    units = res.json()["units"]
    assert units
    assert all(u["kind"] == "org" for u in units)
    assert not set(private) & {u["name"] for u in units}


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


def test_submit_does_not_reveal_existing_usernames_or_employee_numbers(make_client, db_factory):
    """A known username, a known employee number and a fresh one all get the same answer."""
    with db_factory() as db:
        db.query(User).filter_by(username="bharat").one().employee_no = "EMP-1001"
        db.commit()
    anon = make_client()
    known = anon.post("/join-requests", json={"full_name": "Bharat Two", "username": "admin"})
    known_emp = anon.post(
        "/join-requests", json={"full_name": "Kavya Rao", "username": "kavya.rao", "employee_no": "emp-1001"}
    )
    fresh = anon.post("/join-requests", json={"full_name": "Priya Nair", "username": "priya.nair"})
    again = anon.post("/join-requests", json={"full_name": "Priya Nair", "username": "priya.nair"})
    for res in (known, known_emp, fresh, again):
        assert res.status_code == 200
        assert set(res.json()) == {"id", "status", "message"}
        assert res.json()["message"] == fresh.json()["message"]


def test_submit_is_rate_limited_per_client(make_client):
    anon = make_client()
    codes = [
        anon.post("/join-requests", json={"full_name": "Ravi Iyer", "username": f"ravi{n}"}).status_code
        for n in range(11)
    ]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429


def test_submit_refuses_untrusted_origin(make_client):
    res = make_client().post(
        "/join-requests",
        json={"full_name": "Ravi Iyer", "username": "ravi.iyer"},
        headers={"origin": "https://elsewhere.example"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "bad_origin"


def test_submit_refuses_a_private_group_as_unit(make_client, db_factory):
    with db_factory() as db:
        group_id = str(db.query(Workspace).filter(Workspace.kind == "group").first().id)
    res = make_client().post(
        "/join-requests", json={"full_name": "Ravi Iyer", "username": "ravi.iyer", "unit_id": group_id}
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_unit"


def test_approval_never_joins_a_private_group_named_by_the_applicant(as_user, db_factory):
    with db_factory() as db:
        group = db.query(Workspace).filter(Workspace.kind == "group").first()
        req = JoinRequest(full_name="Ravi Iyer", username="ravi.iyer", unit_name=group.name, status="pending")
        db.add(req)
        db.commit()
        req_id, group_id = str(req.id), group.id
    res = as_user("admin").post(f"/admin/join-requests/{req_id}/approve")
    assert res.status_code == 200
    with db_factory() as db:
        created = db.query(User).filter_by(username="ravi.iyer").one()
        assert created.home_workspace_id != group_id
        assert db.get(Workspace, created.home_workspace_id).kind == "org"


def test_approval_refuses_a_username_already_in_use(as_user, db_factory):
    with db_factory() as db:
        req = JoinRequest(full_name="Second Asha", username="asha", status="pending")
        db.add(req)
        db.commit()
        req_id = str(req.id)
    res = as_user("admin").post(f"/admin/join-requests/{req_id}/approve")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "username_taken"
    with db_factory() as db:
        assert db.get(JoinRequest, req.id).status == "pending"


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
