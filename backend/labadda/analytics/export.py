"""The Activity page as CSV rows: exactly the figures the page shows, suppression included."""

from __future__ import annotations

import csv
import io

from ..people_export import safe_cell

COLUMNS = ("section", "item", "this period", "previous period")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
NOT_MEASURED = "not measured"
SUPPRESSED = "fewer than 5"


def _value(value: object, word: str = "measured") -> str:
    if word == "suppressed":
        return SUPPRESSED
    if value is None:
        return NOT_MEASURED
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _figure(found: dict | None) -> str:
    if found is None:
        return ""
    if found["state"] == "suppressed":
        return SUPPRESSED
    if found["state"] == "unknown":
        return NOT_MEASURED
    return str(found["value"])


def _tiles(summary: dict) -> list[list[str]]:
    rows = []
    for tile in summary["tiles"]:
        value, previous = tile["value"], tile["previous"]
        if tile["unit"] == "fraction":
            value = None if value is None else f"{value:.1%}"
            previous = None if previous is None else f"{previous:.1%}"
        rows.append(
            ["Summary", tile["label"], _value(value, tile["state"]), _value(previous, tile["previous_state"])]
        )
    return rows


def _charts(charts: dict) -> list[list[str]]:
    rows = [
        ["Active people per day", point["day"], _value(point["value"], point["state"]), ""]
        for point in charts["active_per_day"]
    ]
    labels = {series["key"]: series["label"] for series in charts["features"]["series"]}
    for point in charts["features"]["points"]:
        for key, label in labels.items():
            value = None if point["values"] is None else point["values"][key]
            item = f"{point['start']} {label}"
            rows.append(["Activity by feature", item, _value(value, point["state"]), ""])
    rows += [
        ["Items created by kind", kind["label"], _value(kind["value"], kind["state"]), ""]
        for kind in charts["items_by_kind"]
    ]
    heat = charts["weekday_hour"]
    for cell in heat["cells"]:
        item = f"{WEEKDAYS[cell['weekday'] - 1]} {cell['hour']:02d}:00"
        word = "suppressed" if cell["weekday"] in heat["suppressed_weekdays"] else "measured"
        rows.append(["Requests by weekday and hour", item, _value(cell["value"], word), ""])
    for point in charts["storage"]:
        rows.append(["Storage (bytes)", f"{point['day']} files", _value(point["files_bytes"]), ""])
        rows.append(["Storage (bytes)", f"{point['day']} database", _value(point["database_bytes"]), ""])
    rows += [
        ["Uploads by size", band["label"], _value(band["value"], band["state"]), ""]
        for band in charts["upload_sizes"]
    ]
    return rows


def _units(units: dict) -> list[list[str]]:
    rows = []
    entries = [(unit["name"], unit) for unit in units["units"]]
    if units["no_home_unit"]:
        entries.append(("No home unit", units["no_home_unit"]))
    for name, unit in entries:
        rows.append(
            [
                "Active people by home unit",
                name,
                _figure(unit["active_people"]),
                _figure(unit["previous_active_people"]),
            ]
        )
        if unit["items_created"] is not None:
            rows.append(["Items created by unit", name, _figure(unit["items_created"]), ""])
    return rows


def rows(summary: dict, units: dict) -> list[list[str]]:
    """Every exported row; an unmeasured period exports one row that says so."""
    if summary["state"] == "unknown":
        return [["Summary", "Usage figures", NOT_MEASURED, ""]]
    found = _tiles(summary) + _charts(summary["charts"])
    if units["state"] == "measured":
        found += _units(units)
    return found


def to_csv(found: list[list[str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for row in found:
        writer.writerow([safe_cell(cell) for cell in row])
    return "﻿" + buffer.getvalue()
