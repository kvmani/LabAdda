"""Text rules shared by change requests."""

import unicodedata


def single_line(value: object) -> object:
    """Keep staff text single-line and valid for PostgreSQL/UTF-8 JSON."""
    if isinstance(value, str):
        if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
            raise ValueError("Use ordinary single-line text without control characters.")
        return value.strip() or None
    return value
