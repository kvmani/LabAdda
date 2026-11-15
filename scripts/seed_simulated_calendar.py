"""Seed rich simulated calendar events for November 2026."""

import uuid
from datetime import datetime, timezone
from labadda.config import get_settings
from labadda.db import session_factory
from labadda.models import CalendarEvent, User, Workspace

settings = get_settings()
db = session_factory(settings.database_url)()

# Find users
admin = db.query(User).filter(User.username == "admin").first()
bharat = db.query(User).filter(User.username == "bharat").first()
deepa = db.query(User).filter(User.username == "deepa").first()
asha = db.query(User).filter(User.username == "asha").first()

if not bharat or not admin:
    print("Users not found")
    exit(1)

# Find workspaces
sed = db.query(Workspace).filter(Workspace.name.ilike("%Surface Engineering%")).first()
tfs = db.query(Workspace).filter(Workspace.name.ilike("%Thin Films%")).first()
club = db.query(Workspace).filter(Workspace.name.ilike("%Microscopy%")).first()
tejas = db.query(Workspace).filter(Workspace.name.ilike("%Tejas%")).first()

print(f"Admin: {admin.id}, Bharat: {bharat.id}")
print(f"SED: {sed.id if sed else None}, TFS: {tfs.id if tfs else None}")

# Clear existing calendar events to avoid duplicates
db.query(CalendarEvent).delete()

