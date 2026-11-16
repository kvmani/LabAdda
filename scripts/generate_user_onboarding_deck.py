"""
Generate executive-grade PowerPoint presentation (.pptx) introducing LabAdda
to all laboratory staff, researchers, and technical officers.

Features high-resolution live screenshots, clear value propositions,
guidelines on experimental scope & privacy, and a 3-step quickstart guide.
"""

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# Paths
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(WORKSPACE_DIR, "docs", "presentation_assets")
OUTPUT_PPTX = os.path.join(WORKSPACE_DIR, "docs", "LabAdda_User_Guide_and_Onboarding_Presentation.pptx")

# Color Palette
NAVY_DARK = RGBColor(11, 25, 44)  # #0B192C Deep Navy
NAVY_SLATE = RGBColor(15, 30, 54)  # #0F1E36 Dark Slate Card
NAVY_HEADER = RGBColor(18, 38, 68)  # #122644 Header Banner
BLUE_PRIMARY = RGBColor(30, 64, 175)  # #1E40AF Royal Blue
BLUE_ACCENT = RGBColor(37, 99, 235)  # #2563EB Vibrant Blue
TEAL_ACCENT = RGBColor(13, 148, 136)  # #0D9488 Teal / Emerald
CYAN_ACCENT = RGBColor(14, 165, 233)  # #0EA5E9 Sky Cyan
BG_LIGHT = RGBColor(248, 250, 252)  # #F8FAFC Off-white Slate
CARD_BG = RGBColor(255, 255, 255)  # #FFFFFF Pure White
CARD_MUTED = RGBColor(241, 245, 249)  # #F1F5F9 Slate-100
BORDER_COLOR = RGBColor(226, 232, 240)  # #E2E8F0 Border
TEXT_MAIN = RGBColor(15, 23, 42)  # #0F172A Slate-900
TEXT_MUTED = RGBColor(71, 85, 105)  # #475569 Slate-600
TEXT_LIGHT = RGBColor(148, 163, 184)  # #94A3B8 Slate-400
WHITE = RGBColor(255, 255, 255)
GREEN_ACCENT = RGBColor(5, 150, 105)  # #059669 Emerald-600
AMBER_ACCENT = RGBColor(217, 119, 6)  # #D97706 Amber-600
PURPLE_ACCENT = RGBColor(109, 40, 217)  # #6D28D9 Purple-700
ROSE_ACCENT = RGBColor(225, 29, 72)  # #E11D48 Rose-600


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
    # Tag Pill
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
    sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.22), Inches(11.7), Inches(0.35))
    tf_sub = sub_box.text_frame
    tf_sub.word_wrap = True
    tf_sub.margin_left = tf_sub.margin_top = tf_sub.margin_right = tf_sub.margin_bottom = 0
    p_sub = tf_sub.paragraphs[0]
    p_sub.text = subtitle_text
    p_sub.font.size = Pt(11.5)
    p_sub.font.color.rgb = TEXT_LIGHT if dark else TEXT_MUTED


def slide_1(prs, blank_layout):
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg1, NAVY_DARK)
    top_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.12))
    set_shape_flat_color(top_bar, CYAN_ACCENT)
    badge = s1.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(1.0), Inches(4.8), Inches(0.42)
    )
    set_shape_flat_color(badge, NAVY_HEADER, CYAN_ACCENT, 1)
    tf_b = badge.text_frame
    p_b = tf_b.paragraphs[0]
    p_b.text = "RESEARCH INTRANET COLLABORATION WORKSPACE"
    p_b.alignment = PP_ALIGN.CENTER
    p_b.font.size = Pt(10)
    p_b.font.bold = True
    p_b.font.color.rgb = CYAN_ACCENT
    t_box = s1.shapes.add_textbox(Inches(1.0), Inches(1.65), Inches(11.3), Inches(1.5))
    tf_t = t_box.text_frame
    tf_t.word_wrap = True
    p_t1 = tf_t.paragraphs[0]
    p_t1.text = "Welcome to LabAdda"
    p_t1.font.size = Pt(38)
    p_t1.font.bold = True
    p_t1.font.color.rgb = WHITE
    p_t2 = tf_t.add_paragraph()
    p_t2.text = "Your Digital Space for Lab Ideas, Sketches, Discussions & Schedules"
    p_t2.font.size = Pt(20)
    p_t2.font.color.rgb = CYAN_ACCENT
    d_box = s1.shapes.add_textbox(Inches(1.0), Inches(3.35), Inches(11.3), Inches(0.8))
    tf_d = d_box.text_frame
    tf_d.word_wrap = True
    return _finish_slide_1(s1=s1, tf_d=tf_d)


