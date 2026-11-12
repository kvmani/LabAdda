#!/usr/bin/env python3
"""Deterministic single-stroke lettering and research sketch fixtures (no fonts/network)."""

import json
import random
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1] / "fixtures/research-day"
GLYPHS = {
    "A": "0,8 3,0 6,8|1,5 5,5",
    "B": "0,8 0,0 4,0 6,2 4,4 0,4|4,4 6,6 4,8 0,8",
    "C": "6,1 4,0 1,1 0,4 1,7 4,8 6,7",
    "D": "0,8 0,0 3,0 6,2 6,6 3,8 0,8",
    "E": "6,0 0,0 0,8 6,8|0,4 5,4",
    "F": "0,8 0,0 6,0|0,4 5,4",
    "G": "6,1 2,0 0,3 0,6 2,8 6,7 6,4 3,4",
    "H": "0,0 0,8|6,0 6,8|0,4 6,4",
    "I": "0,0 6,0|3,0 3,8|0,8 6,8",
    "J": "0,0 6,0 6,6 4,8 1,8 0,6",
    "K": "0,0 0,8|6,0 0,4 6,8",
    "L": "0,0 0,8 6,8",
    "M": "0,8 0,0 3,4 6,0 6,8",
    "N": "0,8 0,0 6,8 6,0",
    "O": "3,0 0,2 0,6 3,8 6,6 6,2 3,0",
    "P": "0,8 0,0 4,0 6,2 4,4 0,4",
    "Q": "3,0 0,2 0,6 3,8 6,6 6,2 3,0|4,6 7,9",
    "R": "0,8 0,0 4,0 6,2 4,4 0,4|3,4 6,8",
    "S": "6,1 3,0 0,2 1,4 5,4 6,6 3,8 0,7",
    "T": "0,0 6,0|3,0 3,8",
    "U": "0,0 0,6 2,8 4,8 6,6 6,0",
    "V": "0,0 3,8 6,0",
    "W": "0,0 1,8 3,4 5,8 6,0",
    "X": "0,0 6,8|6,0 0,8",
    "Y": "0,0 3,4 6,0|3,4 3,8",
    "Z": "0,0 6,0 0,8 6,8",
    "0": "3,0 0,2 0,6 3,8 6,6 6,2 3,0",
    "1": "1,2 3,0 3,8|0,8 6,8",
    "2": "0,1 3,0 6,2 0,8 6,8",
    "3": "0,0 6,0 3,4 6,6 4,8 0,8",
    "4": "5,8 5,0 0,5 6,5",
    "5": "6,0 0,0 0,4 4,4 6,6 4,8 0,8",
    "6": "6,0 2,0 0,4 0,7 4,8 6,6 4,4 0,4",
    "7": "0,0 6,0 2,8",
    "8": "3,4 0,2 3,0 6,2 3,4 0,6 3,8 6,6 3,4",
    "9": "6,4 2,4 0,2 2,0 6,1 6,7 3,8",
    "-": "0,4 6,4",
    "/": "0,8 6,0",
    ":": "3,2 3,2.2|3,6 3,6.2",
    "?": "0,1 3,0 6,2 3,4 3,5|3,8 3,8.2",
    ">": "0,0 6,4 0,8",
    "+": "0,4 6,4|3,1 3,7",
    "=": "0,3 6,3|0,6 6,6",
    ".": "3,8 3,8.2",
}


