"""Bounded operational metrics (AD-08): metadata only, never content, paths or user text."""

from .counters import count, count_workspace, count_workspace_on_commit
from .registry import REGISTRY

__all__ = ["REGISTRY", "count", "count_workspace", "count_workspace_on_commit"]
