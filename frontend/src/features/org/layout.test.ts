import { describe, expect, it } from "vitest";
import {
  GAP_X,
  NODE_WIDTH,
  ancestorIds,
  descendantIds,
  fitScale,
  layoutTree,
  matchUnits,
  reveal,
  unitPath,
} from "./layout";

type Unit = { id: string; parent_id: string | null; name: string; code: string | null };
const unit = (id: string, parent: string | null, name = id): Unit => ({
  id,
  parent_id: parent,
  name,
  code: id.toUpperCase(),
});
const SMALL = [unit("root", null), unit("a", "root"), unit("b", "root"), unit("a1", "a"), unit("a2", "a")];

describe("layoutTree", () => {
  it("centres parents over children and gives leaves consecutive slots", () => {
    const layout = layoutTree(SMALL, new Set());
    const at = (id: string) => layout.nodes.find((node) => node.unit.id === id);
    const step = NODE_WIDTH + GAP_X;
    expect([at("a1")?.x, at("a2")?.x, at("b")?.x]).toEqual([0, step, 2 * step]);
    expect(at("a")?.x).toBe(step / 2);
    expect(at("root")?.x).toBe(1.25 * step);
    expect(layout.edges).toHaveLength(4);
    expect(layout.nodes.every((node) => node.x + NODE_WIDTH <= layout.width)).toBe(true);
  });

  it("lists units in document order, each before its sub-units", () => {
    const order = layoutTree(SMALL, new Set()).nodes.map((node) => node.unit.id);
    expect(order).toEqual(["root", "a", "a1", "a2", "b"]);
  });

  it("hides what lies below a collapsed unit but remembers it has children", () => {
    const layout = layoutTree(SMALL, new Set(["a"]));
    expect(layout.nodes.map((node) => node.unit.id).sort()).toEqual(["a", "b", "root"]);
    expect(layout.nodes.find((node) => node.unit.id === "a")?.hasChildren).toBe(true);
  });

  it("treats a unit whose parent is missing as a top of its own", () => {
    const layout = layoutTree([unit("x", "gone"), unit("y", null)], new Set());
    expect(layout.nodes).toHaveLength(2);
    expect(layout.edges).toHaveLength(0);
  });

  it("is empty for no units", () => {
    expect(layoutTree([], new Set())).toMatchObject({ nodes: [], edges: [] });
  });

  it("lays out 300 units in under 100 ms", () => {
    const units = [unit("u0", null)];
    for (let index = 1; index < 300; index++)
      units.push(unit(`u${index}`, `u${Math.floor((index - 1) / 4)}`));
    const started = performance.now();
    const layout = layoutTree(units, new Set());
    const elapsed = performance.now() - started;
    expect(layout.nodes).toHaveLength(300);
    expect(elapsed).toBeLessThan(100);
  });
});

describe("tree helpers", () => {
  it("finds ancestors nearest first and descendants of any depth", () => {
    expect(ancestorIds(SMALL, "a1")).toEqual(["a", "root"]);
    expect([...descendantIds(SMALL, "root")].sort()).toEqual(["a", "a1", "a2", "b"]);
    expect(descendantIds(SMALL, "b").size).toBe(0);
  });

  it("opens only the ancestors of a revealed unit", () => {
    const collapsed = new Set(["root", "a", "b"]);
    expect([...reveal(collapsed, SMALL, "a1")]).toEqual(["b"]);
  });

  it("matches names and codes ignoring case, and nothing for a blank search", () => {
    const named = [unit("t", null, "Thin Films Section"), unit("c", null, "Corrosion")];
    expect(matchUnits(named, "  thin ").map((item) => item.id)).toEqual(["t"]);
    expect(matchUnits(named, "C").map((item) => item.id)).toEqual(["t", "c"]);
    expect(matchUnits(named, " ")).toEqual([]);
  });

  it("fits the chart to the width without enlarging it", () => {
    expect(fitScale(2000, 1000)).toBe(0.5);
    expect(fitScale(500, 1000)).toBe(1);
    expect(fitScale(100000, 1000)).toBe(0.2);
  });

  it("writes a unit path from the top down", () => {
    expect(unitPath(SMALL, "a1")).toBe("root / a / a1");
  });
});

describe("mixed-depth trees", () => {
  const MIXED = [
    unit("org", null),
    unit("group", "org"),
    unit("div", "group"),
    unit("sec", "div"),
    unit("direct", "group"),
    unit("solo", "org"),
  ];

  it("places a section directly under a group beside a division's sections", () => {
    const layout = layoutTree(MIXED, new Set());
    const at = (id: string) => layout.nodes.find((node) => node.unit.id === id);
    expect([at("div")?.depth, at("direct")?.depth, at("sec")?.depth, at("solo")?.depth]).toEqual([
      2, 2, 3, 1,
    ]);
    expect(layout.nodes.map((node) => node.unit.id)).toEqual([
      "org",
      "group",
      "direct",
      "div",
      "sec",
      "solo",
    ]);
    expect(layout.edges).toHaveLength(5);
    expect(layout.nodes.every((node) => node.x + NODE_WIDTH <= layout.width)).toBe(true);
  });

  it("collapses and reveals at any depth, and finds units by name", () => {
    expect(layoutTree(MIXED, new Set(["div"])).nodes.map((n) => n.unit.id)).not.toContain("sec");
    expect(reveal(new Set(["group", "div"]), MIXED, "sec").size).toBe(0);
    expect(matchUnits(MIXED, "dir").map((u) => u.id)).toEqual(["direct"]);
    expect(unitPath(MIXED, "direct")).toBe("org / group / direct");
  });
});
