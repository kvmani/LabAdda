"""Fictional development fixture. Refused outside development and test."""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Membership, User, Workspace
from .security import hash_password

TREE = [
    # key, name, parent key
    ("root", "Northwind Research", None),
    ("group", "Materials Group", "root"),
    ("division", "Surface Science Division", "group"),
    ("section_a", "Thin Films Section", "division"),
    ("section_b", "Catalysis Section", "division"),
]
USERS = [
    # username, display name, is_admin, is_active
    ("admin", "Site Administrator", True, True),
    ("asha", "Asha Rao", False, True),
    ("ben", "Ben Okafor", False, True),
    ("chen", "Chen Li", False, True),
    ("dana", "Dana Whitfield", False, True),
    ("eli", "Eli Novak", False, True),
    ("fay", "Fay Moreau", False, False),
]
GRANTS = [
    ("asha", "section_a", "steward"),
    ("ben", "section_a", "member"),
    ("chen", "section_b", "member"),
    ("dana", "division", "steward"),
    ("eli", "project", "member"),
    ("dana", "project", "steward"),
    ("fay", "section_a", "member"),
    # A user-created collaborative group spanning two sibling sections.
    ("ben", "reading_club", "steward"),
    ("chen", "reading_club", "member"),
]
HOMES = {"asha": "section_a", "ben": "section_a", "chen": "section_b", "dana": "division", "eli": "project"}


def fixture_password() -> str:
    return os.environ.get("LABADDA_FIXTURE_PASSWORD", "fixture-pass-123")


def reset_database(db: Session) -> None:
    tables = ["usage_reader_grants", "storage_inspections", "usage_observations", "policy_drafts", "panel_pairings", "board_snapshots", "board_ops", "boards", "chat_reads", "chat_messages", "notifications", "assets", "notes", "posts",
              "audit_events", "memberships", "credential_tokens", "auth_sessions"]
    db.execute(text("UPDATE users SET home_workspace_id = NULL"))
    db.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
    db.execute(text("UPDATE workspaces SET created_by = NULL"))
    db.execute(text("DELETE FROM workspaces"))
    db.execute(text("DELETE FROM users"))
    db.commit()


def seed(db: Session) -> dict[str, object]:
    password_hash = hash_password(fixture_password())
    ws: dict[str, Workspace] = {}
    for key, name, parent in TREE:
        w = Workspace(kind="org", name=name, parent_id=ws[parent].id if parent else None)
        db.add(w)
        db.flush()
        ws[key] = w
    ws["project"] = Workspace(kind="project", name="Project Aurora", description="Invite-only pilot project")
    db.add(ws["project"])
    users: dict[str, User] = {}
    for username, display, is_admin, active in USERS:
        u = User(username=username, display_name=display, is_admin=is_admin, is_active=active,
                 password_hash=password_hash, must_set_password=False)
        db.add(u)
        users[username] = u
    db.flush()
    ws["reading_club"] = Workspace(kind="group", name="Microscopy Reading Club", created_by=users["ben"].id,
                                   description="Colleagues from Thin Films and Catalysis reading papers together")
    db.add(ws["reading_club"])
    db.flush()
    for username, key, role in GRANTS:
        db.add(Membership(user_id=users[username].id, workspace_id=ws[key].id, role=role))
    for username, key in HOMES.items():
        users[username].home_workspace_id = ws[key].id
    db.commit()
    return {"workspaces": {k: str(v.id) for k, v in ws.items()}, "users": {k: str(v.id) for k, v in users.items()}}
