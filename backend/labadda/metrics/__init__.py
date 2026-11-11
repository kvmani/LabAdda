"""Bounded operational metrics (AD-08): metadata only, never content, paths or user text."""

from .collector import Collector
from .counters import (
    count,
    count_attachments,
    count_attachments_on_commit,
    count_workspace,
    count_workspace_on_commit,
)
from .middleware import MetricsMiddleware
from .registry import REGISTRY

__all__ = [
    "REGISTRY",
    "Collector",
    "MetricsMiddleware",
    "count",
    "count_attachments",
    "count_attachments_on_commit",
    "count_workspace",
    "count_workspace_on_commit",
]