def generate():
    rng = random.Random(8128)
    ops = []

    def stroke(points, actor="ben", color="#1565c0", width=2):
        ops.append(
            {
                "actor": actor,
                "kind": "stroke",
                "data": {
                    "points": [[round(x, 1), round(y, 1)] for x, y in points],
                    "color": color,
                    "width": width,
                },
            }
        )

    def hand(text, x, y, scale=2, actor="ben", color="#1f2933"):  # noqa: PLR0917 — drawing helper, many positional call sites
        for i, c in enumerate(text):
            if c == " ":
                continue
            for segment in GLYPHS[c].split("|"):
                pts = [list(map(float, p.split(","))) for p in segment.split()]
                stroke(
                    [
                        (
                            x + i * 8 * scale + a * scale + b * 0.11 + rng.uniform(-0.35, 0.35),
                            y + b * scale + rng.uniform(-0.4, 0.4),
                        )
                        for a, b in pts
                    ],
                    actor,
                    color,
                    1.8,
                )

    def box(x, y, w, h, actor, color):  # noqa: PLR0917 — geometry helper, many positional call sites
        stroke(
            [(x + 2, y), (x + w, y + 2), (x + w - 1, y + h), (x, y + h - 2), (x + 2, y)], actor, color, 2.4
        )

    def arrow(x, y, xx, yy, actor="ben"):
        stroke([(x, y), (xx, yy)], actor)
        stroke([(xx - 9, yy - 6), (xx, yy), (xx - 9, yy + 7)], actor)

    hand("AURORA / CATALYST INTERFACE STUDY", 36, 24, 2.6, "dana")
    hand("QUESTION: DOES OXYGEN VACANCY DENSITY CONTROL SELECTIVITY?", 36, 66, 1.65, "dana")
    boxes = [
        (40, "PREPARE FILMS", "ASHA + BEN", "asha", "#1565c0"),
        (360, "SURFACE CHECK", "MIRA / XPS", "mira", "#6a1b9a"),
        (680, "REACTION TEST", "CHEN / GC", "chen", "#2e7d32"),
    ]
    for x, title, owner, actor, color in boxes:
        box(x, 140, 260, 115, actor, color)
        hand(title, x + 15, 158, 2, actor, color)
        hand(owner, x + 15, 202, 1.7, actor, color)
    arrow(301, 193, 353, 193)
    arrow(622, 193, 673, 193)
    hand("20 / 40 / 60 NM", 48, 277, 1.8, "asha")
    hand("BLANK + REFERENCE", 363, 277, 1.65, "mira")
    hand("3 REPEATS / BATCH", 683, 277, 1.7, "chen")
    stroke([(810, 306), (810, 352), (168, 352), (168, 309)], "dana", "#c62828")
    hand("IF DRIFT > 5: RECALIBRATE BEFORE NEXT BATCH", 220, 365, 1.65, "dana", "#c62828")
    box(46, 418, 894, 115, "ben", "#1565c0")
    hand("DECISION GATE / FRIDAY REVIEW", 65, 436, 2, "dana")
    hand("BEN: PAIR FILM IDS WITH GC RUN IDS BEFORE FITTING.", 65, 478, 1.85, "ben")
    notes = [
        ("asha", 45, "ASHA / PREP", "KEEP A BLANK", "EACH BATCH", "#fff59d"),
        ("ben", 233, "BEN / CHECK", "REPEAT 40 NM", "DRIFT FIRST", "#b3e5fc"),
        ("mira", 421, "MIRA / XPS", "NO AIR BREAK", "LOG TRANSFER", "#c8e6c9"),
        ("chen", 609, "CHEN / GC", "3 REPEATS", "ADD CONTROL", "#ffccbc"),
        ("dana", 797, "DANA / NEXT", "REVIEW FRIDAY", "SHARE SUMMARY", "#fff59d"),
    ]
    papers = []
    for actor, x, title, l1, l2, color in notes:
        # Native sticky objects remain selectable and editable; handwriting is native pen strokes.
        ops.append(
            {"actor": actor, "kind": "sticky", "data": {"x": x, "y": 575, "text": title, "color": color}}
        )
        hand(l1, x + 10, 620, 1.45, actor)
        hand(l2, x + 10, 650, 1.45, actor)
        papers.append(f'<path d="M{x},575 l180,2 -2,118 -178,-1 Z" fill="{color}"/>')
        # SVG labels mirror the native sticky titles; the note body uses vector handwriting.
        papers.append(
            f'<text x="{x + 10}" y="600" font-family="sans-serif" font-size="13">{escape(title)}</text>'
        )
    polylines = [
        '<polyline points="'
        + " ".join(f"{x},{y}" for x, y in o["data"]["points"])
        + f'" fill="none" stroke="{o["data"]["color"]}" stroke-width="{o["data"]["width"]}" '
        + 'stroke-linecap="round" stroke-linejoin="round"/>'
        for o in ops
        if o["kind"] == "stroke"
    ]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 730" width="1000" '
        'height="730"><title>Fictional Aurora research plan with five handwritten sticky '
        'notes</title><rect width="1000" height="730" fill="#fff"/>'
        + "".join(papers + polylines)
        + "</svg>\n"
    )
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "research-plan.svg").write_text(svg)
    (ROOT / "sticky-notes.svg").write_text(
        svg.replace(
            'viewBox="0 0 1000 730" width="1000" height="730"',
            'viewBox="25 555 965 160" width="965" height="160"',
        )
    )
    (ROOT / "interface-schematic.svg").write_text(
        svg.replace(
            'viewBox="0 0 1000 730" width="1000" height="730"',
            'viewBox="25 120 935 280" width="935" height="280"',
        )
    )
    # Backgrounds must commit before handwriting, including when the harness batches operations.
    ops = [o for o in ops if o["kind"] == "sticky"] + [o for o in ops if o["kind"] == "stroke"]
    (ROOT / "board-objects.json").write_text(json.dumps(ops, indent=2) + "\n")
    print(f"{len(ops)} native board objects generated")


if __name__ == "__main__":
    generate()
