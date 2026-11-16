"""Allowlisted bundled fonts keep board exports independent of host font packages."""

from pathlib import Path

from PIL import ImageFont

from .errors import Invalid

FONT_FILES = {
    "sans": "DejaVuSans.ttf",
    "serif": "DejaVuSerif.ttf",
    "mono": "DejaVuSansMono.ttf",
    "handwritten": "Kalam-Regular.ttf",
}


def validate_style(data: dict) -> dict:
    """Accept a small, bounded style vocabulary instead of arbitrary CSS or paths."""
    family = data.get("font_family", "sans")
    size = data.get("font_size", 16)
    if not isinstance(family, str) or family not in FONT_FILES:
        raise Invalid("invalid_board_op", "Choose a supported board font.")
    if not isinstance(size, int) or isinstance(size, bool) or not 8 <= size <= 48:
        raise Invalid("invalid_board_op", "Font size must be a whole number from 8 to 48.")
    return {"font_family": family, "font_size": size}


def board_font(data: dict, scale: float) -> ImageFont.FreeTypeFont:
    """Render the same packaged typeface in server snapshots and browser canvases."""
    family = data.get("font_family", "sans")
    filename = FONT_FILES.get(family, FONT_FILES["sans"])
    return ImageFont.truetype(
        str(Path(__file__).with_name("fonts") / filename),
        size=max(1, round(data.get("font_size", 16) * scale)),
    )