def _finish_slide_1(*, s1, tf_d):
    p_d = tf_d.paragraphs[0]
    p_d.text = (
        "LabAdda is a friendly, lightweight browser-based collaboration space designe"
        "d specifically for our research community on the internal laboratory intrane"
        "t. Think of it as a digital whiteboard for our entire institute—built to mak"
        "e scientific communication faster, simpler, and more engaging."
    )
    p_d.font.size = Pt(13)
    p_d.font.color.rgb = TEXT_LIGHT
    cards = [
        (
            "Grassroots Experiment",
            "An informal initiative to speed up peer discussions without bureaucratic overhead",
            CYAN_ACCENT,
        ),
        (
            "The Whiteboard Rule",
            "No sensitive/official records; share what you'd put on your physical lab board",
            TEAL_ACCENT,
        ),
        (
            "Strict Privacy",
            "Administrators have zero content access; your personal notes & sketches stay private",
            GREEN_ACCENT,
        ),
        (
            "100% Air-Gapped",
            "Hosted exclusively on our internal network; zero external dependencies or cloud data",
            BLUE_ACCENT,
        ),
    ]
    card_w = Inches(2.65)
    card_gap = Inches(0.24)
    start_x = Inches(1.0)
    card_y = Inches(4.55)
    card_h = Inches(1.9)
    for i, (head, body, acc_col) in enumerate(cards):
        cx = start_x + i * (card_w + card_gap)
        c_shape = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, card_w, card_h)
        set_shape_flat_color(c_shape, NAVY_SLATE, NAVY_HEADER, 1.5)
        s_bar = s1.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, cx + Inches(0.15), card_y + Inches(0.15), card_w - Inches(0.3), Inches(0.04)
        )
        set_shape_flat_color(s_bar, acc_col)
        tb = s1.shapes.add_textbox(
            cx + Inches(0.15), card_y + Inches(0.28), card_w - Inches(0.3), card_h - Inches(0.35)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p1 = tf.paragraphs[0]
        p1.text = head
        p1.font.size = Pt(13)
        p1.font.bold = True
        p1.font.color.rgb = WHITE
        p2 = tf.add_paragraph()
        p2.text = body
        p2.font.size = Pt(10.5)
        p2.font.color.rgb = TEXT_LIGHT


def slide_2(prs, blank_layout):
    s2 = prs.slides.add_slide(blank_layout)
    bg2 = s2.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg2, BG_LIGHT)
    add_header(
        s2,
        "Platform Purpose & Scope",
        "What LabAdda Is — and What It Is Not",
        "Clear boundaries ensure safe, productive, and comfortable adoption across all research units.",
    )
    col_w = Inches(5.65)
    col_h = Inches(5.3)
    c1_x = Inches(0.8)
    c2_x = Inches(6.88)
    col_y = Inches(1.7)
    c1 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, c1_x, col_y, col_w, col_h)
    set_shape_flat_color(c1, CARD_BG, GREEN_ACCENT, 2)
    s_bar1 = s2.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, c1_x + Inches(0.2), col_y + Inches(0.2), col_w - Inches(0.4), Inches(0.06)
    )
    set_shape_flat_color(s_bar1, GREEN_ACCENT)
    tb1 = s2.shapes.add_textbox(
        c1_x + Inches(0.3), col_y + Inches(0.35), col_w - Inches(0.6), col_h - Inches(0.5)
    )
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "✓ What LabAdda IS"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = GREEN_ACCENT
    is_points = [
        (
            "A Digital Whiteboard for Your Team:",
            "A shared canvas to sketch mechanisms, experimental setups, and brainstorm ideas freely.",
        ),
        (
            "A Grassroots Intranet Experiment:",
            "Built by researchers for researchers to explore faster, simpler peer collabo"
            "ration without delay.",
        ),
        (
            "Fast, Informal Coordination:",
            "Keep meeting minutes, equipment availability notes, and quick action items i"
            "n one place instead of buried in emails.",
        ),
        (
            "Unified Lab Calendar in IST:",
            "Track institutional seminars, division reviews, and project milestones along"
            "side your personal tasks.",
        ),
        (
            "An Organic Community Space:",
            "Usage is expected to grow naturally as more colleagues discover its convenie"
            "nce and invite team peers.",
        ),
    ]
    for title, desc in is_points:
        p_t = tf1.add_paragraph()
        p_t.text = f"• {title} "
        p_t.font.size = Pt(11.5)
        p_t.font.bold = True
        p_t.font.color.rgb = TEXT_MAIN
        p_d = tf1.add_paragraph()
        p_d.text = f"   {desc}"
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = TEXT_MUTED
    return _finish_slide_2(c2_x=c2_x, col_h=col_h, col_w=col_w, col_y=col_y, s2=s2)


