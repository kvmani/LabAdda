"""One-level contribution rights never widen content visibility or moderation."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from labadda import policy
from labadda.models import ContributionDelegation, Membership, User, Workspace
from labadda.security import utcnow


@pytest.mark.parametrize(
    "name,key,allowed",
    [
        ("bharat", "section_a", True),
        ("bharat", "division", False),
        ("asha", "division", True),
        ("asha", "group", False),
        ("deepa", "group", True),
        ("admin", "root", False),
        ("farhan", "section_a", False),
        ("esha", "project", True),
    ],
)
def test_contribution_matrix(db_factory, ids, name, key, allowed):
    with db_factory() as db:
        workspace = db.get(Workspace, uuid.UUID(ids["workspaces"][key]))
        assert (uuid.UUID(ids["users"][name]) in policy.contribution_user_ids(db, workspace)) == allowed


def test_delegate_is_parent_specific_and_expires(db_factory, ids):
    with db_factory() as db:
        section = uuid.UUID(ids["workspaces"]["section_a"])
        division = db.get(Workspace, uuid.UUID(ids["workspaces"]["division"]))
        user = db.get(User, uuid.UUID(ids["users"]["bharat"]))
        grant = ContributionDelegation(
            source_id=section,
            destination_id=division.id,
            user_id=user.id,
            granted_by=uuid.UUID(ids["users"]["asha"]),
        )
        db.add(grant)
        db.flush()
        assert user.id in policy.contribution_user_ids(db, division)
        group = db.get(Workspace, uuid.UUID(ids["workspaces"]["group"]))
        assert user.id not in policy.contribution_user_ids(db, group)
        grant.expires_at = utcnow() - timedelta(seconds=1)
        db.flush()
        assert user.id not in policy.contribution_user_ids(db, division)
        grant.expires_at = None
        grant.revoked_at = utcnow()
        db.flush()
        assert user.id not in policy.contribution_user_ids(db, division)


def test_delegation_requires_current_subtree_and_parent(db_factory, ids):
    with db_factory() as db:
        section = db.get(Workspace, uuid.UUID(ids["workspaces"]["section_a"]))
        division = db.get(Workspace, uuid.UUID(ids["workspaces"]["division"]))
        user_id = uuid.UUID(ids["users"]["bharat"])
        db.add(
            ContributionDelegation(
                source_id=section.id,
                destination_id=division.id,
                user_id=user_id,
                granted_by=uuid.UUID(ids["users"]["asha"]),
            )
        )
        db.flush()
        membership = db.scalar(
            select(Membership).where(Membership.user_id == user_id, Membership.workspace_id == section.id)
        )
        db.delete(membership)
        db.flush()
        assert user_id not in policy.contribution_user_ids(db, division)


def test_direct_parent_member_and_read_only_override(db_factory, ids):
    with db_factory() as db:
        workspace = db.get(Workspace, uuid.UUID(ids["workspaces"]["division"]))
        user_id = uuid.UUID(ids["users"]["bharat"])
        db.add(Membership(workspace_id=workspace.id, user_id=user_id, role="member"))
        db.flush()
        assert user_id in policy.contribution_user_ids(db, workspace)
        workspace.posting_policy = "read_only"
        db.flush()
        assert user_id not in policy.contribution_user_ids(db, workspace)
        assert uuid.UUID(ids["users"]["deepa"]) in policy.contribution_user_ids(db, workspace)
        workspace.archived = True
        assert policy.contribution_user_ids(db, workspace) == set()


def test_steward_appoints_and_parent_revokes(as_user, ids):
    source = ids["workspaces"]["section_a"]
    destination = ids["workspaces"]["division"]
    body = {"user_id": ids["users"]["bharat"], "reason": "Represent the section"}
    created = as_user("asha").post(f"/workspaces/{source}/delegations", json=body)
    assert created.status_code == 201
    grant = created.json()
    duplicate = as_user("asha").post(f"/workspaces/{source}/delegations", json=body)
    assert duplicate.status_code == 409
    revoked = as_user("deepa").post(
        f"/workspaces/{destination}/delegations/{grant['id']}/revoke",
        json={"revision": grant["revision"], "reason": "Representation completed"},
    )
    assert revoked.status_code == 200
    stale = as_user("asha").post(
        f"/workspaces/{source}/delegations/{grant['id']}/revoke",
        json={"revision": grant["revision"], "reason": "Representation completed"},
    )
    assert stale.status_code == 409


@pytest.mark.parametrize(
    "name,expected", [("bharat", 403), ("deepa", 404), ("chitra", 404), ("admin", 404), ("esha", 404)]
)
def test_appointment_denial_matrix(as_user, ids, name, expected):
    source = ids["workspaces"]["section_a"]
    response = as_user(name).post(
        f"/workspaces/{source}/delegations",
        json={"user_id": ids["users"]["bharat"], "reason": "Represent the section"},
    )
    assert response.status_code == expected


def test_appointment_rejects_sibling_and_naive_expiry(as_user, ids):
    client = as_user("asha")
    url = f"/workspaces/{ids['workspaces']['section_a']}/delegations"
    response = client.post(url, json={"user_id": ids["users"]["chitra"], "reason": "Invalid sibling"})
    assert response.status_code == 422
    response = client.post(
        url,
        json={
            "user_id": ids["users"]["bharat"],
            "reason": "Invalid expiry",
            "expires_at": "2099-01-01T00:00:00",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "resource,body",
    [
        ("posts", {"body": "Higher unit contribution"}),
        ("chat", {"body": "Higher unit contribution", "client_id": "representative-01"}),
        (
            "board/ops",
            {
                "op_id": "representative-01",
                "epoch": 1,
                "type": "add",
                "object_id": "representative-note",
                "payload": {
                    "kind": "text",
                    "data": {"x": 10, "y": 10, "text": "Unit summary", "color": "#1f2933"},
                },
            },
        ),
    ],
)
def test_inherited_member_can_read_but_needs_delegation_to_write(as_user, ids, resource, body):
    division = ids["workspaces"]["division"]
    bharat = as_user("bharat")
    detail = bharat.get(f"/workspaces/{division}").json()
    assert detail["can_write"] is True
    assert detail["can_contribute"] is False
    denied = bharat.post(f"/workspaces/{division}/{resource}", json=body)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "representative_required"
    appointed = as_user("asha").post(
        f"/workspaces/{ids['workspaces']['section_a']}/delegations",
        json={"user_id": ids["users"]["bharat"], "reason": "Represent our section"},
    )
    assert appointed.status_code == 201
    assert bharat.get(f"/workspaces/{division}").json()["can_contribute"] is True
    accepted = bharat.post(f"/workspaces/{division}/{resource}", json=body)
    assert accepted.status_code in (200, 201)


def test_leaving_and_rejoining_does_not_restore_delegation(as_user, ids):
    source = ids["workspaces"]["section_a"]
    user = ids["users"]["bharat"]
    created = as_user("asha").post(
        f"/workspaces/{source}/delegations", json={"user_id": user, "reason": "Represent our section"}
    )
    assert created.status_code == 201
    admin = as_user("admin")
    assert admin.delete(f"/admin/workspaces/{source}/memberships/{user}").status_code == 200
    assert admin.put(f"/admin/workspaces/{source}/memberships", json={"user_id": user}).status_code == 200
    detail = as_user("bharat").get(f"/workspaces/{ids['workspaces']['division']}").json()
    assert detail["can_contribute"] is False


def test_panel_intent_cannot_manage_representation(as_user, ids):
    response = as_user("asha").get(
        f"/workspaces/{ids['workspaces']['section_a']}/delegations", headers={"X-LabAdda-Panel": "1"}
    )
    assert response.status_code == 401


def test_delegation_downgrade_preserves_authority_history(as_user, ids, migrated):
    from alembic import command

    from labadda.cli import alembic_config

    result = as_user("asha").post(
        f"/workspaces/{ids['workspaces']['section_a']}/delegations",
        json={"user_id": ids["users"]["bharat"], "reason": "Retain authority history"},
    )
    assert result.status_code == 201
    with pytest.raises(RuntimeError, match="Delegation history"):
        command.downgrade(alembic_config(migrated), "0046")
    assert (
        as_user("asha").get(f"/workspaces/{ids['workspaces']['section_a']}/delegations").json()["delegations"]
    )


@pytest.mark.parametrize("operation", ["update", "move", "erase"])
def test_contributor_cannot_modify_another_authors_object(as_user, ids, operation):
    workspace = ids["workspaces"]["section_a"]
    path = f"/workspaces/{workspace}/board/ops"
    created = as_user("asha").post(
        path,
        json={
            "op_id": "owner-note-create",
            "epoch": 1,
            "type": "add",
            "object_id": "owner-note",
            "payload": {
                "kind": "text",
                "data": {"x": 10, "y": 10, "text": "Author owned", "color": "#1f2933"},
            },
        },
    )
    assert created.status_code == 200
    response = as_user("bharat").post(
        path,
        json={
            "op_id": "other-note-change",
            "epoch": 1,
            "type": operation,
            "object_id": "owner-note",
            "base_revision": 1,
            "payload": {"dx": 10, "dy": 10, "data": {"x": 10, "y": 10, "text": "Changed"}},
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "author_required"


def test_moving_a_unit_away_and_back_does_not_restore_delegation(as_user, ids):
    source = ids["workspaces"]["section_a"]
    assert (
        as_user("asha")
        .post(
            f"/workspaces/{source}/delegations",
            json={"user_id": ids["users"]["bharat"], "reason": "Represent the section"},
        )
        .status_code
        == 201
    )
    admin = as_user("admin")
    for parent in [ids["workspaces"]["group"], ids["workspaces"]["division"]]:
        result = admin.patch(
            f"/admin/workspaces/{source}",
            json={"move": True, "parent_id": parent, "reason": "Reorganise fictional units"},
        )
        assert result.status_code == 200
    assert (
        as_user("bharat").get(f"/workspaces/{ids['workspaces']['division']}").json()["can_contribute"]
        is False
    )


def test_both_socket_permission_paths_recheck_delegation(as_user, ids, db_factory, settings):
    from labadda.models import AuthSession
    from labadda.realtime import Connection, Hub

    as_user("bharat")
    user_id = uuid.UUID(ids["users"]["bharat"])
    workspace = uuid.UUID(ids["workspaces"]["division"])
    with db_factory() as db:
        session_id = db.scalar(select(AuthSession.id).where(AuthSession.user_id == user_id))
    connection = Connection(None, user_id, session_id, "Bharat Kulkarni")
    hub = Hub(db_factory, settings)
    assert hub._check(connection, {workspace}) == (True, {workspace}, set())
    assert hub._check_many([connection], workspace)[connection] == (True, True, False)
    result = as_user("asha").post(
        f"/workspaces/{ids['workspaces']['section_a']}/delegations",
        json={"user_id": str(user_id), "reason": "Represent section during discussion"},
    )
    assert result.status_code == 201
    assert hub._check(connection, {workspace}) == (True, {workspace}, {workspace})
    assert hub._check_many([connection], workspace)[connection] == (True, True, True)
    with db_factory() as db:
        grant = db.get(ContributionDelegation, uuid.UUID(result.json()["id"]))
        grant.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert hub._check(connection, {workspace}) == (True, {workspace}, set())
    assert hub._check_many([connection], workspace)[connection] == (True, True, False)


def test_unit_can_have_four_independent_representatives(as_user, ids):
    source = ids["workspaces"]["section_a"]
    destination = ids["workspaces"]["division"]
    admin = as_user("admin")
    for name in ["chitra", "esha", "deepa"]:
        assert (
            admin.put(
                f"/admin/workspaces/{source}/memberships", json={"user_id": ids["users"][name]}
            ).status_code
            == 200
        )
    steward = as_user("asha")
    grants = []
    for name in ["bharat", "chitra", "esha", "deepa"]:
        result = steward.post(
            f"/workspaces/{source}/delegations",
            json={"user_id": ids["users"][name], "reason": "Represent the section together"},
        )
        assert result.status_code == 201
        grants.append(result.json())
    assert len(steward.get(f"/workspaces/{source}/delegations").json()["delegations"]) == 4
    revoked = steward.post(
        f"/workspaces/{source}/delegations/{grants[0]['id']}/revoke",
        json={"revision": 1, "reason": "End one appointment only"},
    )
    assert revoked.status_code == 200
    assert as_user("bharat").get(f"/workspaces/{destination}").json()["can_contribute"] is False
    for name in ["chitra", "esha", "deepa", "asha"]:
        assert as_user(name).get(f"/workspaces/{destination}").json()["can_contribute"] is True


def test_demoted_steward_cannot_undo_another_authors_item(as_user, ids):
    from tests.test_board_pilot_safety import operation

    workspace = ids["workspaces"]["section_a"]
    path = f"/workspaces/{workspace}/board"
    bharat = as_user("bharat")
    asha = as_user("asha")
    assert operation(bharat, path, "add").status_code == 200
    assert operation(asha, path, "update", revision=1).status_code == 200
    admin = as_user("admin")
    assert (
        admin.put(
            f"/admin/workspaces/{workspace}/memberships",
            json={"user_id": ids["users"]["bharat"], "role": "steward"},
        ).status_code
        == 200
    )
    assert (
        admin.put(
            f"/admin/workspaces/{workspace}/memberships",
            json={"user_id": ids["users"]["asha"], "role": "member"},
        ).status_code
        == 200
    )
    result = operation(asha, path, "undo")
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "author_required"
