"""Reusable realistic ink fixtures exercise upload and board input boundaries."""

import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree

from labadda.api.board import _validate_add

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "fixtures/research-day"


def test_research_art_is_deterministic_and_native(tmp_path):
    spec = importlib.util.spec_from_file_location("research_art", ROOT / "scripts/generate-research-art.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    module.generate()
    for name in ("research-plan.svg", "sticky-notes.svg", "interface-schematic.svg", "board-objects.json"):
        assert (tmp_path / name).read_bytes() == (ART / name).read_bytes()
    objects = json.loads((ART / "board-objects.json").read_text())
    assert {o["actor"] for o in objects} == {"asha", "bharat", "mira", "chitra", "deepa"}
    assert sum(o["kind"] == "sticky" for o in objects) == 5
    assert all(o["kind"] == "sticky" for o in objects[:5])
    assert all(o["kind"] == "stroke" for o in objects[5:])
    for obj in objects:
        normalized = _validate_add(None, None, None, {"kind": obj["kind"], "data": obj["data"]})
        assert normalized["data"] == obj["data"]
    svg = ElementTree.parse(ART / "research-plan.svg")  # noqa: S314 — committed fixture file
    assert len(svg.findall(".//{http://www.w3.org/2000/svg}polyline")) == sum(
        o["kind"] == "stroke" for o in objects
    )
    assert not svg.findall(".//{http://www.w3.org/2000/svg}script")
    assert not any("href" in key for element in svg.iter() for key in element.attrib)


def test_realistic_svg_source_cannot_cross_upload_boundary(as_user):
    svg = (ART / "research-plan.svg").read_bytes()
    bharat = as_user("bharat")
    for mime in ("image/svg+xml", "image/png"):
        response = bharat.post("/uploads", files={"file": ("research-plan.svg", svg, mime)})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unsupported_type"