def _finish_slide_2(*, c2_x, col_h, col_w, col_y, s2):
    c2 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, c2_x, col_y, col_w, col_h)
    set_shape_flat_color(c2, CARD_BG, ROSE_ACCENT, 2)
    s_bar2 = s2.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, c2_x + Inches(0.2), col_y + Inches(0.2), col_w - Inches(0.4), Inches(0.06)
    )
    set_shape_flat_color(s_bar2, ROSE_ACCENT)
    tb2 = s2.shapes.add_textbox(
        c2_x + Inches(0.3), col_y + Inches(0.35), col_w - Inches(0.6), col_h - Inches(0.5)
    )
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "✗ What LabAdda IS NOT"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = ROSE_ACCENT
    is_not_points = [
        (
            "NOT an Official Institutional Platform:",
            "It does not replace any formal management, circular, or statutory workflow of our organisation.",
        ),
        (
            "NO Place for Sensitive or Official Data:",
            "Never upload classified records, confidential findings, or formal administra"
            "tive grievances here.",
        ),
        (
            "NOT a Heavy File Storage Dump:",
            "Keep uploads lightweight (<20MB per file). Massive raw instrument datasets s"
            "tay on central NAS storage.",
        ),
        (
            "NOT a Monitored Spyware Tool:",
            "Administrators CANNOT read your messages, private notes, or whiteboard sketc"
            "hes (enforced by design).",
        ),
        (
            "NO Bureaucratic Approvals Needed:",
            "Any staff member can create private project groups or discussion clubs instantly in one click.",
        ),
    ]
    for title, desc in is_not_points:
        p_t = tf2.add_paragraph()
        p_t.text = f"• {title} "
        p_t.font.size = Pt(11.5)
        p_t.font.bold = True
        p_t.font.color.rgb = TEXT_MAIN
        p_d = tf2.add_paragraph()
        p_d.text = f"   {desc}"
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = TEXT_MUTED


def slide_3(prs, blank_layout):
    # SLIDE 3: Why Use LabAdda (The 6 Major Capabilities)
    s3 = prs.slides.add_slide(blank_layout)
    bg3 = s3.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg3, BG_LIGHT)
    add_header(
        s3,
        "Key Capabilities",
        "Six Reasons Every Lab Member Should Try LabAdda",
        "Designed to streamline everyday laboratory work, reduce communication fatigu"
        "e, and spark innovation.",
    )

    six_cards = [
        (
            "📅 Central Calendar in IST",
            "Combines institute seminars, division events, project deadlines, and persona"
            "l reminders into one clean view.",
            BLUE_PRIMARY,
        ),
        (
            "🎨 Multi-Board Whiteboards",
            "Sketch mechanisms, stickies, and diagrams with custom board tabs (e.g., 'SiC"
            " Project') and live collaboration.",
            CYAN_ACCENT,
        ),
        (
            "📢 Organized Noticeboards",
            "Official section circulars and team notices pinned with rich discussion thre"
            "ads, eliminating inbox clutter.",
            TEAL_ACCENT,
        ),
        (
            "⚡ Actionable Tasks & Todos",
            "Convert whiteboard ideas and chat messages directly into actionable tasks wi"
            "th due dates and checklists.",
            GREEN_ACCENT,
        ),
        (
            "🔒 Personal Private Workbench",
            "My Day, My Notes, My Whiteboard, and My Tasks remain strictly isolated and visible only to you.",
            PURPLE_ACCENT,
        ),
        (
            "🛡️ Built-in Admin Blindness",
            "Rigorous privacy: administrators see server health and storage metrics only—never your content.",
            ROSE_ACCENT,
        ),
    ]

    grid_w = Inches(3.68)
    grid_h = Inches(2.45)
    xs = [Inches(0.8), Inches(4.82), Inches(8.84)]
    ys = [Inches(1.75), Inches(4.55)]

    for idx, (title, desc, color) in enumerate(six_cards):
        gx = xs[idx % 3]
        gy = ys[idx // 3]

        c_box = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, gx, gy, grid_w, grid_h)
        set_shape_flat_color(c_box, CARD_BG, BORDER_COLOR, 1)

        s_bar = s3.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            gx + Inches(0.15),
            gy + Inches(0.15),
            grid_w - Inches(0.3),
            Inches(0.04),
        )
        set_shape_flat_color(s_bar, color)

        tb = s3.shapes.add_textbox(
            gx + Inches(0.2),
            gy + Inches(0.28),
            grid_w - Inches(0.4),
            grid_h - Inches(0.4),
        )
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p1 = tf.paragraphs[0]
        p1.text = title
        p1.font.size = Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = color

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_MUTED


