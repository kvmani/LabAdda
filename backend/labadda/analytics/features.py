"""Which stored counters the Activity page reads, and the plain words it shows for them."""

from __future__ import annotations

# (metric, label) in the order of the "activity by feature" chart.
FEATURES: tuple[tuple[str, str], ...] = (
    ("posts.created", "Posts"),
    ("replies.created", "Replies"),
    ("chat.messages", "Chat messages"),
    ("board.operations", "Whiteboard changes"),
    ("tasks.created", "Tasks created"),
    ("tasks.completed", "Tasks completed"),
    ("uploads.count", "Files added"),
)
FEATURE_METRICS = tuple(metric for metric, _ in FEATURES)
# "Items created": things people made, not edits to them (whiteboard strokes, completions).
ITEM_METRICS = ("posts.created", "replies.created", "chat.messages", "tasks.created", "uploads.count")

KINDS: tuple[tuple[str, str], ...] = (
    ("org", "Organisation units"),
    ("project", "Projects"),
    ("group", "Groups"),
)

SIZE_LABELS: dict[str, str] = {
    "under_100kb": "Under 100 KB",
    "under_1mb": "100 KB to 1 MB",
    "under_10mb": "1 MB to 10 MB",
    "10mb_or_more": "10 MB or more",
}

REQUESTS = "http.requests"
CONNECTIONS = "sockets.connected"
STORAGE: tuple[tuple[str, str], ...] = (("assets.bytes", "files"), ("db.size_bytes", "database"))
