"""GET /admin/health: the latest sampled result of every health item, served from memory (AD-07)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..deps import Actor, require_console
from ..health import ITEMS
from ..health.sampler import Sampler
from ..health.types import worst
from ..security import utcnow
from ..serialize import iso

router = APIRouter(tags=["health"])
console_health = require_console("health")


def _chart(item) -> dict | None:
    chart = item.chart
    return {"metric": chart.metric, "dimension": chart.dimension, "unit": chart.unit} if chart else None


def current_items(request: Request) -> list[dict]:
    """The latest result of every item, measured now when no background scheduler runs."""
    sampler: Sampler = request.app.state.health
    # Without a background scheduler (a development instance) nobody else would measure.
    if not request.app.state.settings.run_scheduler and sampler.due(utcnow()):
        sampler.run_once()
    rows = sampler.snapshot()
    items = []
    for item, (_, result, age) in zip(ITEMS, rows, strict=True):
        items.append(
            {
                "key": item.key,
                "label": item.label,
                **result.as_dict(),
                "age_seconds": round(age),
                "help": f"troubleshooting/{item.help}",
                "chart": _chart(item),
            }
        )
    return items


@router.get("/admin/health")
def health(request: Request, actor: Actor = Depends(console_health)) -> dict:
    """Nothing here touches content tables; the figures were measured by the background sampler."""
    items = current_items(request)
    return {
        "overall": worst([row["status"] for row in items]),
        "generated_at": iso(utcnow()),
        "interval_seconds": request.app.state.settings.health.sample_seconds,
        "items": items,
    }