def slide_4(prs, blank_layout):
    # SLIDE 4: Feature Tour — Home & Central Calendar
    s4 = prs.slides.add_slide(blank_layout)
    bg4 = s4.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg4, BG_LIGHT)
    add_header(
        s4,
        "Feature Deep Dive",
        "Member Home & The Central Calendar",
        "Personalized collegiate greeting engine, instant FAQs, and multi-tier instit"
        "utional event scheduling.",
    )

    # Left Column: Screenshot & Explanation of Home
    left_x = Inches(0.8)
    col_width = Inches(5.65)
    img_h = Inches(3.6)

    # Home Screenshot
    img_home = os.path.join(ASSETS_DIR, "13_home_welcome_and_faq.png")
    if os.path.exists(img_home):
        s4.shapes.add_picture(img_home, left_x, Inches(1.75), width=col_width, height=img_h)

    tb_h = s4.shapes.add_textbox(left_x, Inches(5.45), col_width, Inches(1.6))
    tf_h = tb_h.text_frame
    tf_h.word_wrap = True
    p = tf_h.paragraphs[0]
    p.text = "Member Home & Personalized Salutations"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = BLUE_PRIMARY

    p2 = tf_h.add_paragraph()
    p2.text = (
        "• 180+ Dynamic greetings: Warm, collegiate messages greet you based on the t"
        "ime of day.\n"
        "• Built-in FAQ Accordion: Answers all questions on boundaries, privacy, and "
        "group creation.\n"
        "• One-click access to your research division, project workspaces, and person"
        "al tools."
    )
    p2.font.size = Pt(10.5)
    p2.font.color.rgb = TEXT_MUTED

    # Right Column: Screenshot & Explanation of Calendar
    right_x = Inches(6.88)
    img_cal = os.path.join(ASSETS_DIR, "15_calendar_month_view.png")
    if os.path.exists(img_cal):
        s4.shapes.add_picture(img_cal, right_x, Inches(1.75), width=col_width, height=img_h)

    tb_c = s4.shapes.add_textbox(right_x, Inches(5.45), col_width, Inches(1.6))
    tf_c = tb_c.text_frame
    tf_c.word_wrap = True
    p = tf_c.paragraphs[0]
    p.text = "Central Calendar (Google-Grade Experience)"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = BLUE_PRIMARY

    p2 = tf_c.add_paragraph()
    p2.text = (
        "• Hierarchical Visibility: Institute events for all; division events for uni"
        "t members.\n"
        "• Multiple Views: Smooth switching between Month, Week, Day, and Agenda schedule.\n"
        "• Color Tagging & IST Format: Create events with venue notes, color chips, a"
        "nd quick filters."
    )
    p2.font.size = Pt(10.5)
    p2.font.color.rgb = TEXT_MUTED


