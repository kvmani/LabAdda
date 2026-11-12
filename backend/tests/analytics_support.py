"""Synthetic people, activity days and metric samples for the analytics tests."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy.dialects.postgresql import insert

from labadda import analytics
from labadda.metrics.flush import upsert
from labadda.metrics.registry import Sample
from labadda.models import ActivityDay, User


@pytest.fixture(autouse=True)
def fresh_cache():
    analytics.CACHE.clear()
    yield
    analytics.CACHE.clear()


def add_people(db_factory, home: str | None, count: int, prefix: str) -> list[str]:
    """Create ``count`` fictional people with the given home workspace; returns their IDs."""
    created = []
    with db_factory() as db:
        for number in range(count):
            person = User(
                username=f"{prefix}-{number:02d}",
                display_name=f"Synthetic {prefix} {number}",
                must_set_password=True,
                home_workspace_id=uuid.UUID(home) if home else None,
            )
            db.add(person)
            db.flush()
            created.append(str(person.id))
        db.commit()
    return created


def mark_active(db_factory, people: list[str], *days: date) -> None:
    with db_factory() as db:
        for person in people:
            for day in days:
                db.execute(
                    insert(ActivityDay).values(user_id=uuid.UUID(person), day=day).on_conflict_do_nothing()
                )
        db.commit()


def store(db_factory, resolution: str, *rows: tuple[datetime, str, str, float]) -> None:
    with db_factory() as db:
        upsert(
            db,
            resolution,
            [Sample(start, metric, dimension, value, 1) for start, metric, dimension, value in rows],
        )
        db.commit()


def tile(summary: dict, key: str) -> dict:
    return next(item for item in summary["tiles"] if item["key"] == key)