simulated_events = [
    # 1. Site-wide Institute events
    {
        "scope_kind": "site",
        "workspace_id": None,
        "owner_id": None,
        "created_by": admin.id,
        "title": "National Science Day Planning Seminar",
        "description": "Annual keynote address and research presentation coordination across divisions.",
        "location": "Dr. Raman Auditorium",
        "starts_at": datetime(2026, 11, 16, 9, 30, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 16, 12, 30, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#1565c0",
    },
    {
        "scope_kind": "site",
        "workspace_id": None,
        "owner_id": None,
        "created_by": admin.id,
        "title": "Air-Gap Network & Server Maintenance Window",
        "description": "Scheduled offline backup and hardware integrity inspection.",
        "location": "Main Server Room",
        "starts_at": datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 22, 23, 59, tzinfo=timezone.utc),
        "all_day": True,
        "color": "#c62828",
    },
    {
        "scope_kind": "site",
        "workspace_id": None,
        "owner_id": None,
        "created_by": admin.id,
        "title": "Director's All-Hands Institute Address",
        "description": "Quarterly achievements review and upcoming project roadmap release.",
        "location": "Auditorium & Virtual Stream",
        "starts_at": datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 27, 16, 30, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#1565c0",
    },

    # 2. Division events (Surface Engineering Division)
    {
        "scope_kind": "workspace",
        "workspace_id": sed.id if sed else None,
        "owner_id": None,
        "created_by": deepa.id if deepa else admin.id,
        "title": "SED Monthly Progress & Milestone Review",
        "description": "Review progress reports from Thin Films and Corrosion sections.",
        "location": "SED Conference Hall 2B",
        "starts_at": datetime(2026, 11, 18, 14, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 18, 16, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#6a1b9a",
    },
    {
        "scope_kind": "workspace",
        "workspace_id": sed.id if sed else None,
        "owner_id": None,
        "created_by": deepa.id if deepa else admin.id,
        "title": "Division Budget & Capital Equipment Allocation",
        "description": "Finalize allocation for high-vacuum deposition system upgrades.",
        "location": "Division Head Office",
        "starts_at": datetime(2026, 11, 25, 11, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#6a1b9a",
    },

    # 3. Section events (Thin Films Section)
    {
        "scope_kind": "workspace",
        "workspace_id": tfs.id if tfs else None,
        "owner_id": None,
        "created_by": bharat.id,
        "title": "PVD Chamber Target Alignment & Calibration",
        "description": "Calibrate magnetron sputtering sources for titanium nitride coatings.",
        "location": "Thin Films Lab 104",
        "starts_at": datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#00838f",
    },
    {
        "scope_kind": "workspace",
        "workspace_id": tfs.id if tfs else None,
        "owner_id": None,
        "created_by": asha.id if asha else bharat.id,
        "title": "Weekly Section Scrum & XRD Sample Dispatch",
        "description": "Weekly status update on wafer batches sent for X-ray diffraction.",
        "location": "Section Discussion Room",
        "starts_at": datetime(2026, 11, 20, 11, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#00838f",
    },
    {
        "scope_kind": "workspace",
        "workspace_id": tfs.id if tfs else None,
        "owner_id": None,
        "created_by": bharat.id,
        "title": "Chamber Bake-Out & Ultra-High Vacuum Check",
        "description": "Overnight bake-out cycle to reach 10^-8 Torr baseline.",
        "location": "Vacuum Rig A",
        "starts_at": datetime(2026, 11, 24, 16, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#00838f",
    },

    # 4. Project Tejas
    {
        "scope_kind": "workspace",
        "workspace_id": tejas.id if tejas else None,
        "owner_id": None,
        "created_by": deepa.id if deepa else admin.id,
        "title": "Tejas Pilot Milestone 2 Flight Test Review",
        "description": "Thermal barrier coating integrity under cyclic high-temperature simulation.",
        "location": "Project Tejas War Room",
        "starts_at": datetime(2026, 11, 19, 14, 30, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 19, 17, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#ef6c00",
    },

    # 5. Collaborative Group (Microscopy Journal Club)
    {
        "scope_kind": "workspace",
        "workspace_id": club.id if club else None,
        "owner_id": None,
        "created_by": bharat.id,
        "title": "Journal Club: In-situ HRTEM of Grain Growth",
        "description": "Discussion led by Dr. Bharat on atomic-scale observation of grain boundaries.",
        "location": "Library Seminar Room 1",
        "starts_at": datetime(2026, 11, 21, 15, 30, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 21, 17, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#2e7d32",
    },

    # 6. Bharat's Personal Calendar (strictly private)
    {
        "scope_kind": "personal",
        "workspace_id": None,
        "owner_id": bharat.id,
        "created_by": bharat.id,
        "title": "Draft SiC Thin Films Manuscript for Journal",
        "description": "Focus time: complete results and discussion section on hardness tests.",
        "location": "Cabin 12",
        "starts_at": datetime(2026, 11, 17, 14, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 17, 16, 30, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#d81b60",
    },
    {
        "scope_kind": "personal",
        "workspace_id": None,
        "owner_id": bharat.id,
        "created_by": bharat.id,
        "title": "One-on-One Technical Mentoring with Anish",
        "description": "Review Python data processing script for XRD peak deconvolution.",
        "location": "Office Bench 3",
        "starts_at": datetime(2026, 11, 18, 11, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#d81b60",
    },
    {
        "scope_kind": "personal",
        "workspace_id": None,
        "owner_id": bharat.id,
        "created_by": bharat.id,
        "title": "Prepare Presentation Slides for Monday Rollout",
        "description": "Finalize feature walkthrough deck and simulated lab screenshots.",
        "location": "Work Desk",
        "starts_at": datetime(2026, 11, 23, 9, 30, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 11, 23, 11, 30, tzinfo=timezone.utc),
        "all_day": False,
        "color": "#d81b60",
    },
]

for ev in simulated_events:
    if ev["scope_kind"] == "workspace" and not ev["workspace_id"]:
        continue
    db_ev = CalendarEvent(
        id=uuid.uuid4(),
        scope_kind=ev["scope_kind"],
        workspace_id=ev["workspace_id"],
        owner_id=ev["owner_id"],
        created_by=ev["created_by"],
        title=ev["title"],
        description=ev["description"],
        location=ev["location"],
        starts_at=ev["starts_at"],
        ends_at=ev["ends_at"],
        all_day=ev["all_day"],
        color=ev["color"],
    )
    db.add(db_ev)

db.commit()
print(f"Successfully seeded {len(simulated_events)} calendar events.")