def slide_5(prs, blank_layout):
    left_x, right_x = Inches(0.8), Inches(6.88)
    col_width, img_h = Inches(5.65), Inches(3.6)
    # SLIDE 5: Feature Tour — Whiteboards & Creative Sketching
    s5 = prs.slides.add_slide(blank_layout)
    bg5 = s5.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg5, BG_LIGHT)
    add_header(
        s5,
        "Feature Deep Dive",
        "Multi-Board Whiteboards & Visual Thinking",
        "Real-time ink drawing, sticky notes with shapes and sizes, multi-board tabs,"
        " and snapshot publishing.",
    )

    # Multi-board screenshot
    img_wb1 = os.path.join(ASSETS_DIR, "14_multiboard_whiteboard.png")
    if os.path.exists(img_wb1):
        s5.shapes.add_picture(img_wb1, left_x, Inches(1.75), width=col_width, height=img_h)

    tb_w1 = s5.shapes.add_textbox(left_x, Inches(5.45), col_width, Inches(1.6))
    tf_w1 = tb_w1.text_frame
    tf_w1.word_wrap = True
    p = tf_w1.paragraphs[0]
    p.text = "Multi-Board Tabs & Custom Naming"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = TEAL_ACCENT

    p2 = tf_w1.add_paragraph()
    p2.text = (
        "• Up to 5 boards per space: Separate your ideas by topic (e.g., 'SiC Project"
        "', 'Furnace B').\n"
        "• Short Tab Naming: Click the ✏️ pencil icon to assign meaningful custom names.\n"
        "• Live presence & undo: See active team members and undo your own strokes se"
        "amlessly."
    )
    p2.font.size = Pt(10.5)
    p2.font.color.rgb = TEXT_MUTED

    # Team Whiteboard Tools screenshot
    img_wb2 = os.path.join(ASSETS_DIR, "04_collaborative_live_whiteboard.png")
    if os.path.exists(img_wb2):
        s5.shapes.add_picture(img_wb2, right_x, Inches(1.75), width=col_width, height=img_h)

    tb_w2 = s5.shapes.add_textbox(right_x, Inches(5.45), col_width, Inches(1.6))
    tf_w2 = tb_w2.text_frame
    tf_w2.word_wrap = True
    p = tf_w2.paragraphs[0]
    p.text = "Creative Shapes & Snapshot Publishing"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = TEAL_ACCENT

    p2 = tf_w2.add_paragraph()
    p2.text = (
        "• Geometric Shapes & Stickies: Draw lines, arrows, rectangles, and circles e"
        "ffortlessly.\n"
        "• Sticky Note Varieties: Small, medium, large stickies in square, round, sta"
        "r, or heart shapes.\n"
        "• Publish Snapshots: Capture a committed whiteboard region directly to the n"
        "oticeboard."
    )
    p2.font.size = Pt(10.5)
    p2.font.color.rgb = TEXT_MUTED


def slide_6(prs, blank_layout):
    left_x, right_x = Inches(0.8), Inches(6.88)
    col_width, img_h = Inches(5.65), Inches(3.6)
    # SLIDE 6: Feature Tour — Noticeboards, Chat & Tasks
    s6 = prs.slides.add_slide(blank_layout)
    bg6 = s6.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg6, BG_LIGHT)
    add_header(
        s6,
        "Feature Deep Dive",
        "Noticeboards, Fast Chat & Research Tasks",
        "Clear official notices, real-time message streams, and structured action items in one flow.",
    )

    img_nb = os.path.join(ASSETS_DIR, "03_division_noticeboard.png")
    if os.path.exists(img_nb):
        s6.shapes.add_picture(img_nb, left_x, Inches(1.75), width=col_width, height=img_h)

    tb_nb = s6.shapes.add_textbox(left_x, Inches(5.45), col_width, Inches(1.6))
    tf_nb = tb_nb.text_frame
    tf_nb.word_wrap = True
    p = tf_nb.paragraphs[0]
    p.text = "Hierarchical Noticeboard & Pinned Circulars"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT

    p2 = tf_nb.add_paragraph()
    p2.text = (
        "• Pinned Notices: Key equipment rules and division circulars remain pinned a"
        "t the top.\n"
        "• Threaded Replies: Discuss posts with colleague replies without losing context.\n"
        "• Upward Visibility: Section staff automatically see announcements from pare"
        "nt division."
    )
    p2.font.size = Pt(10.5)
    p2.font.color.rgb = TEXT_MUTED

    img_task = os.path.join(ASSETS_DIR, "06_research_tasks_workflow.png")
    if os.path.exists(img_task):
        s6.shapes.add_picture(img_task, right_x, Inches(1.75), width=col_width, height=img_h)

    tb_tk = s6.shapes.add_textbox(right_x, Inches(5.45), col_width, Inches(1.6))
    tf_tk = tb_tk.text_frame
    tf_tk.word_wrap = True
    p = tf_tk.paragraphs[0]
    p.text = "Task Tracking & Chat-to-Task Conversion"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT

    p2 = tf_tk.add_paragraph()
    p2.text = (
        "• Status & Priority: Follow tasks across Open, In Progress, Blocked, and Com"
        "pleted.\n"
        "• Checklists & Sub-items: Break complex experiments into step-by-step milestones.\n"
        "• Direct Conversion: Turn any chat message or whiteboard discussion into an "
        "assigned task."
    )
    p2.font.size = Pt(10.5)
    p2.font.color.rgb = TEXT_MUTED


