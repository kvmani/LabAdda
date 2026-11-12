"""Small-group protection for per-unit figures, applied before anything leaves the server.

Rules (AD-08, T64):

1. A unit's figures are published only when at least ``MIN_GROUP`` of its people were active in
   the period; otherwise the whole row is ``suppressed`` (the number is never sent).
2. Complementary suppression: the site totals are published exactly and every person has at
   most one home, so "total minus the published units" would reveal the suppressed rows taken
   together. While suppressed rows cover fewer than ``MIN_GROUP`` active people, the smallest
   published row is suppressed as well.
3. Published people counts are rounded to the nearest ``ROUND_TO``, so the difference between
   overlapping periods (7 days inside 30, this period against the previous one, today against
   yesterday) cannot be read down to one person.

Units are reported for their own home people only, never including their sub-units, so a parent
minus its children reveals nothing either.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping

MIN_GROUP = 5
ROUND_TO = 5


def rounded(value: float) -> int:
    """Round half up to the nearest ``ROUND_TO``; a published group is never shown below it."""
    return max(ROUND_TO, int((value + ROUND_TO / 2) // ROUND_TO) * ROUND_TO)


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


def figure(value: float, shown: bool, *, people: bool) -> dict:
    """One per-unit figure as sent to the client: a number, or ``suppressed`` without one."""
    if not shown:
        return {"state": "suppressed"}
    return {"state": "shown", "value": rounded(value) if people else int(value)}
