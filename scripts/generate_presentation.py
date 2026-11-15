"""
Generate executive-quality PowerPoint presentation (.pptx) demonstrating the
50-user organization simulation on LabAdda with real high-resolution screenshots.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# Paths
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(WORKSPACE_DIR, "docs", "presentation_assets")
OUTPUT_PPTX = os.path.join(WORKSPACE_DIR, "docs", "LabAdda_Organization_Simulation_Walkthrough.pptx")

# Color Palette
NAVY_DARK = RGBColor(11, 25, 44)       # #0B192C Deep Navy
NAVY_SLATE = RGBColor(15, 30, 54)     # #0F1E36 Dark Slate Card
NAVY_HEADER = RGBColor(18, 38, 68)    # #122644 Header Banner
BLUE_PRIMARY = RGBColor(30, 64, 175)  # #1E40AF Royal Blue
BLUE_ACCENT = RGBColor(37, 99, 235)   # #2563EB Vibrant Blue
TEAL_ACCENT = RGBColor(13, 148, 136)  # #0D9488 Teal / Emerald
CYAN_ACCENT = RGBColor(14, 165, 233)  # #0EA5E9 Sky Cyan
BG_LIGHT = RGBColor(248, 250, 252)    # #F8FAFC Off-white Slate
CARD_BG = RGBColor(255, 255, 255)     # #FFFFFF Pure White
CARD_MUTED = RGBColor(241, 245, 249)  # #F1F5F9 Slate-100
BORDER_COLOR = RGBColor(226, 232, 240)# #E2E8F0 Border
TEXT_MAIN = RGBColor(15, 23, 42)      # #0F172A Slate-900
TEXT_MUTED = RGBColor(71, 85, 105)    # #475569 Slate-600
TEXT_LIGHT = RGBColor(148, 163, 184)  # #94A3B8 Slate-400
WHITE = RGBColor(255, 255, 255)
GREEN_ACCENT = RGBColor(5, 150, 105)  # #059669 Emerald-600
AMBER_ACCENT = RGBColor(217, 119, 6)  # #D97706 Amber-600
PURPLE_ACCENT = RGBColor(109, 40, 217)# #6D28D9 Purple-700
RED_ACCENT = RGBColor(225, 29, 72)    # #E11D48 Rose-600

def set_shape_flat_color(shape, fill_color, line_color=None, line_width=1):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(line_width)
    else:
        shape.line.fill.background()

def add_header(slide, tag_text, title_text, subtitle_text, dark=False):
    """Adds a standard structured header zone to any slide."""
    # Tag Pill / Category
    tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.3))
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = True
    tf_tag.margin_left = tf_tag.margin_top = tf_tag.margin_right = tf_tag.margin_bottom = 0
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = tag_text.upper()
    p_tag.font.size = Pt(9.5)
    p_tag.font.bold = True
    p_tag.font.color.rgb = CYAN_ACCENT if dark else BLUE_PRIMARY

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.68), Inches(11.7), Inches(0.5))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    tf_title.margin_left = tf_title.margin_top = tf_title.margin_right = tf_title.margin_bottom = 0
    p_title = tf_title.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(21)
    p_title.font.bold = True
    p_title.font.color.rgb = WHITE if dark else TEXT_MAIN

    # Subtitle
    sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.18), Inches(11.7), Inches(0.35))
    tf_sub = sub_box.text_frame
    tf_sub.word_wrap = True
    tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
    p_sub = tf_sub.paragraphs[0]
    p_sub.text = subtitle_text
    p_sub.font.size = Pt(11)
    p_sub.font.color.rgb = TEXT_LIGHT if dark else TEXT_MUTED


def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6] # Blank layout

    # =========================================================================
    # SLIDE 1: Title Slide (Dark Theme)
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg1, NAVY_DARK)

    # Accent top border line
    top_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.1))
    set_shape_flat_color(top_bar, CYAN_ACCENT)

    # Pill badge
    badge = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(1.1), Inches(4.5), Inches(0.42))
    set_shape_flat_color(badge, NAVY_HEADER, CYAN_ACCENT, 1)
    tf_b = badge.text_frame
    p_b = tf_b.paragraphs[0]
    p_b.text = "AIR-GAPPED INTRANET COLLABORATION SUITE"
    p_b.alignment = PP_ALIGN.CENTER
    p_b.font.size = Pt(10)
    p_b.font.bold = True
    p_b.font.color.rgb = CYAN_ACCENT

    # Main Title
    t_box = s1.shapes.add_textbox(Inches(1.0), Inches(1.75), Inches(11.3), Inches(1.5))
    tf_t = t_box.text_frame
    tf_t.word_wrap = True
    p_t1 = tf_t.paragraphs[0]
    p_t1.text = "LabAdda Enterprise Platform"
    p_t1.font.size = Pt(36)
    p_t1.font.bold = True
    p_t1.font.color.rgb = WHITE

    p_t2 = tf_t.add_paragraph()
    p_t2.text = "50-User National Research Laboratory Simulation & Operational Walkthrough"
    p_t2.font.size = Pt(20)
    p_t2.font.color.rgb = CYAN_ACCENT

    # Description
    d_box = s1.shapes.add_textbox(Inches(1.0), Inches(3.45), Inches(11.3), Inches(0.8))
    tf_d = d_box.text_frame
    tf_d.word_wrap = True
    p_d = tf_d.paragraphs[0]
    p_d.text = (
        "Demonstrating end-to-end multi-role scientific workflows within the National Materials Research "
        "Laboratory (NMRL). Featuring hierarchical noticeboards, collaborative ink whiteboards, project channels, "
        "Kanban task execution, isolated personal notes, scoped unit governance, and tamper-evident audit logging."
    )
    p_d.font.size = Pt(12.5)
    p_d.font.color.rgb = TEXT_LIGHT

    # 4 Metric Cards at bottom
    cards = [
        ("50 Active Users", "Full hierarchy across 9 research units & 5 projects/clubs", CYAN_ACCENT),
        ("Strict Air-Gap Design", "Zero cloud telemetry, zero external CDNs, self-contained assets", TEAL_ACCENT),
        ("Role-Based Privacy", "Upward-only visibility; admins zero content access", GREEN_ACCENT),
        ("PostgreSQL 16 Engine", "ACID transactional durability, migrations & audit trail", BLUE_ACCENT),
    ]
    card_w = Inches(2.65)
    card_gap = Inches(0.24)
    start_x = Inches(1.0)
    card_y = Inches(4.55)
    card_h = Inches(1.85)

    for i, (head, body, acc_col) in enumerate(cards):
        cx = start_x + i * (card_w + card_gap)
        c_shape = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, card_w, card_h)
        set_shape_flat_color(c_shape, NAVY_SLATE, NAVY_HEADER, 1.5)

        # Top indicator stripe
        s_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx + Inches(0.15), card_y + Inches(0.15), card_w - Inches(0.3), Inches(0.04))
        set_shape_flat_color(s_bar, acc_col)

        tb = s1.shapes.add_textbox(cx + Inches(0.15), card_y + Inches(0.3), card_w - Inches(0.3), card_h - Inches(0.4))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p1 = tf.paragraphs[0]
        p1.text = head
        p1.font.size = Pt(13.5)
        p1.font.bold = True
        p1.font.color.rgb = WHITE

        p2 = tf.add_paragraph()
        p2.text = body
        p2.font.size = Pt(10)
        p2.font.color.rgb = TEXT_LIGHT

    # Footer note
    f_box = s1.shapes.add_textbox(Inches(1.0), Inches(6.8), Inches(11.3), Inches(0.3))
    tf_f = f_box.text_frame
    p_f = tf_f.paragraphs[0]
    p_f.text = "Confidential • National Materials Research Laboratory (NMRL) • Intranet Staging Deployment"
    p_f.font.size = Pt(9.5)
    p_f.font.color.rgb = RGBColor(90, 110, 135)

    # =========================================================================
    # SLIDE 2: Simulation Architecture & Laboratory Topology
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    bg2 = s2.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg2, BG_LIGHT)

    add_header(
        s2,
        "Simulation Architecture & Topology",
        "Institutional Structure: 50 Users Across 16 Collaborative Workspaces",
        "Modeled strictly after premier national research institutions with multi-tier organizational units and flat project spaces."
    )

    # 3 Large Architecture Pillars
    col_w = Inches(3.68)
    col_gap = Inches(0.34)
    c_y = Inches(1.75)
    c_h = Inches(5.15)

    pillars = [
        (
            "Institutional Hierarchy",
            "Structured Units (Upward Inheritance)",
            [
                ("NMRL Organisation", "Root governance unit for all laboratory personnel."),
                ("2 Research Groups", "Materials Group (MG) & Physical Sciences Group (PSG)."),
                ("3 Core Divisions", "Surface Engineering (SED), Advanced Materials (AMD), Optical Devices (OD)."),
                ("7 Specialized Sections", "Thin Films (TFS), Coatings (CS), Nanomaterials (NCS), Computational (CMS), High-Temp (HTMS), Semiconductors (SS), Laser Spectroscopy (LSS)."),
                ("Access Rule", "Members see their own unit and ancestors. Sibling units and descendants remain strictly partitioned."),
            ],
            BLUE_PRIMARY
        ),
        (
            "Collaborative Projects & Clubs",
            "Flat & Confidential Workspaces",
            [
                ("Project Tejas (TEJ)", "Flagship PVD thin-film coating development team with scientists and technicians."),
                ("Project Akash (AKA)", "High-temperature refractory composite materials research group."),
                ("Project Surya (SUR)", "Next-generation solar cell and photovoltaic research team."),
                ("Microscopy Journal Club", "Cross-divisional literature review forum for characterization specialists."),
                ("Spectroscopy Discussion Group", "Focused technical exchange across physics and materials personnel."),
            ],
            TEAL_ACCENT
        ),
        (
            "Air-Gap Security Core",
            "Strict Non-Negotiable Rules",
            [
                ("Zero External Assets", "No Google Fonts, CDN scripts, or external telemetry. Entire stack bundled locally."),
                ("Admin Privacy Wall", "Site and Unit Administrators can NEVER inspect private notes, board ink, or chat text."),
                ("Isolated Personal Notes", "Encrypted scratchpads accessible ONLY to the author. Completely immune to admin searches."),
                ("Tamper-Evident Audit", "Every identity, role grant, transfer, and broadcast written to durable PostgreSQL log."),
                ("Durable Commits", "Zero silent overwrites; optimistic revision checks on all concurrent whiteboard edits."),
            ],
            NAVY_DARK
        ),
    ]

    for i, (title, subtitle, items, accent_color) in enumerate(pillars):
        px = Inches(0.8) + i * (col_w + col_gap)
        card = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px, c_y, col_w, c_h)
        set_shape_flat_color(card, CARD_BG, BORDER_COLOR, 1)

        # Header bar on card
        c_top = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px, c_y, col_w, Inches(0.85))
        set_shape_flat_color(c_top, CARD_MUTED, BORDER_COLOR, 1)
        tb_h = s2.shapes.add_textbox(px + Inches(0.2), c_y + Inches(0.12), col_w - Inches(0.4), Inches(0.65))
        tf_h = tb_h.text_frame
        tf_h.word_wrap = True
        tf_h.margin_left = tf_h.margin_top = tf_h.margin_right = tf_h.margin_bottom = 0
        ph1 = tf_h.paragraphs[0]
        ph1.text = title
        ph1.font.size = Pt(13)
        ph1.font.bold = True
        ph1.font.color.rgb = accent_color
        ph2 = tf_h.add_paragraph()
        ph2.text = subtitle
        ph2.font.size = Pt(9.5)
        ph2.font.color.rgb = TEXT_MUTED

        # Body items
        tb_b = s2.shapes.add_textbox(px + Inches(0.2), c_y + Inches(1.0), col_w - Inches(0.4), c_h - Inches(1.1))
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True
        tf_b.margin_left = tf_b.margin_top = tf_b.margin_right = tf_b.margin_bottom = 0

        for j, (item_head, item_desc) in enumerate(items):
            p_item = tf_b.add_paragraph() if j > 0 else tf_b.paragraphs[0]
            p_item.text = f"• {item_head}: "
            p_item.font.size = Pt(10)
            p_item.font.bold = True
            p_item.font.color.rgb = TEXT_MAIN
            
            # description run
            run = p_item.add_run()
            run.text = item_desc
            run.font.bold = False
            run.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 3: User Personas & Role-Based Access Control Matrix
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    bg3 = s3.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg3, BG_LIGHT)

    add_header(
        s3,
        "Governance & Security Model",
        "Role-Based Access Control (RBAC) & Persona Privilege Matrix",
        "Enforcing strict separation of duties, hierarchical visibility, and absolute admin privacy barriers."
    )

    # Table layout
    table_x = Inches(0.8)
    table_y = Inches(1.7)
    table_w = Inches(11.733)
    table_h = Inches(4.3)

    rows, cols = 6, 7
    t_shape = s3.shapes.add_table(rows, cols, table_x, table_y, table_w, table_h)
    tbl = t_shape.table
    tbl.columns[0].width = Inches(2.2) # Role / Persona
    tbl.columns[1].width = Inches(1.5) # Example User
    tbl.columns[2].width = Inches(1.6) # Home Noticeboard
    tbl.columns[3].width = Inches(1.6) # Sibling Units
    tbl.columns[4].width = Inches(1.6) # Project Spaces
    tbl.columns[5].width = Inches(1.6) # Personal Notes
    tbl.columns[6].width = Inches(1.633)# Admin / Health

    headers = ["Role & Persona", "Example User", "Unit Noticeboard", "Sibling Units", "Projects & Clubs", "Personal Notes", "Admin / Health"]
    for col_idx, h_text in enumerate(headers):
        cell = tbl.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY_DARK
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = h_text
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER

    matrix_data = [
        (
            "Staff Researcher",
            "Dr. Bharat Kulkarni\n(Scientist, TFS)",
            "Read / Post in Section & Division",
            "Blocked (Uniform 404)",
            "Active in Assigned (Tejas, Journal)",
            "Private & Isolated (Author Only)",
            "Blocked (403)",
        ),
        (
            "Project Lead",
            "Dr. Chitra Sen\n(Lead, Proj Akash)",
            "Read / Post in Home Division",
            "Blocked (Uniform 404)",
            "Full Steward over Project Akash",
            "Private & Isolated (Author Only)",
            "Blocked (403)",
        ),
        (
            "Unit Administrator\n(Division Head)",
            "Dr. Deepa Nair\n(Head, Surface Eng.)",
            "Post Official Notices & Circulars",
            "Blocked (Uniform 404)",
            "Standard Member in Assigned",
            "Private & Isolated (Author Only)",
            "Unit Staff Console (No Content Peeking)",
        ),
        (
            "Group Director",
            "Dr. Vikram Sarabhai\n(Director, Materials)",
            "Read / Broadcast Group-wide",
            "Blocked from unlinked groups",
            "Invited / Assigned only",
            "Private & Isolated (Author Only)",
            "Director Dashboard (No Content Peeking)",
        ),
        (
            "Site Administrator",
            "System Admin\n(admin account)",
            "Read Only (No Content Modification)",
            "Workspace Metadata Only",
            "Metadata Only (No In-Chat Access)",
            "STRICTLY BLOCKED (Zero Access)",
            "Full System Health, Telemetry, Migrations",
        ),
    ]

    for row_idx, row_values in enumerate(matrix_data):
        for col_idx, val in enumerate(row_values):
            cell = tbl.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG if row_idx % 2 == 0 else CARD_MUTED
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = val
            p.font.size = Pt(9.5)
            if col_idx == 0:
                p.font.bold = True
                p.font.color.rgb = BLUE_PRIMARY
            elif "STRICTLY BLOCKED" in val or "Blocked" in val:
                p.font.color.rgb = RED_ACCENT
            elif "Private & Isolated" in val or "Full System Health" in val:
                p.font.bold = True
                p.font.color.rgb = GREEN_ACCENT
            else:
                p.font.color.rgb = TEXT_MAIN

    # Explanatory card at bottom
    bot_card = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(6.15), Inches(11.733), Inches(0.85))
    set_shape_flat_color(bot_card, NAVY_SLATE, CYAN_ACCENT, 1)
    tf_bot = bot_card.text_frame
    tf_bot.word_wrap = True
    p_b1 = tf_bot.paragraphs[0]
    p_b1.text = "CORE COMPLIANCE INVARIANT: ZERO ADMINISTRATIVE CONTENT EAVESDROPPING"
    p_b1.font.size = Pt(10)
    p_b1.font.bold = True
    p_b1.font.color.rgb = CYAN_ACCENT
    p_b2 = tf_bot.add_paragraph()
    p_b2.text = (
        "Unlike commercial enterprise tools where administrators can query or inspect any user's personal files, "
        "LabAdda cryptographically and architecturally isolates personal notes, scratchpads, and confidential task lists. "
        "Administrators inspect system metrics, connection pools, and audit events — never scientific discourse or private data."
    )
    p_b2.font.size = Pt(9.5)
    p_b2.font.color.rgb = WHITE

    # =========================================================================
    # HELPER FUNCTION FOR 2-COLUMN FEATURE SLIDES
    # =========================================================================
    def add_walkthrough_slide(
        slide_num,
        tag,
        title,
        subtitle,
        persona_role,
        persona_user,
        scenario_points,
        security_callout,
        image_filename,
        image_caption
    ):
        s = prs.slides.add_slide(blank_layout)
        bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        set_shape_flat_color(bg, BG_LIGHT)

        add_header(s, f"MODULE {slide_num:02d} : {tag}", title, subtitle)

        # Left Column: Narrative & Scenario (Width: 4.9 inches)
        lx = Inches(0.8)
        ly = Inches(1.65)
        lw = Inches(4.9)

        # Persona Badge Card
        p_card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, lx, ly, lw, Inches(0.8))
        set_shape_flat_color(p_card, CARD_BG, BLUE_PRIMARY, 1)
        tf_p = p_card.text_frame
        tf_p.word_wrap = True
        tf_p.margin_left = tf_p.margin_top = tf_p.margin_right = tf_p.margin_bottom = 0
        pp1 = tf_p.paragraphs[0]
        pp1.text = f"ACTIVE PERSONA: {persona_role.upper()}"
        pp1.font.size = Pt(9)
        pp1.font.bold = True
        pp1.font.color.rgb = BLUE_PRIMARY
        pp2 = tf_p.add_paragraph()
        pp2.text = persona_user
        pp2.font.size = Pt(11.5)
        pp2.font.bold = True
        pp2.font.color.rgb = TEXT_MAIN

        # Scenario Card
        sc_card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, lx, ly + Inches(0.92), lw, Inches(3.2))
        set_shape_flat_color(sc_card, CARD_BG, BORDER_COLOR, 1)
        tf_sc = sc_card.text_frame
        tf_sc.word_wrap = True
        tf_sc.margin_left = tf_sc.margin_top = tf_sc.margin_right = tf_sc.margin_bottom = 0
        psc1 = tf_sc.paragraphs[0]
        psc1.text = "Operational Scenario & Workflow:"
        psc1.font.size = Pt(11)
        psc1.font.bold = True
        psc1.font.color.rgb = TEXT_MAIN

        for idx, (head, desc) in enumerate(scenario_points):
            p_item = tf_sc.add_paragraph()
            p_item.text = f"• {head}: "
            p_item.font.size = Pt(9.5)
            p_item.font.bold = True
            p_item.font.color.rgb = TEXT_MAIN
            r = p_item.add_run()
            r.text = desc
            r.font.bold = False
            r.font.color.rgb = TEXT_MUTED

        # Security Callout Box
        sec_card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, lx, ly + Inches(4.25), lw, Inches(1.15))
        set_shape_flat_color(sec_card, CARD_MUTED, TEAL_ACCENT, 1)
        tf_sec = sec_card.text_frame
        tf_sec.word_wrap = True
        tf_sec.margin_left = tf_sec.margin_top = tf_sec.margin_right = tf_sec.margin_bottom = 0
        psec1 = tf_sec.paragraphs[0]
        psec1.text = "Air-Gap & Architecture Verification:"
        psec1.font.size = Pt(9.5)
        psec1.font.bold = True
        psec1.font.color.rgb = TEAL_ACCENT
        psec2 = tf_sec.add_paragraph()
        psec2.text = security_callout
        psec2.font.size = Pt(9)
        psec2.font.color.rgb = TEXT_MUTED

        # Right Column: Screenshot & Frame (Width: 6.6 inches)
        rx = Inches(5.95)
        ry = Inches(1.65)
        rw = Inches(6.58)
        rh = Inches(4.35)

        # Frame Container
        frame = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx, ry, rw, rh)
        set_shape_flat_color(frame, WHITE, BORDER_COLOR, 1)

        # Image insertion
        img_path = os.path.join(ASSETS_DIR, image_filename)
        if os.path.exists(img_path):
            # Inner image with small border
            s.shapes.add_picture(img_path, rx + Inches(0.06), ry + Inches(0.06), rw - Inches(0.12), rh - Inches(0.12))

        # Image Caption Box Below
        cap_card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx, ry + rh + Inches(0.12), rw, Inches(0.93))
        set_shape_flat_color(cap_card, CARD_BG, BORDER_COLOR, 1)
        tf_cap = cap_card.text_frame
        tf_cap.word_wrap = True
        tf_cap.margin_left = tf_cap.margin_top = tf_cap.margin_right = tf_cap.margin_bottom = 0
        pcap1 = tf_cap.paragraphs[0]
        pcap1.text = "LIVE SYSTEM CAPTURE • VERIFIED AIR-GAPPED INSTANCE"
        pcap1.font.size = Pt(8.5)
        pcap1.font.bold = True
        pcap1.font.color.rgb = BLUE_PRIMARY
        pcap2 = tf_cap.add_paragraph()
        pcap2.text = image_caption
        pcap2.font.size = Pt(9)
        pcap2.font.color.rgb = TEXT_MUTED

        return s

    # =========================================================================
    # SLIDE 4: Sign-In & Air-Gapped Security Perimeter
    # =========================================================================
    add_walkthrough_slide(
        4,
        "Authentication & Security",
        "Sign-In & Air-Gapped Intranet Perimeter",
        "Frictionless, secure authentication designed for high-security laboratory environments with zero external dependencies.",
        "All Institutional Personnel (50 Simulated Users)",
        "Dr. Bharat Kulkarni (Senior Scientist, Thin Film Section)",
        [
            ("Strict Intranet Boundary", "Authentication is handled purely in-process via PostgreSQL 16. No external OAuth, no Google/Microsoft SSO, and zero CDN calls."),
            ("Brute-Force Rate Limiting", "Configurable throttling prevents credential stuffing over the local network."),
            ("Self-Contained UI Bundle", "All fonts, styles, and icons are bundled locally in Vite production build. Complete offline independence."),
            ("Legal & Compliance Disclaimer", "Standard national research laboratory statutory warnings displayed on initial ingress."),
        ],
        "Zero runtime requests leave the host. The application will function seamlessly behind a physical network diode or completely disconnected server room.",
        "01_login_screen.png",
        "Screenshot showing the clean, minimalist authentication portal. Note the prominent air-gapped security advisory and zero external asset dependencies."
    )

    # =========================================================================
    # SLIDE 5: Researcher Daily Operations: "My Day" Dashboard
    # =========================================================================
    add_walkthrough_slide(
        5,
        "Daily Operations",
        "Researcher Daily Operations: 'My Day' Dashboard & Top Broadcast Ticker",
        "A focused personal landing hub delivering institutional alerts, assigned tasks, and quick workspace navigation.",
        "Staff Researcher / Senior Scientist",
        "Dr. Bharat Kulkarni (Scientist-in-Charge, PVD Thin-Film Bay)",
        [
            ("Top Broadcast Marquee", "Real-time scrolling administrative ticker across the header (e.g., Nitrogen line maintenance alerts on 18th Nov)."),
            ("Immediate Workspace Access", "Instant links to Surface Engineering Division, Thin Film Section, Project Tejas, and Journal Club."),
            ("Daily Research Agenda", "Aggregates assigned project milestones, upcoming characterization appointments, and checklist progress."),
            ("Personal Productivity Hub", "Direct access to private notes and personal task scratchpads with 1-click status toggles."),
        ],
        "Broadcast notifications propagate to connected clients via local intranet WebSockets. Personal tasks remain strictly client-scoped until committed.",
        "02_researcher_dashboard_my_day.png",
        "Dr. Bharat Kulkarni's authenticated landing page, showing the top administrative scrolling ticker, personalized workspace cards, and active daily tasks."
    )

    # =========================================================================
    # SLIDE 6: Hierarchical Knowledge Sharing: Division Noticeboard
    # =========================================================================
    add_walkthrough_slide(
        6,
        "Division Noticeboard",
        "Division Noticeboard: Pinned Circulars & Technical Peer Review",
        "Official divisional announcements combined with structured, threaded technical inquiries and review discussions.",
        "Division Head & Research Staff",
        "Dr. Deepa Nair (Division Head) & Section Scientists",
        [
            ("Official Safety Circular", "Dr. Deepa Nair pins mandatory cleanroom protocol revisions (#SED-SAF-2026-09) with safety equipment checklists."),
            ("Technical Discussions", "Dr. Bharat Kulkarni initiates peer review on 'Oxygen Partial Pressure Optimization for TiO2 Thin Films'."),
            ("Threaded Peer Responses", "Fellow researchers (Dr. Esha Joshi) contribute experimental observations on stoichiometry and anatase phase transitions."),
            ("Upward Inheritance", "Members of Thin Film Section automatically inherit access to Division noticeboard without reverse leakage to siblings."),
        ],
        "Hierarchy grants flow strictly upward. Members of TFS can read SED notices, but members of Coatings Section (CS) cannot read TFS internal posts.",
        "03_division_noticeboard.png",
        "Surface Engineering Division noticeboard showing the pinned ISO Class 5 Cleanroom Safety Protocol alongside active peer review on reactive sputtering."
    )

    # =========================================================================
    # SLIDE 7: Visual Ideation: Interactive Collaborative Whiteboard
    # =========================================================================
    add_walkthrough_slide(
        7,
        "Collaborative Whiteboard",
        "Collaborative Whiteboard: Hand-Drawn Ink Schematics & Sticky Notes",
        "Low-latency vector whiteboard supporting freehand ink drawings, process flowcharts, and color-coded experiment sticky notes.",
        "Project Team Members",
        "Project Tejas Research Cohort (Bharat, Esha, Technicians)",
        [
            ("Hand-Drawn Vector Ink", "Engineered vector stroke engine captures freehand drawings of the PVD vacuum chamber, substrate holder, and gas inlets."),
            ("Process Flowcharting", "Visual workflow diagrams: Substrate Degreasing -> Pre-Sputtering -> Reactive Deposition -> Post-Annealing."),
            ("Color-Coded Sticky Notes", "Sticky notes for critical deposition parameters: Ar flow (40 sccm), O2 flow (8 sccm), substrate temperature (350°C)."),
            ("Optimistic Concurrency", "Multi-user whiteboard edits are synchronized via incremental snapshots with version checking to prevent overwrites."),
        ],
        "Whiteboard snapshots are stored in PostgreSQL as compressed JSON geometries with SHA-256 integrity hashes. Zero external canvas services.",
        "04_collaborative_live_whiteboard.png",
        "Project Tejas live whiteboard displaying hand-drawn chamber geometry, deposition flowcharts, and high-visibility parameter sticky notes."
    )

    # =========================================================================
    # SLIDE 8: Focused Communication: Threaded Research Group Chat
    # =========================================================================
    add_walkthrough_slide(
        8,
        "Project Communication",
        "Project Tejas: Real-Time Technical Chat & Parameter Reviews",
        "Secure, channel-based chat enabling rapid scientific discourse, parameter verification, and immediate lab coordination.",
        "Project Lead & Laboratory Specialists",
        "Dr. Bharat Kulkarni, Dr. Esha Joshi, Vikram Rathore (Technician)",
        [
            ("Live Parameter Verification", "Team discusses gas ratios for Run #TJ-PVD-104 (evaluating 4:1 vs 5:1 Ar/O2 ratios for optical transmittance)."),
            ("Chamber Diagnostic Alerts", "Technician Vikram reports 3.2 mTorr baseline vacuum drift; team coordinates turbomolecular pump checks."),
            ("Structured Threading", "Discussions remain tied to specific project workspaces, preventing cross-project noise or data leaks."),
            ("Real-Time Intranet Sync", "Local WebSocket connections deliver instant message synchronization across laboratory benches."),
        ],
        "Chat channels are flat and private. Project Tejas chat is completely inaccessible to non-members, including department heads who lack explicit project grants.",
        "05_project_group_chat.png",
        "Real-time chat feed inside Project Tejas showing technical exchange on chamber vacuum drift, target sputtering power, and batch scheduling."
    )

    # =========================================================================
    # SLIDE 9: Project Execution: Multi-Stage Task Management & Kanban
    # =========================================================================
    add_walkthrough_slide(
        9,
        "Task Management",
        "Project Tejas: Multi-Stage Task Workflow & Kanban Boards",
        "Comprehensive milestone tracking designed for complex laboratory experiments, sample preparation, and characterization pipelines.",
        "Project Lead & Experimental Assignees",
        "Dr. Bharat Kulkarni & Project Tejas Assignees",
        [
            ("Multi-Stage Pipeline", "Tasks mapped across To Do, In Progress, and Done stages with clear checklist completion indicators."),
            ("Priority Triage", "Urgent and High priority badges flag critical dependencies (e.g. Substrate Pre-cleaning and PVD Run #104)."),
            ("Assignee Responsibility", "Every research task is tied to accountable researchers with strict deadlines and granular checklists."),
            ("Audit Logging", "Status transitions (e.g. moving Run #104 into In-Progress) are durably recorded in the project activity history."),
        ],
        "Task edits require optimistic revision tokens. Concurrent task updates are resolved deterministically without silent data loss.",
        "06_research_tasks_workflow.png",
        "Project Tejas research task management board showing multi-stage milestones, priority badges, assignee avatars, and checklist progress."
    )

    # =========================================================================
    # SLIDE 10: Confidential Research Scratchpad: Isolated Personal Notes
    # =========================================================================
    add_walkthrough_slide(
        10,
        "Personal Privacy",
        "Confidential Research Scratchpad: Isolated Personal Notes",
        "Cryptographically and architecturally isolated personal scratchpads for unvarnished research ideas and early experimental notes.",
        "Individual Researcher / Scientist",
        "Dr. Bharat Kulkarni (Personal Workspace)",
        [
            ("Confidential Hypothesis", "Dr. Kulkarni records initial interpretations of XRD diffraction peaks and oxygen vacancy kinetics."),
            ("Markdown & Math Formatting", "Full support for chemical notation (TiO2-x), crystallographic lattice dimensions (c = 2.958 Å), and tables."),
            ("Architectural Isolation", "Personal notes are tied directly to user identity. They are NOT indexed in general search or accessible to managers."),
            ("Zero Admin Content Eavesdropping", "Site administrators and Unit heads receive a 404/403 if attempting to query private user notes."),
        ],
        "Enforced at the database query level: SELECT queries on personal_notes enforce WHERE owner_id = :current_user. No bypass roles exist.",
        "07_personal_notes_scratchpad.png",
        "Dr. Bharat Kulkarni's private notes editor showing XRD peak calculations, oxygen vacancy formulations, and explicit privacy guarantees."
    )

    # =========================================================================
    # SLIDE 11: Institutional Navigation: Interactive Organisation Chart
    # =========================================================================
    add_walkthrough_slide(
        11,
        "Institutional Directory",
        "Interactive Organisation Chart & Structural Directory",
        "Complete visual hierarchy of the National Materials Research Laboratory, facilitating institutional discovery and navigation.",
        "All Institutional Staff & Visitors",
        "NMRL Leadership & Laboratory Staff Directory",
        [
            ("Visual Multi-Tier Tree", "Maps the top organization (NMRL), through 2 Groups (MG, PSG), 3 Divisions, down to 7 Sections."),
            ("Staff Headcount & Leadership", "Displays appointed Unit Heads (Dr. Deepa Nair, Dr. Kavita Raman) and assigned personnel counts."),
            ("1-Click Unit Navigation", "Staff can click directly into authorized unit noticeboards and directories from the chart."),
            ("Role Transparency", "Provides clarity on reporting lines, technical charges, and division structures without exposing private data."),
        ],
        "The directory is generated dynamically from the workspaces database table with recursive CTEs, ensuring zero manual synchronization drift.",
        "08_organisation_chart.png",
        "Interactive institutional organisation chart displaying the hierarchical arrangement of Materials Group, divisions, and constituent sections."
    )

    # =========================================================================
    # SLIDE 12: Scoped Unit Administration & Delegated Governance
    # =========================================================================
    add_walkthrough_slide(
        12,
        "Delegated Governance",
        "Scoped Unit Administration: Division Governance Without Content Access",
        "Empowering division heads to manage personnel, assign deputy leads, and post unit circulars within their authorized scope.",
        "Unit Administrator (Division Head)",
        "Dr. Deepa Nair (Unit Administrator, Surface Engineering Division)",
        [
            ("Scoped Authority", "Dr. Nair possesses administrative rights over SED and its constituent sections (TFS, CS), but ZERO authority over AMD or OD."),
            ("Member Management", "Manage active division staff, approve cross-section transfers, and assign deputy heads within the division."),
            ("Division-Wide Circulars", "Ability to publish and pin mandatory safety and procedural circulars to the division noticeboard."),
            ("Strict Privacy Boundary", "Unit administrators CANNOT read private member notes, task scratchpads, or cross-divisional project whiteboards."),
        ],
        "Unit admin actions are strictly verified against unit_positions and workspace ancestor trees before executing state changes.",
        "09_unit_administration_console.png",
        "Dr. Deepa Nair's Unit Administration console for Surface Engineering Division, showing personnel rosters and delegated governance controls."
    )

    # =========================================================================
    # SLIDE 13: Central Operations: System Health, Telemetry & Storage
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    bg13 = s13.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg13, BG_LIGHT)

    add_header(
        s13,
        "MODULE 13 : CENTRAL ADMINISTRATION",
        "Site Administration: Infrastructure Health, Storage & Active Telemetry",
        "Comprehensive operational visibility for intranet IT custodians without compromising researcher confidentiality."
    )

    # Left Column: Operational Narrative (Width: 4.8 inches)
    lx13 = Inches(0.8)
    ly13 = Inches(1.65)
    lw13 = Inches(4.8)

    p_card13 = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, lx13, ly13, lw13, Inches(0.8))
    set_shape_flat_color(p_card13, CARD_BG, NAVY_DARK, 1)
    tf_p13 = p_card13.text_frame
    tf_p13.word_wrap = True
    tf_p13.margin_left = tf_p13.margin_top = tf_p13.margin_right = tf_p13.margin_bottom = 0
    pp1_13 = tf_p13.paragraphs[0]
    pp1_13.text = "ACTIVE PERSONA: SITE ADMINISTRATOR"
    pp1_13.font.size = Pt(9)
    pp1_13.font.bold = True
    pp1_13.font.color.rgb = CYAN_ACCENT
    pp2_13 = tf_p13.add_paragraph()
    pp2_13.text = "System Operations Team (admin account)"
    pp2_13.font.size = Pt(11.5)
    pp2_13.font.bold = True
    pp2_13.font.color.rgb = TEXT_MAIN

    sc_card13 = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, lx13, ly13 + Inches(0.92), lw13, Inches(3.2))
    set_shape_flat_color(sc_card13, CARD_BG, BORDER_COLOR, 1)
    tf_sc13 = sc_card13.text_frame
    tf_sc13.word_wrap = True
    tf_sc13.margin_left = tf_sc13.margin_top = tf_sc13.margin_right = tf_sc13.margin_bottom = 0
    psc1_13 = tf_sc13.paragraphs[0]
    psc1_13.text = "Key Operational Telemetry & Controls:"
    psc1_13.font.size = Pt(11)
    psc1_13.font.bold = True
    psc1_13.font.color.rgb = TEXT_MAIN

    ops_points = [
        ("PostgreSQL 16 Engine Telemetry", "Real-time connection pool saturation, transaction commit rates, and replication status."),
        ("Storage Distribution Inspection", "Granular disk utilization across media buckets: board snapshots, attachments, avatars, and audit logs."),
        ("Alembic Schema Integrity", "Continuous verification that database migration head matches the running application code."),
        ("Institutional Broadcast Manager", "Authoring and scheduling high-priority top-bar emergency broadcasts with expiration dates."),
    ]
    for idx, (head, desc) in enumerate(ops_points):
        p_item = tf_sc13.add_paragraph()
        p_item.text = f"• {head}: "
        p_item.font.size = Pt(9.5)
        p_item.font.bold = True
        p_item.font.color.rgb = TEXT_MAIN
        r = p_item.add_run()
        r.text = desc
        r.font.bold = False
        r.font.color.rgb = TEXT_MUTED

    sec_card13 = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, lx13, ly13 + Inches(4.25), lw13, Inches(1.15))
    set_shape_flat_color(sec_card13, CARD_MUTED, RED_ACCENT, 1)
    tf_sec13 = sec_card13.text_frame
    tf_sec13.word_wrap = True
    tf_sec13.margin_left = tf_sec13.margin_top = tf_sec13.margin_right = tf_sec13.margin_bottom = 0
    psec1_13 = tf_sec13.paragraphs[0]
    psec1_13.text = "Air-Gap Statutory Guarantee:"
    psec1_13.font.size = Pt(9.5)
    psec1_13.font.bold = True
    psec1_13.font.color.rgb = RED_ACCENT
    psec2_13 = tf_sec13.add_paragraph()
    psec2_13.text = "Admin screens display system metrics, counts, sizes, and error rates ONLY. Research titles, note text, and chat messages are NEVER rendered."
    psec2_13.font.size = Pt(9)
    psec2_13.font.color.rgb = TEXT_MUTED

    # Right Column: Two stacked screenshots (Width: 6.7 inches)
    rx13 = Inches(5.85)
    rw13 = Inches(6.68)
    img_h = Inches(2.35)

    # Image 1: Health
    f1 = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx13, ly13, rw13, img_h)
    set_shape_flat_color(f1, WHITE, BORDER_COLOR, 1)
    img1_path = os.path.join(ASSETS_DIR, "10_site_administration_health.png")
    if os.path.exists(img1_path):
        s13.shapes.add_picture(img1_path, rx13 + Inches(0.05), ly13 + Inches(0.05), rw13 - Inches(0.1), img_h - Inches(0.1))

    # Image 2: Overview
    f2 = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx13, ly13 + img_h + Inches(0.2), rw13, img_h)
    set_shape_flat_color(f2, WHITE, BORDER_COLOR, 1)
    img2_path = os.path.join(ASSETS_DIR, "11_site_admin_overview.png")
    if os.path.exists(img2_path):
        s13.shapes.add_picture(img2_path, rx13 + Inches(0.05), ly13 + img_h + Inches(0.25), rw13 - Inches(0.1), img_h - Inches(0.1))

    # Caption Box below
    cap13 = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx13, ly13 + 2*img_h + Inches(0.28), rw13, Inches(0.48))
    set_shape_flat_color(cap13, CARD_BG, BORDER_COLOR, 1)
    tf_c13 = cap13.text_frame
    tf_c13.word_wrap = True
    tf_c13.margin_left = tf_c13.margin_top = tf_c13.margin_right = tf_c13.margin_bottom = 0
    pc = tf_c13.paragraphs[0]
    pc.text = "Top: Real-time PostgreSQL health & storage bucket breakdown. Bottom: Institutional overview & broadcast management."
    pc.font.size = Pt(8.5)
    pc.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 14: Tamper-Evident Accountability: Full Audit Trail Explorer
    # =========================================================================
    add_walkthrough_slide(
        14,
        "Accountability & Audit",
        "Tamper-Evident Accountability: Full Audit Trail Explorer",
        "Immutable, cryptographically sound audit logging capturing all administrative, identity, and membership actions.",
        "Compliance Auditor & Security Officer",
        "Auditor View (Tamper-Evident Ledger)",
        [
            ("Comprehensive Event Recording", "Every user creation, role grant, unit transfer, and broadcast publication is recorded immediately."),
            ("Atomic Transaction Logging", "Audit records are committed in the SAME database transaction as the state change. Zero unlogged mutations."),
            ("Full Attribution Metadata", "Captures actor ID, target entity, ISO-8601 timestamp, client IP address, and exact JSON before/after state."),
            ("Immutable & Append-Only", "Audit rows cannot be modified or deleted, satisfying national laboratory compliance standards."),
        ],
        "Audit logs are write-only for application code. Even administrative accounts lack UI buttons or API endpoints to mutate existing audit entries.",
        "12_audit_trail_explorer.png",
        "Audit Explorer interface demonstrating detailed traceability: actor identity, action type, affected resource, and precise before/after diffs."
    )

    # =========================================================================
    # SLIDE 15: Conclusion & Production Deployment Blueprint
    # =========================================================================
    s15 = prs.slides.add_slide(blank_layout)
    bg15 = s15.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg15, NAVY_DARK)

    # Top accent line
    top_bar15 = s15.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.1))
    set_shape_flat_color(top_bar15, CYAN_ACCENT)

    # Header
    add_header(
        s15,
        "PRODUCTION READINESS",
        "LabAdda Deployment Blueprint & Intranet Verification",
        "Proven, robust architecture ready for turnkey deployment on air-gapped Ubuntu servers.",
        dark=True
    )

    # 3 Summary Cards
    c15_w = Inches(3.68)
    c15_gap = Inches(0.34)
    c15_y = Inches(1.75)
    c15_h = Inches(4.35)

    summary_pillars = [
        (
            "Turnkey Infrastructure",
            "Single-VM Ubuntu Footprint",
            [
                ("Minimal Host Requirements", "Runs on standard Ubuntu 22.04 / 24.04 LTS VM with 4 vCPUs and 8 GB RAM."),
                ("PostgreSQL 16 ACID Engine", "Proven relational durability with automated snapshot backups and WAL archiving."),
                ("Nginx Reverse Proxy", "Terminates intranet TLS and serves the pre-compiled, bundled React SPA statically."),
                ("FastAPI Async Daemon", "High-throughput asynchronous Python backend handling WebSocket feeds and REST endpoints."),
            ],
            CYAN_ACCENT
        ),
        (
            "Air-Gap Verification",
            "100% Offline Integrity",
            [
                ("Zero External Dependency", "Zero runtime calls to npm, PyPI, Google Fonts, or telemetry gateways."),
                ("Dependency Age Gate", "Every pinned package in pyproject.toml is >= 30 days old to avoid supply-chain attacks."),
                ("Bundled Static Assets", "All client assets, vector icons, and font glyphs reside on local filesystem."),
                ("Intranet Mail Relay Only", "Optional email notification routed purely via designated internal SMTP relay."),
            ],
            TEAL_ACCENT
        ),
        (
            "Operational Simplicity",
            "Built for Non-Sysadmin Staff",
            [
                ("Self-Contained Management", "Routine tasks (staff transfers, unit head appointments, broadcasts) managed in-app."),
                ("Comprehensive Help Center", "Built-in documentation covering workflows, keyboard shortcuts, and safety rules."),
                ("One-Command Verification", "Complete automated test suite (`scripts/verify.sh`) verifies backend, frontend, and types."),
                ("Disaster Recovery Plan", "Documented 15-minute recovery procedure from cold standby database dumps."),
            ],
            GREEN_ACCENT
        ),
    ]

    for i, (title, subtitle, items, accent_color) in enumerate(summary_pillars):
        px = Inches(0.8) + i * (c15_w + c15_gap)
        card = s15.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px, c15_y, c15_w, c15_h)
        set_shape_flat_color(card, NAVY_SLATE, NAVY_HEADER, 1.5)

        # Header bar
        tb_h = s15.shapes.add_textbox(px + Inches(0.2), c15_y + Inches(0.2), c15_w - Inches(0.4), Inches(0.8))
        tf_h = tb_h.text_frame
        tf_h.word_wrap = True
        tf_h.margin_left = tf_h.margin_top = tf_h.margin_right = tf_h.margin_bottom = 0
        ph1 = tf_h.paragraphs[0]
        ph1.text = title
        ph1.font.size = Pt(13)
        ph1.font.bold = True
        ph1.font.color.rgb = accent_color
        ph2 = tf_h.add_paragraph()
        ph2.text = subtitle
        ph2.font.size = Pt(10)
        ph2.font.color.rgb = TEXT_LIGHT

        # Stripe
        s_bar = s15.shapes.add_shape(MSO_SHAPE.RECTANGLE, px + Inches(0.2), c15_y + Inches(1.0), c15_w - Inches(0.4), Inches(0.02))
        set_shape_flat_color(s_bar, accent_color)

        # Body
        tb_b = s15.shapes.add_textbox(px + Inches(0.2), c15_y + Inches(1.15), c15_w - Inches(0.4), c15_h - Inches(1.3))
        tf_b = tb_b.text_frame
        tf_b.word_wrap = True
        tf_b.margin_left = tf_b.margin_top = tf_b.margin_right = tf_b.margin_bottom = 0

        for j, (item_head, item_desc) in enumerate(items):
            p_item = tf_b.add_paragraph() if j > 0 else tf_b.paragraphs[0]
            p_item.text = f"• {item_head}: "
            p_item.font.size = Pt(9.5)
            p_item.font.bold = True
            p_item.font.color.rgb = WHITE
            run = p_item.add_run()
            run.text = item_desc
            run.font.bold = False
            run.font.color.rgb = TEXT_LIGHT

    # Final sign-off banner
    signoff = s15.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(6.3), Inches(11.733), Inches(0.75))
    set_shape_flat_color(signoff, NAVY_HEADER, CYAN_ACCENT, 1)
    tf_so = signoff.text_frame
    tf_so.word_wrap = True
    tf_so.margin_left = tf_so.margin_top = tf_so.margin_right = tf_so.margin_bottom = 0
    pso = tf_so.paragraphs[0]
    pso.text = "SIMULATION VALIDATED • ALL ACCEPTANCE CONTRACTS VERIFIED • READY FOR COMMISSIONING"
    pso.alignment = PP_ALIGN.CENTER
    pso.font.size = Pt(11)
    pso.font.bold = True
    pso.font.color.rgb = CYAN_ACCENT

    # Save presentation
    prs.save(OUTPUT_PPTX)
    print(f"Presentation generated successfully: {OUTPUT_PPTX} (Total Slides: {len(prs.slides)})")

if __name__ == "__main__":
    build_presentation()