def slide_7(prs, blank_layout):
    # SLIDE 7: Personal Tools & Ironclad Privacy
    s7 = prs.slides.add_slide(blank_layout)
    bg7 = s7.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg7, BG_LIGHT)
    add_header(
        s7,
        "Your Personal Space",
        "Private Scratchpads & Administrator Blindness",
        "Work with total peace of mind: your private thoughts remain strictly yours.",
    )

    # 3 Column layout for Personal Tools
    p_w = Inches(3.68)
    p_h = Inches(5.1)
    pxs = [Inches(0.8), Inches(4.82), Inches(8.84)]
    py = Inches(1.8)

    p_cards = [
        (
            "☀️ My Day",
            "Morning Executive Dashboard",
            [
                "Consolidates your daily schedule, upcoming deadlines, and new updates into o"
                "ne clean summary.",
                "Never wonder what to tackle first: see assigned project tasks and calendar e"
                "vents side by side.",
                "Helps you plan experimental runs and meeting times seamlessly.",
            ],
            BLUE_PRIMARY,
        ),
        (
            "📝 My Notes",
            "Personal Research Scratchpad",
            [
                "Your confidential digital lab notebook: draft thoughts, literature summaries"
                ", and reminders.",
                "Instant full-text search across your personal notes.",
                "Completely invisible to colleagues and administrators—zero external visibility.",
            ],
            PURPLE_ACCENT,
        ),
        (
            "🛡️ Administrator Blindness",
            "Privacy Enforced By Code",
            [
                "Administrators manage accounts and server health only—they cannot read your contents.",
                "Querying another person's personal notes or calendar returns a uniform 404 Not Found.",
                "Data safety: all changes committed transactionally with zero data leakage.",
            ],
            GREEN_ACCENT,
        ),
    ]

    for i, (head, subhead, bullets, col_color) in enumerate(p_cards):
        c_box = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pxs[i], py, p_w, p_h)
        set_shape_flat_color(c_box, CARD_BG, BORDER_COLOR, 1)

        s_bar = s7.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            pxs[i] + Inches(0.2),
            py + Inches(0.2),
            p_w - Inches(0.4),
            Inches(0.06),
        )
        set_shape_flat_color(s_bar, col_color)

        tb = s7.shapes.add_textbox(
            pxs[i] + Inches(0.25),
            py + Inches(0.35),
            p_w - Inches(0.5),
            p_h - Inches(0.5),
        )
        tf = tb.text_frame
        tf.word_wrap = True

        p1 = tf.paragraphs[0]
        p1.text = head
        p1.font.size = Pt(17)
        p1.font.bold = True
        p1.font.color.rgb = col_color

        p2 = tf.add_paragraph()
        p2.text = subhead
        p2.font.size = Pt(11)
        p2.font.bold = True
        p2.font.color.rgb = TEXT_MAIN

        tf.add_paragraph()  # spacer

        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.size = Pt(11)
            p_b.font.color.rgb = TEXT_MUTED


def slide_8(prs, blank_layout):
    pxs = [Inches(0.8), Inches(4.82), Inches(8.84)]
    # SLIDE 8: Getting Started in 3 Simple Steps
    s8 = prs.slides.add_slide(blank_layout)
    bg8 = s8.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg8, BG_LIGHT)
    add_header(
        s8,
        "Quick Start Guide",
        "How to Get Started on LabAdda in 3 Easy Steps",
        "No software installation, no browser plugins, no setup delays. Accessible fr"
        "om any device on the intranet.",
    )

    step_w = Inches(3.68)
    step_h = Inches(5.1)
    step_y = Inches(1.8)

    steps = [
        (
            "STEP 1",
            "Open Intranet Portal",
            "🖥️",
            [
                "Open your web browser (Edge, Chrome, or Firefox).",
                "Navigate to our internal portal address: http://127.0.0.1:8000/ (or your loc"
                "al laboratory host URL).",
                "Bookmark the link in your browser bar for instantaneous daily access.",
                "Works on Windows, Linux, and touch panels across the institute.",
            ],
            BLUE_PRIMARY,
        ),
        (
            "STEP 2",
            "Sign In to Your Space",
            "🔑",
            [
                "Use your designated laboratory username and password.",
                "If it's your first time, click your one-time activation link to set your secure password.",
                "Notice the personalized salutation greeting you with warm morning/evening encouragement!",
                "Explore the quick FAQ directly on the home page.",
            ],
            CYAN_ACCENT,
        ),
        (
            "STEP 3",
            "Collaborate & Explore",
            "🚀",
            [
                "Visit your Section or Division space to view pinned notices and ongoing discussions.",
                "Open Calendar to check this week's seminars or schedule a project meeting.",
                "Open My Whiteboard and sketch an idea or post sticky notes.",
                "Click '+ New group' to create an instant private workspace for any project o"
                "r reading circle!",
            ],
            GREEN_ACCENT,
        ),
    ]

    for i, (badge_txt, step_title, emoji, bullets, col_color) in enumerate(steps):
        c_box = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pxs[i], step_y, step_w, step_h)
        set_shape_flat_color(c_box, CARD_BG, BORDER_COLOR, 1)

        # Badge pill
        bp = s8.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            pxs[i] + Inches(0.25),
            step_y + Inches(0.25),
            Inches(1.2),
            Inches(0.35),
        )
        set_shape_flat_color(bp, col_color)
        tf_bp = bp.text_frame
        p_bp = tf_bp.paragraphs[0]
        p_bp.text = badge_txt
        p_bp.alignment = PP_ALIGN.CENTER
        p_bp.font.size = Pt(10)
        p_bp.font.bold = True
        p_bp.font.color.rgb = WHITE

        tb = s8.shapes.add_textbox(
            pxs[i] + Inches(0.25),
            step_y + Inches(0.75),
            step_w - Inches(0.5),
            step_h - Inches(0.9),
        )
        tf = tb.text_frame
        tf.word_wrap = True

        p1 = tf.paragraphs[0]
        p1.text = f"{emoji} {step_title}"
        p1.font.size = Pt(16)
        p1.font.bold = True
        p1.font.color.rgb = TEXT_MAIN

        tf.add_paragraph()  # spacer

        for b in bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.size = Pt(11)
            p_b.font.color.rgb = TEXT_MUTED


