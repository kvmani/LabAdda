"""Seed a realistic 50-user National Fundamental and Advanced Science Centre, Mumbai (NFASC) simulation.

Follows repository guidelines (Indian names, air-gapped laboratory hierarchy,
realistic research workflows across all roles).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path

# Add backend directory to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from labadda import __version__, audit, people
from labadda.db import session_factory
from labadda.fixtures import reset_database
from labadda.models import (
    Board,
    BoardSnapshot,
    ChatMessage,
    Membership,
    Note,
    Post,
    SiteBroadcast,
    TodoList,
    TodoTask,
    UnitAdminGrant,
    UnitPosition,
    User,
    Workspace,
)
from labadda.security import hash_password, utcnow

DATABASE_URL = os.environ.get(
    "LABADDA_DATABASE_URL",
    "postgresql+psycopg://labadda:labadda-dev@localhost:5432/labadda_dev",
)

FIXTURE_PASSWORD = os.environ.get("LABADDA_FIXTURE_PASSWORD", "fixture-pass-123")


# 50 Realistic Indian Scientists, Engineers, and Staff
USERS_DATA = [
    # (username, display_name, title, is_admin, home_key, is_steward)
    ("admin", "Site Administrator", "Systems Operations Officer", True, "root", False),
    (
        "vikram",
        "Dr. Vikram Sarabhai",
        "Director, Materials Group",
        False,
        "group_mg",
        True,
    ),
    (
        "deepa",
        "Dr. Deepa Nair",
        "Head, Surface Engineering Division",
        False,
        "div_sed",
        True,
    ),
    ("asha", "Dr. Asha Rao", "Head, Thin Films Section", False, "sec_tfs", True),
    (
        "arvind",
        "Dr. Arvind Swaminathan",
        "Head, Corrosion Section",
        False,
        "sec_cs",
        True,
    ),
    ("kavita", "Dr. Kavita Krishnan", "Head, Optics Division", False, "div_od", True),
    (
        "bharat",
        "Dr. Bharat Kulkarni",
        "Principal Scientist & Lead, Project Tejas",
        False,
        "sec_tfs",
        False,
    ),
    (
        "chitra",
        "Dr. Chitra Iyer",
        "Senior Scientist & Lead, Project Akash",
        False,
        "sec_cs",
        False,
    ),
    (
        "mira",
        "Dr. Mira Sen",
        "Senior Scientist & Lead, Project Surya",
        False,
        "sec_tfs",
        False,
    ),
    (
        "devendra",
        "Dr. Devendra Joshi",
        "Principal Scientist, Advanced Metallurgy",
        False,
        "div_amd",
        True,
    ),
    (
        "esha",
        "Esha Menon",
        "Senior Research Fellow, Thin Films",
        False,
        "sec_tfs",
        False,
    ),
    ("gita", "Gita Sen", "Scientist, Surface Metrology", False, "sec_tfs", False),
    (
        "hari",
        "Hari Rao",
        "Postdoctoral Fellow, PVD Sputtering",
        False,
        "sec_tfs",
        False,
    ),
    (
        "ananya",
        "Ananya Sharma",
        "Junior Research Fellow, Optical Coatings",
        False,
        "sec_tfs",
        False,
    ),
    (
        "rajesh",
        "Rajesh Verma",
        "Senior Technical Officer, Vacuum Systems",
        False,
        "sec_tfs",
        False,
    ),
    (
        "sneha",
        "Sneha Patel",
        "Materials Analyst, Interface Kinetics",
        False,
        "sec_cs",
        False,
    ),
    (
        "sunita",
        "Sunita Rao",
        "Senior Technical Officer, XRD Laboratory",
        False,
        "div_sed",
        False,
    ),
    (
        "pradeep",
        "Pradeep Bhatt",
        "Scientific Officer, Salt Fog Testing",
        False,
        "sec_cs",
        False,
    ),
    (
        "neha",
        "Neha Kulkarni",
        "Research Scientist, Thermal Barrier Physics",
        False,
        "sec_tfs",
        False,
    ),
    ("rahul", "Rahul Deshmukh", "High Vacuum System Engineer", False, "sec_tfs", False),
    (
        "pooja",
        "Pooja Mehta",
        "Research Associate, Nanocoatings",
        False,
        "sec_ncs",
        True,
    ),
    (
        "sanjay",
        "Dr. Sanjay Gupta",
        "Principal Scientist, Computational Materials",
        False,
        "sec_cms",
        True,
    ),
    ("meera", "Meera Nambiar", "Scientist, Laser Metrology", False, "sec_lss", False),
    (
        "ramesh",
        "Dr. Ramesh Pillai",
        "Scientist, High Temperature Alloys",
        False,
        "sec_htms",
        True,
    ),
    (
        "priya",
        "Priya Namboodiri",
        "Chemical Vapor Deposition Specialist",
        False,
        "sec_tfs",
        False,
    ),
    (
        "suresh",
        "Suresh Shenoy",
        "Instrumentation Engineer, Sensors",
        False,
        "sec_ss",
        True,
    ),
    (
        "divya",
        "Divya Balan",
        "Research Fellow, Electrochemical Impedance",
        False,
        "sec_cs",
        False,
    ),
    (
        "karthik",
        "Karthik Raman",
        "Metallurgical Engineer, Superalloys",
        False,
        "sec_htms",
        False,
    ),
    (
        "swati",
        "Swati Kulkarni",
        "Senior Technical Assistant, Electron Microscopy",
        False,
        "div_sed",
        False,
    ),
    ("manoj", "Manoj Tiwari", "Quality Assurance Officer", False, "group_mg", False),
    (
        "rekha",
        "Rekha Nayak",
        "Scientific Officer, Spectrophotometry",
        False,
        "sec_lss",
        True,
    ),
    ("alok", "Alok Saxena", "Cryogenics Specialist", False, "sec_ss", False),
    (
        "shalini",
        "Shalini Mishra",
        "Senior Research Fellow, Perovskites",
        False,
        "sec_tfs",
        False,
    ),
    (
        "tanvi",
        "Tanvi Shah",
        "Project Associate, Project Tejas",
        False,
        "sec_tfs",
        False,
    ),
    (
        "gautam",
        "Gautam Sen",
        "Division Safety & Radiation Officer",
        False,
        "div_sed",
        False,
    ),
    (
        "vidya",
        "Vidya Murthy",
        "Technical Assistant, Thin Film Profilometry",
        False,
        "sec_tfs",
        False,
    ),
    ("naveen", "Naveen Kumar", "Electron Beam PVD Technician", False, "sec_tfs", False),
    (
        "harish",
        "Harish Chandra",
        "Plasma Spray Coating Specialist",
        False,
        "sec_tfs",
        False,
    ),
    (
        "pallavi",
        "Pallavi Hegde",
        "Electrochemist, Marine Coatings",
        False,
        "sec_cs",
        False,
    ),
    ("tarun", "Tarun Roy", "Surface Profilometry Analyst", False, "sec_ncs", False),
    (
        "smita",
        "Smita Banerjee",
        "Research Scholar, High-k Dielectrics",
        False,
        "sec_tfs",
        False,
    ),
    (
        "rakesh",
        "Rakesh Sethi",
        "Scientific Officer, Micro-tribology",
        False,
        "sec_cs",
        False,
    ),
    (
        "aparna",
        "Aparna Sundaram",
        "Nanofabrication Specialist",
        False,
        "sec_ncs",
        False,
    ),
    ("vinay", "Vinay Prasad", "Optical Coating Engineer", False, "sec_ss", False),
    (
        "jyoti",
        "Jyoti Pandey",
        "Research Scholar, Corrosion Inhibitors",
        False,
        "sec_cs",
        False,
    ),
    (
        "mohan",
        "Mohan Das",
        "Metallography Laboratory Technician",
        False,
        "sec_htms",
        False,
    ),
    (
        "preeti",
        "Preeti Agarwal",
        "Scientific Documentation Assistant",
        False,
        "group_mg",
        False,
    ),
    (
        "chetan",
        "Chetan Bhagat",
        "Data Acquisition & Sensor Networks",
        False,
        "sec_ss",
        False,
    ),
    ("nandita", "Nandita Das", "Senior Metallographer", False, "div_amd", False),
    ("farhan", "Farhan Qureshi", "Former Visiting Fellow", False, "sec_tfs", False),
]

# Hierarchy: key, name, parent_key, code, level
ORG_TREE = [
    (
        "root",
        "National Fundamental and Advanced Science Centre, Mumbai",
        None,
        "NFASC",
        "organisation",
    ),
    ("group_mg", "Materials Group", "root", "MG", "group"),
    ("group_psg", "Physical Sciences Group", "root", "PSG", "group"),
    ("div_sed", "Surface Engineering Division", "group_mg", "SED", "division"),
    ("div_amd", "Advanced Metallurgy Division", "group_mg", "AMD", "division"),
    ("div_od", "Optics Division", "group_psg", "OD", "division"),
    ("sec_tfs", "Thin Films Section", "div_sed", "TFS", "section"),
    ("sec_cs", "Corrosion Section", "div_sed", "CS", "section"),
    ("sec_ncs", "Nanocoatings Section", "div_sed", "NCS", "section"),
    ("sec_cms", "Computational Materials Section", "div_amd", "CMS", "section"),
    ("sec_htms", "High Temperature Materials Section", "div_amd", "HTMS", "section"),
    ("sec_ss", "Sensors Section", "div_od", "SS", "section"),
    ("sec_lss", "Laser Spectroscopy Section", "div_od", "LSS", "section"),
]


def seed_simulation():
    print(f"Connecting to database: {DATABASE_URL}")
    factory = session_factory(DATABASE_URL)

    with factory() as db:
        print("Resetting database...")
        reset_database(db)

        # 1. Create Workspaces
        print("Creating organizational units, projects, and groups...")
        ws: dict[str, Workspace] = {}
        for key, name, parent_key, code, level in ORG_TREE:
            w = Workspace(
                kind="org",
                name=name,
                code=code,
                level=level,
                parent_id=ws[parent_key].id if parent_key else None,
                description=f"{name} ({code}) - National Fundamental and Advanced Science Centre, Mumbai",
            )
            db.add(w)
            db.flush()
            ws[key] = w

        # Projects
        ws["proj_tejas"] = Workspace(
            kind="project",
            name="Project Tejas",
            code="TEJ",
            description="High-Temperature Thermal Barrier Coatings for Aerospace Applications",
        )
        ws["proj_akash"] = Workspace(
            kind="project",
            name="Project Akash",
            code="AKA",
            description="Corrosion Resistant Multi-layer Sensors for Marine Defense Platforms",
        )
        ws["proj_surya"] = Workspace(
            kind="project",
            name="Project Surya",
            code="SUR",
            description="Perovskite & Tandem Photovoltaic Thin Film Development",
        )

        # Collaborative Groups
        ws["grp_microscopy"] = Workspace(
            kind="group",
            name="Microscopy Journal Club",
            description="Bi-weekly literature review on in-situ TEM, SEM and SPM surface analysis",
        )
        ws["grp_spectroscopy"] = Workspace(
            kind="group",
            name="Spectroscopy Discussion Group",
            description="Cross-divisional forum for XPS, Raman and FTIR peak deconvolution",
        )

        for p in (
            "proj_tejas",
            "proj_akash",
            "proj_surya",
            "grp_microscopy",
            "grp_spectroscopy",
        ):
            db.add(ws[p])
        db.flush()

        # 2. Create Users
        print(f"Creating {len(USERS_DATA)} users with fixture credentials...")
        pw_hash = hash_password(FIXTURE_PASSWORD)
        users: dict[str, User] = {}

        for username, display_name, title, is_admin, home_key, _ in USERS_DATA:
            u = User(
                username=username,
                display_name=display_name,
                is_admin=is_admin,
                password_hash=pw_hash,
                must_set_password=False,
                welcome_dismissed_at=utcnow(),
                whats_new_seen_release=__version__,
            )
            # Farhan is inactive (departed research fellow)
            status = "left" if username == "farhan" else "active"
            people.set_status(u, status)
            db.add(u)
            users[username] = u

        db.flush()

        # Set home workspaces
        for username, _, _, _, home_key, _ in USERS_DATA:
            users[username].home_workspace_id = ws[home_key].id

        # 3. Create Memberships
        print("Assigning memberships across units, projects, and groups...")
        # Add everyone to root and their home section/division
        for username, _, _, _, home_key, is_steward in USERS_DATA:
            role = "steward" if is_steward else "member"
            db.add(
                Membership(
                    user_id=users[username].id, workspace_id=ws[home_key].id, role=role
                )
            )
            # Also give root membership
            if home_key != "root":
                db.add(
                    Membership(
                        user_id=users[username].id,
                        workspace_id=ws["root"].id,
                        role="member",
                    )
                )

        # Add section members to their parent division explicitly for write/steward
        div_members = {
            "div_sed": [
                "deepa",
                "asha",
                "arvind",
                "bharat",
                "chitra",
                "mira",
                "esha",
                "gita",
                "hari",
                "ananya",
                "rajesh",
                "sneha",
                "sunita",
                "pradeep",
                "neha",
                "rahul",
                "pooja",
                "gautam",
                "swati",
                "vidya",
                "naveen",
                "harish",
                "pallavi",
                "tarun",
                "smita",
                "rakesh",
                "aparna",
                "jyoti",
            ],
            "div_amd": ["devendra", "ramesh", "karthik", "mohan", "nandita"],
            "div_od": ["kavita", "suresh", "meera", "rekha", "alok", "vinay", "chetan"],
        }
        for div_key, u_list in div_members.items():
            for u in u_list:
                role = "steward" if u in ("deepa", "devendra", "kavita") else "member"
                if not db.scalar(
                    Membership.__table__.select().where(
                        Membership.user_id == users[u].id,
                        Membership.workspace_id == ws[div_key].id,
                    )
                ):
                    db.add(
                        Membership(
                            user_id=users[u].id, workspace_id=ws[div_key].id, role=role
                        )
                    )

        # Project Tejas Members
        tejas_team = [
            "bharat",
            "asha",
            "deepa",
            "mira",
            "esha",
            "gita",
            "hari",
            "rajesh",
            "neha",
            "rahul",
            "tanvi",
            "naveen",
            "harish",
            "ramesh",
            "karthik",
        ]
        for u in tejas_team:
            role = "steward" if u in ("bharat", "deepa") else "member"
            db.add(
                Membership(
                    user_id=users[u].id, workspace_id=ws["proj_tejas"].id, role=role
                )
            )

        # Project Akash Members
        akash_team = [
            "chitra",
            "arvind",
            "sneha",
            "pradeep",
            "divya",
            "pallavi",
            "rakesh",
            "jyoti",
            "suresh",
            "chetan",
        ]
        for u in akash_team:
            role = "steward" if u in ("chitra", "arvind") else "member"
            db.add(
                Membership(
                    user_id=users[u].id, workspace_id=ws["proj_akash"].id, role=role
                )
            )

        # Collaborative Club Members
        for u in (
            "bharat",
            "chitra",
            "asha",
            "devendra",
            "swati",
            "esha",
            "mohan",
            "nandita",
        ):
            db.add(
                Membership(
                    user_id=users[u].id,
                    workspace_id=ws["grp_microscopy"].id,
                    role="steward" if u == "bharat" else "member",
                )
            )
        for u in ("mira", "kavita", "meera", "rekha", "ananya", "smita", "vinay"):
            db.add(
                Membership(
                    user_id=users[u].id,
                    workspace_id=ws["grp_spectroscopy"].id,
                    role="steward" if u == "mira" else "member",
                )
            )

        db.flush()

        # 4. Unit Administration Grants (SED, TFS, OD)
        print("Configuring Unit Administration grants...")
        now = utcnow()
        db.add(
            UnitAdminGrant(
                user_id=users["deepa"].id,
                workspace_id=ws["div_sed"].id,
                granted_by=users["admin"].id,
                granted_at=now - timedelta(days=60),
            )
        )
        db.add(
            UnitAdminGrant(
                user_id=users["asha"].id,
                workspace_id=ws["sec_tfs"].id,
                granted_by=users["admin"].id,
                granted_at=now - timedelta(days=45),
            )
        )
        db.add(
            UnitAdminGrant(
                user_id=users["kavita"].id,
                workspace_id=ws["div_od"].id,
                granted_by=users["admin"].id,
                granted_at=now - timedelta(days=30),
            )
        )

        # Unit Positions
        db.add(
            UnitPosition(
                workspace_id=ws["group_mg"].id,
                position="head",
                user_id=users["vikram"].id,
                starts_on=now.date() - timedelta(days=365),
            )
        )
        db.add(
            UnitPosition(
                workspace_id=ws["div_sed"].id,
                position="head",
                user_id=users["deepa"].id,
                starts_on=now.date() - timedelta(days=180),
            )
        )
        db.add(
            UnitPosition(
                workspace_id=ws["sec_tfs"].id,
                position="head",
                user_id=users["asha"].id,
                starts_on=now.date() - timedelta(days=180),
            )
        )
        db.add(
            UnitPosition(
                workspace_id=ws["sec_cs"].id,
                position="head",
                user_id=users["arvind"].id,
                starts_on=now.date() - timedelta(days=180),
            )
        )
        db.add(
            UnitPosition(
                workspace_id=ws["div_od"].id,
                position="head",
                user_id=users["kavita"].id,
                starts_on=now.date() - timedelta(days=120),
            )
        )

        # 5. Site Broadcasts
        print("Configuring Site-wide Broadcast Banner...")
        db.add(
            SiteBroadcast(
                message="NMRL Pilot Intranet: Operation verified on air-gapped Ubuntu infrastructure. All research teams please adhere to clean data classification protocols.",
                level="info",
                active=True,
                position=1,
                revision=1,
                created_at=now - timedelta(days=7),
                updated_at=now - timedelta(days=7),
            )
        )

        # 6. Noticeboard Posts & Official Notices
        print(
            "Populating Noticeboard posts, announcements, and technical discussions..."
        )
        # Surface Engineering Division Noticeboard
        sed_p1 = Post(
            workspace_id=ws["div_sed"].id,
            author_id=users["deepa"].id,
            kind="official",
            pinned=True,
            body=(
                "### Official Notice: Annual Laboratory Safety Audit & High-Vacuum Equipment Recertification\n\n"
                "The Directorate has scheduled the mandatory annual safety audit for all Surface Engineering Division labs from **November 18 to 22**.\n\n"
                "- **Thin Films Section**: PVD chamber interlocks, turbo-molecular pump backing lines, and Ar/O2 cylinder manifolds.\n"
                "- **Corrosion Section**: Autoclave overpressure rupture discs and acid fume extraction scrubbing efficiency.\n"
                "- **Nanocoatings Section**: Chemical handling hoods and hazardous solvent disposal logs.\n\n"
                "All Section Heads are requested to ensure safety logbooks are signed and equipment calibration tags are up to date."
            ),
            created_at=now - timedelta(days=2, hours=4),
        )
        db.add(sed_p1)
        db.flush()

        # Reply to official notice
        db.add(
            Post(
                workspace_id=ws["div_sed"].id,
                author_id=users["asha"].id,
                parent_id=sed_p1.id,
                kind="discussion",
                body="Thin Films Section has completed preliminary inspection of all high-vacuum interlocks. PVD-02 calibration certificate was renewed yesterday.",
                created_at=now - timedelta(days=1, hours=22),
            )
        )

        # Research discussion post in SED
        sed_p2 = Post(
            workspace_id=ws["div_sed"].id,
            author_id=users["bharat"].id,
            kind="discussion",
            pinned=False,
            body=(
                "### Friday Technical Review: Oxygen Vacancy Kinetics in ZrO2-Y2O3 Barrier Coatings\n\n"
                "We have concluded the 20nm, 40nm, and 60nm reactive sputtering runs for Project Tejas. Preliminary XPS spectra show a 4.8% variation in vacancy density near the substrate interface.\n\n"
                "Thin Films and Corrosion sections will hold a joint review this Friday at 15:00 in Room 204. Please bring comparative profilometry curves."
            ),
            created_at=now - timedelta(hours=18),
        )
        db.add(sed_p2)
        db.flush()

        db.add(
            Post(
                workspace_id=ws["div_sed"].id,
                author_id=users["chitra"].id,
                parent_id=sed_p2.id,
                kind="discussion",
                body="Corrosion Section will present the electrochemical impedance spectroscopy (EIS) data from the 60nm coupons exposed to 3.5% NaCl. There is a noticeable passivation improvement.",
                created_at=now - timedelta(hours=14),
            )
        )

        # Thin Films Section Noticeboard
        tfs_p1 = Post(
            workspace_id=ws["sec_tfs"].id,
            author_id=users["asha"].id,
            kind="official",
            pinned=True,
            body=(
                "### Thin Films Section: Substrate Ultrasonic Cleaning Protocol Revision\n\n"
                "All operators of PVD Sputtering Unit 1 & 2 must adhere to the 4-stage cleaning sequence: Acetone (15 min) -> Isopropanol (15 min) -> DI Water rinse -> N2 dry bake (120C, 30 min). Witness coupons must be stored strictly in the vacuum desiccator."
            ),
            created_at=now - timedelta(days=3),
        )
        db.add(tfs_p1)

        tfs_p2 = Post(
            workspace_id=ws["sec_tfs"].id,
            author_id=users["esha"].id,
            kind="discussion",
            body="Batch 4B deposition is completed. Thickness measurements across 6 points show uniformity within 1.2% standard deviation. Substrates are transferred to the characterization box.",
            created_at=now - timedelta(hours=8),
        )
        db.add(tfs_p2)

        # 7. Interactive Live Whiteboard (Hand-drawn Ink Objects)
        print(
            "Populating Live Whiteboard with ink drawings, schematics, and sticky notes..."
        )
        art_file = ROOT / "fixtures/research-day/board-objects.json"
        board_state = {}
        if art_file.exists():
            raw_objects = json.loads(art_file.read_text(encoding="utf-8"))
            # Take sticky notes and sample of strokes for high fidelity rendering
            for i, obj in enumerate(raw_objects[:120]):
                board_state[f"obj_{i:04d}"] = {
                    "kind": obj["kind"],
                    "data": obj["data"],
                    "author": str(users["bharat"].id),
                    "alive": True,
                    "rev": 1,
                    "dx": 0.0,
                    "dy": 0.0,
                }

        # Board in Project Tejas
        board_tejas = Board(
            workspace_id=ws["proj_tejas"].id,
            epoch=1,
            revision=len(board_state),
            base_revision=0,
        )
        db.add(board_tejas)
        db.flush()

        db.add(
            BoardSnapshot(
                workspace_id=ws["proj_tejas"].id,
                epoch=1,
                revision=len(board_state),
                state=board_state,
                created_at=now - timedelta(hours=6),
            )
        )

        # Board in Thin Films Section
        board_tfs = Board(
            workspace_id=ws["sec_tfs"].id,
            epoch=1,
            revision=len(board_state),
            base_revision=0,
        )
        db.add(board_tfs)
        db.flush()

        db.add(
            BoardSnapshot(
                workspace_id=ws["sec_tfs"].id,
                epoch=1,
                revision=len(board_state),
                state=board_state,
                created_at=now - timedelta(hours=5),
            )
        )

        # 8. Project Chat & Threaded Messages
        print("Populating Project Chat & Threads...")
        chat_script = [
            (
                "asha",
                "Films are ready: 20, 40 and 60 nm ZrO2-Y2O3 series. Uncoated witness coupons are stored in desiccator box #4.",
                5,
            ),
            (
                "chitra",
                "Thanks Asha. Gas Chromatography and XRD slot is reserved for 14:00. Can we run a reference baseline before the series?",
                4.5,
            ),
            (
                "mira",
                "XPS beamline queue is clear after lunch. Please ensure samples are capped; atmospheric exposure would perturb the vacancy signal.",
                4,
            ),
            (
                "bharat",
                "I added the sample-to-run calibration table to the project plan. If reference baseline drifts above 2%, we repeat the 40 nm sample.",
                3.5,
            ),
            (
                "deepa",
                "Agreed. Keep raw spectral traces in this project channel; post only the reviewed synthesis and conclusions to the Division board.",
                3,
            ),
            (
                "esha",
                "Substrate pre-heating thermocouple reached stable 650 C. Ready for the next deposition cycle whenever Dr. Bharat confirms.",
                2,
            ),
            (
                "rajesh",
                "Chamber base pressure reached 2.4e-7 mbar with liquid nitrogen trap filled. Mass flow controllers calibrated for Ar/O2 80:20 ratio.",
                1.5,
            ),
            (
                "bharat",
                "Excellent. Proceed with the automated sequence. I have updated the task checklist on our project board.",
                0.5,
            ),
        ]
        chat_msgs = []
        for author, text_msg, hours_ago in chat_script:
            msg = ChatMessage(
                workspace_id=ws["proj_tejas"].id,
                author_id=users[author].id,
                body=text_msg,
                client_id=f"client_chat_{uuid.uuid4().hex[:12]}",
                created_at=now - timedelta(hours=hours_ago),
            )
            db.add(msg)
            chat_msgs.append(msg)
        db.flush()

        # Threaded reply on the second message
        db.add(
            ChatMessage(
                workspace_id=ws["proj_tejas"].id,
                author_id=users["asha"].id,
                parent_id=chat_msgs[1].id,
                body="Baseline standard coupon #STD-01 is mounted on holder 2 for the 14:00 run.",
                client_id=f"client_chat_{uuid.uuid4().hex[:12]}",
                created_at=now - timedelta(hours=4.2),
            )
        )

        # 9. Tasks & Workflows
        print("Populating Research Tasks and Kanban boards...")
        # Todo list for Project Tejas
        tejas_todo_list = TodoList(
            workspace_id=ws["proj_tejas"].id,
            created_by=users["bharat"].id,
            client_id=uuid.uuid4(),
            create_digest=uuid.uuid4().hex,
            title="Project Tejas: Phase-II Coating Trials",
            revision=1,
            created_at=now - timedelta(days=10),
        )
        db.add(tejas_todo_list)
        db.flush()

        tasks_info = [
            (
                "Substrate Ultrasonic Degreasing & Pre-treatment",
                "Clean 12 Inconel-718 turbine alloy coupons following revised 4-stage solvent procedure.",
                users["esha"].id,
                "high",
                "done",
                True,
                now.date() - timedelta(days=2),
                [
                    {"text": "Acetone ultrasonic bath 15 min", "done": True},
                    {"text": "DI water rinse & dry bake", "done": True},
                ],
            ),
            (
                "Electron Beam PVD Chamber Pump-down & Glow Discharge",
                "Achieve base pressure < 5e-7 mbar, execute 10-minute Ar plasma substrate reverse sputtering etch.",
                users["rajesh"].id,
                "high",
                "done",
                True,
                now.date() - timedelta(days=1),
                [
                    {"text": "Turbopump backing pressure check", "done": True},
                    {"text": "RF substrate bias tuning", "done": True},
                ],
            ),
            (
                "Multi-layer Deposition of 40nm & 60nm YSZ Coatings",
                "Execute reactive sputtering run at 650 C substrate temperature with continuous optical emission monitoring.",
                users["bharat"].id,
                "high",
                "in_progress",
                False,
                now.date() + timedelta(days=1),
                [
                    {"text": "Deposition rate calibration", "done": True},
                    {"text": "Substrate rotation set to 12 rpm", "done": True},
                    {"text": "Thickness monitoring", "done": False},
                ],
            ),
            (
                "High-Resolution Cross-Sectional SEM & EDS Line Scans",
                "Mount witness samples, FIB cross-section preparation, evaluate elemental diffusion across interface.",
                users["swati"].id,
                "normal",
                "todo",
                False,
                now.date() + timedelta(days=3),
                [
                    {"text": "Diamond saw precision slicing", "done": False},
                    {"text": "EDS line scan at 15 kV", "done": False},
                ],
            ),
            (
                "High-Temperature Cyclic Oxidation Testing (1050 C)",
                "Expose coated coupons to 100 thermal shock cycles in air furnace (1050 C to room temp forced air).",
                users["neha"].id,
                "high",
                "todo",
                False,
                now.date() + timedelta(days=7),
                [
                    {"text": "Weigh samples to 0.1 mg accuracy", "done": False},
                    {"text": "Program furnace PID controller", "done": False},
                ],
            ),
            (
                "Quarter-3 Milestone Report & Deliverable Compilation",
                "Collate microstructural findings, EIS Nyquist plots, and draft formal report for NMRL Directorate.",
                users["deepa"].id,
                "normal",
                "in_progress",
                False,
                now.date() + timedelta(days=14),
                [
                    {"text": "Aggregate XRD peak tables", "done": True},
                    {"text": "Executive summary draft", "done": False},
                ],
            ),
        ]

        for title, desc, assignee, priority, status, done, due, checklist in tasks_info:
            db.add(
                TodoTask(
                    list_id=tejas_todo_list.id,
                    created_by=users["bharat"].id,
                    client_id=uuid.uuid4(),
                    create_digest=uuid.uuid4().hex,
                    title=title,
                    description=desc,
                    due_date=due,
                    priority=priority,
                    status=status,
                    done=done,
                    assignee_id=assignee,
                    checklist=checklist,
                    revision=1,
                    created_at=now - timedelta(days=5),
                    updated_at=now - timedelta(hours=3),
                )
            )

        # Personal task list for Bharat
        bharat_todo_list = TodoList(
            owner_id=users["bharat"].id,
            created_by=users["bharat"].id,
            client_id=uuid.uuid4(),
            create_digest=uuid.uuid4().hex,
            title="My Personal Priorities & Action Items",
            revision=1,
            created_at=now - timedelta(days=12),
        )
        db.add(bharat_todo_list)
        db.flush()

        db.add(
            TodoTask(
                list_id=bharat_todo_list.id,
                created_by=users["bharat"].id,
                client_id=uuid.uuid4(),
                create_digest=uuid.uuid4().hex,
                title="Review Fellowship Extension for Esha Menon",
                description="Evaluate progress report on high-temperature barrier layers before Friday submission to DG Office.",
                due_date=now.date() + timedelta(days=2),
                priority="high",
                status="todo",
                done=False,
                checklist=[
                    {"text": "Check publication manuscript draft", "done": False}
                ],
                revision=1,
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            )
        )

        # 10. Personal Research Notes
        print("Populating Personal Notes and Scratchpads...")
        notes_data = [
            (
                users["bharat"].id,
                "Inconel-718 Substrate Degas Observation",
                "Note from yesterday's trial: When ramping past 520 C, vacuum chamber pressure rose to 8e-6 mbar temporarily. Likely residual moisture from ultrasonic rinse. Advise Esha to increase nitrogen pre-bake to 45 minutes at 140 C.",
            ),
            (
                users["bharat"].id,
                "Literature Reference: Perovskite Interfacial Strain",
                "Paper by Ramanathan et al. (Acta Mater. 2024): lattice mismatch between YSZ and bond coat drops from 3.2% to 0.9% when doping with 2 mol% Sc2O3. Check if our chemical inventory has Scandium nitrate precursor.",
            ),
            (
                users["asha"].id,
                "Thin Films Section Lab Inspection Notes",
                "Turbo-molecular pump on Sputter-1 due for 8,000-hour bearing overhaul in December. Quote received from vendor under rate contract. Forward to Dr. Deepa for purchase approval.",
            ),
        ]
        for owner_id, title, body in notes_data:
            db.add(
                Note(
                    owner_id=owner_id,
                    title=title,
                    body=body,
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(hours=4),
                )
            )

        # 11. Audit Trail Events
        print("Populating tamper-evident Audit Trail records...")
        audit_events = [
            (
                "identity.create",
                "identity",
                users["bharat"].id,
                "Site Administrator initialized user account Bharat Kulkarni",
            ),
            (
                "identity.create",
                "identity",
                users["deepa"].id,
                "Site Administrator initialized user account Deepa Nair",
            ),
            (
                "unit_admin.grant",
                "authority",
                ws["div_sed"].id,
                "Site Administrator appointed Dr. Deepa Nair as Unit Administrator of Surface Engineering Division",
            ),
            (
                "unit_admin.grant",
                "authority",
                ws["sec_tfs"].id,
                "Site Administrator appointed Dr. Asha Rao as Unit Administrator of Thin Films Section",
            ),
            (
                "position.set",
                "authority",
                ws["div_sed"].id,
                "Dr. Deepa Nair confirmed as Head, Surface Engineering Division",
            ),
            (
                "broadcast.create",
                "site",
                None,
                "Site Administrator issued air-gapped pilot advisory broadcast",
            ),
        ]
        for action, scope, target_id, reason in audit_events:
            audit.record(
                db,
                actor=users["admin"],
                action=action,
                scope_type=scope,
                target_id=target_id or users["admin"].id,
                reason=reason,
                status_before=None,
                status_after="active",
            )

        db.commit()
        print("Successfully seeded realistic 50-user NMRL research organization!")


if __name__ == "__main__":
    seed_simulation()
