"""Small-group protection, applied before anything leaves the server (AD-08, T64).

Per-unit people:

1. A unit's figures are published only when at least ``MIN_GROUP`` of its home people were
   active in the period; otherwise the whole row is ``suppressed`` (the number is never sent).
2. Complementary suppression: site totals are published and every person has at most one home,
   so "total minus the published units" would reveal the suppressed rows taken together. While
   suppressed rows that have people hold fewer than ``MIN_GROUP`` active people, the smallest
   published row is suppressed as well.
3. Published counts are rounded to the nearest ``ROUND_TO``. This blurs the difference between
   overlapping periods, but it is deterministic: watching a figure step between two roundings
   as a sliding window moves can still show that the count crossed a boundary. That residual
   risk is accepted and documented in the console guide.

Per-unit items follow the people rule, and then their own complementary rule: the "Organisation
units" item total is published, so the items of hidden units (including units nobody has as a
home) are published only as a remainder that is spread over at least two hidden units and holds
at least ``MIN_GROUP`` items; otherwise more published item figures are hidden.

Units count only their own home people, never their sub-units, so a parent minus its children
reveals nothing either. Home units are read as they are now (see the guide on transfers).
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping

MIN_GROUP = 5
ROUND_TO = 5


def rounded(value: float) -> int:
    """Round half up to the nearest ``ROUND_TO`` (a published group of people is at least 5)."""
    return int((value + ROUND_TO / 2) // ROUND_TO) * ROUND_TO


def published(active: Mapping[Hashable, int]) -> set[Hashable]:
    """The keys whose rows may be published, given each row's exact active people.

    ``active`` holds only rows that have at least one person; a row with nobody in it reveals
    nothing about anyone and is suppressed by the caller without affecting the others.
    """
    shown = {key for key, people in active.items() if people >= MIN_GROUP}
    while True:
        hidden = sum(people for key, people in active.items() if key not in shown)
        if len(shown) == len(active) or hidden >= MIN_GROUP or not shown:
            return shown
        smallest = min(shown, key=lambda key: (active[key], str(key)))
        shown.discard(smallest)


def figure(value: float, shown: bool) -> dict:
    """One per-unit figure as sent to the client: a rounded number, or ``suppressed`` without one."""
    if not shown:
        return {"state": "suppressed"}
    return {"state": "shown", "value": rounded(value)}


def published_items(items: Mapping[Hashable, float], candidates: set[Hashable]) -> set[Hashable]:
    """The rows whose item counts may be published.

    ``items`` holds every row that has items in the organisation total, including units without
    home people and the overflow bucket; ``candidates`` are the rows whose people are published.
    """
    shown = {key for key in candidates if key in items}
    while shown:
        hidden = [value for key, value in items.items() if key not in shown]
        spread = sum(1 for value in hidden if value > 0)
        if not hidden or (sum(hidden) >= MIN_GROUP and spread >= 2):
            return shown
        shown.discard(min(shown, key=lambda key: (items[key], str(key))))
    return shown