def slide_9(prs, blank_layout):
    # SLIDE 9: Best Practices & Etiquette (Digital Whiteboard Rule)
    s9 = prs.slides.add_slide(blank_layout)
    bg9 = s9.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg9, BG_LIGHT)
    add_header(
        s9,
        "Usage Guidelines",
        "Best Practices for a Safe & Collegial Environment",
        "Simple rules of thumb that ensure LabAdda remains fast, enjoyable, and safe for everyone.",
    )

    rules = [
        (
            "The Digital Whiteboard Rule",
            "Post only what you would comfortably write on a physical lab whiteboard",
            "Treat LabAdda as an informal visual scratchpad. Great for brainstorming hypo"
            "theses, diagramming mechanisms, planning trials, and coordinating equipment "
            "times. Keep any sensitive, restricted, or official administrative records st"
            "rictly on designated formal institutional channels.",
            BLUE_PRIMARY,
        ),
        (
            "Keep File Attachments Lightweight",
            "Upload concise summaries, micrographs, and PDFs under 20 MB",
            "LabAdda operates on a dedicated intranet server with local SSD storage. Keep"
            "ing files light ensures lightning-fast load times for everyone. Massive raw "
            "spectrometer or diffraction datasets should remain on the institute's high-c"
            "apacity central NAS storage.",
            AMBER_ACCENT,
        ),
        (
            "Friendly Communication & Ethics",
            "Communicate with courtesy, mutual respect, and encouraging teamwork",
            "Research breakthroughs happen when colleagues support each other's ideas. Ke"
            "ep discussions constructive, share credit generously, and foster a welcoming"
            " atmosphere for junior scholars and multidisciplinary teams.",
            GREEN_ACCENT,
        ),
        (
            "Give Feedback & Shape the Future",
            "This is an active experiment—your feedback directly influences updates",
            "Have an idea for a tool that would save your lab 10 minutes a day? Spotted a"
            " quirk? Click the Feedback button in the top bar anytime. Our developer team"
            " reviews all suggestions to continuously enhance the platform.",
            PURPLE_ACCENT,
        ),
    ]

    r_w = Inches(5.65)
    r_h = Inches(2.45)
    r_xs = [Inches(0.8), Inches(6.88)]
    r_ys = [Inches(1.75), Inches(4.55)]

    for idx, (title, sub, body, color) in enumerate(rules):
        rx = r_xs[idx % 2]
        ry = r_ys[idx // 2]

        c_box = s9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx, ry, r_w, r_h)
        set_shape_flat_color(c_box, CARD_BG, BORDER_COLOR, 1)

        s_bar = s9.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            rx + Inches(0.2),
            ry + Inches(0.18),
            r_w - Inches(0.4),
            Inches(0.04),
        )
        set_shape_flat_color(s_bar, color)

        tb = s9.shapes.add_textbox(rx + Inches(0.25), ry + Inches(0.3), r_w - Inches(0.5), r_h - Inches(0.45))
        tf = tb.text_frame
        tf.word_wrap = True

        p1 = tf.paragraphs[0]
        p1.text = title
        p1.font.size = Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = color

        p2 = tf.add_paragraph()
        p2.text = sub
        p2.font.size = Pt(11)
        p2.font.bold = True
        p2.font.color.rgb = TEXT_MAIN

        p3 = tf.add_paragraph()
        p3.text = body
        p3.font.size = Pt(10.5)
        p3.font.color.rgb = TEXT_MUTED


