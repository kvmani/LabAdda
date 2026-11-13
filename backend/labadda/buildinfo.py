"""Version and commit recorded with feedback, read on the server from the single build record."""

from __future__ import annotations

from . import __version__, build_info

UNKNOWN = "unknown"


def software_version() -> str:
    return __version__


def software_commit() -> str:
    commit, _ = build_info.commit_and_date()
    return commit or UNKNOWN
