"""Write closed metric minutes to ``metric_samples`` in one batched upsert.

Rows carry absolute per-bucket totals and an upsert replaces them, so a repeated flush of the
same minutes (a retry after a failure between commit and ``discard``) cannot double count.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import MetricSample
from .registry import REGISTRY, Registry, Sample

# Six bound parameters per row keeps a statement far below PostgreSQL's parameter limit,
# even after the scheduler has been paused and many minutes are waiting.
ROWS_PER_STATEMENT = 2000


def upsert(db: Session, resolution: str, samples: Iterable[Sample]) -> int:
    """Insert or replace rows for one resolution; the caller commits."""
    rows = [
        {
            "bucket_start": sample.bucket_start,
            "resolution": resolution,
            "metric": sample.metric,
            "dimension": sample.dimension,
            "value": sample.value,
            "samples": sample.samples,
        }
        for sample in samples
    ]
    for start in range(0, len(rows), ROWS_PER_STATEMENT):
        statement = insert(MetricSample).values(rows[start : start + ROWS_PER_STATEMENT])
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["bucket_start", "resolution", "metric", "dimension"],
                set_={"value": statement.excluded.value, "samples": statement.excluded.samples},
            )
        )
    return len(rows)


def flush(db: Session, *, now: datetime, registry: Registry = REGISTRY) -> int:
    """Write every closed minute, commit, then forget it; returns the number of rows written."""
    samples = registry.closed(now)
    if not samples:
        return 0
    written = upsert(db, "minute", samples)
    db.commit()
    registry.discard(samples)
    return written