def slide_10(prs, blank_layout):
    s10 = prs.slides.add_slide(blank_layout)
    bg10 = s10.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    set_shape_flat_color(bg10, NAVY_DARK)
    top_bar10 = s10.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(0.12))
    set_shape_flat_color(top_bar10, GREEN_ACCENT)
    t_box10 = s10.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(1.5))
    tf10 = t_box10.text_frame
    tf10.word_wrap = True
    p_c1 = tf10.paragraphs[0]
    p_c1.text = "Ready to Explore LabAdda?"
    p_c1.font.size = Pt(36)
    p_c1.font.bold = True
    p_c1.font.color.rgb = WHITE
    p_c2 = tf10.add_paragraph()
    p_c2.text = "Let's connect our teams, sketch bold ideas, and achieve research excellence together."
    p_c2.font.size = Pt(18)
    p_c2.font.color.rgb = CYAN_ACCENT
    res_cards = [
        (
            "📖 In-App Help Center",
            "Comprehensive User Guides",
            "Browse 87 detailed articles covering every feature from whiteboards to calen"
            "dar at /help or via the 'Help with this page' link.",
        ),
        (
            "💬 Feedback Channel",
            "Direct to Developer Team",
            "Click the 'Feedback' button in the top navigation bar anytime to submit sugg"
            "estions, bug reports, or feature requests.",
        ),
        (
            "🏢 Your Unit Steward",
            "Account & Workspace Support",
            "Reach out to your designated division or section steward for additional work"
            "space grants or login assistance.",
        ),
    ]
    res_w = Inches(3.6)
    res_gap = Inches(0.25)
    res_y = Inches(3.2)
    res_h = Inches(2.5)
    for i, (head, sub, desc) in enumerate(res_cards):
        rx = Inches(1.0) + i * (res_w + res_gap)
        c_shape = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, rx, res_y, res_w, res_h)
        set_shape_flat_color(c_shape, NAVY_SLATE, NAVY_HEADER, 1.5)
        s_bar = s10.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, rx + Inches(0.15), res_y + Inches(0.15), res_w - Inches(0.3), Inches(0.04)
        )
        set_shape_flat_color(s_bar, CYAN_ACCENT if i == 0 else TEAL_ACCENT if i == 1 else GREEN_ACCENT)
        tb = s10.shapes.add_textbox(
            rx + Inches(0.2), res_y + Inches(0.3), res_w - Inches(0.4), res_h - Inches(0.4)
        )
        tf = tb.text_frame
        tf.word_wrap = True
        p1 = tf.paragraphs[0]
        p1.text = head
        p1.font.size = Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = WHITE
        p2 = tf.add_paragraph()
        p2.text = sub
        p2.font.size = Pt(11)
        p2.font.bold = True
        p2.font.color.rgb = CYAN_ACCENT
        p3 = tf.add_paragraph()
        p3.text = desc
        p3.font.size = Pt(10.5)
        p3.font.color.rgb = TEXT_LIGHT
    return _finish_slide_10(s10=s10)


def _finish_slide_10(*, s10):
    fb = s10.shapes.add_textbox(Inches(1.0), Inches(6.3), Inches(11.3), Inches(0.5))
    tf_fb = fb.text_frame
    p_fb = tf_fb.paragraphs[0]
    p_fb.text = (
        "LabAdda Intranet Workspace · Conceived and Developed by Dr. K. V. Mani Krish"
        "na, Materials Group · Version 0.0.2 Beta"
    )
    p_fb.font.size = Pt(10.5)
    p_fb.font.color.rgb = TEXT_LIGHT
    p_fb.alignment = PP_ALIGN.CENTER


def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]
    slide_1(prs, blank_layout)
    slide_2(prs, blank_layout)
    slide_3(prs, blank_layout)
    slide_4(prs, blank_layout)
    slide_5(prs, blank_layout)
    slide_6(prs, blank_layout)
    slide_7(prs, blank_layout)
    slide_8(prs, blank_layout)
    slide_9(prs, blank_layout)
    slide_10(prs, blank_layout)
    prs.save(OUTPUT_PPTX)
    print(f"Presentation generated: {OUTPUT_PPTX}; slides: {len(prs.slides)}")


if __name__ == "__main__":
    build_presentation()
