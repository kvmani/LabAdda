import { describe, expect, it } from "vitest";
import { moveObject } from "./move";
import type { BoardObject } from "./types";

describe("moving private board objects", () => {
  it("moves a drawing as one shape and leaves the original unchanged", () => {
    const original: BoardObject = {
      id: "stroke",
      kind: "stroke",
      color: "#1565c0",
      points: [
        [20, 30],
        [70, 90],
      ],
    };
    const result = moveObject(original, 15, -10);
    expect(result.points).toEqual([
      [35, 20],
      [85, 80],
    ]);
    expect(original.points).toEqual([
      [20, 30],
      [70, 90],
    ]);
  });
  it("keeps the complete drawing inside the board instead of clipping individual points", () => {
    const original: BoardObject = {
      id: "stroke",
      kind: "stroke",
      color: "#1565c0",
      points: [
        [900, 500],
        [990, 590],
      ],
    };
    const result = moveObject(original, 100, 100);
    expect(result.points).toEqual([
      [910, 510],
      [1000, 600],
    ]);
  });
  it("moves a note with its formatting and author intact", () => {
    const original: BoardObject = {
      id: "note",
      kind: "sticky",
      color: "#fff59d",
      x: 5,
      y: 5,
      text: "Materials discussion",
      font_family: "handwritten",
      font_size: 24,
      author: "Asha Rao",
    };
    const result = moveObject(original, -10, 15);
    expect(result.x).toBe(0);
    expect(result.y).toBe(20);
    expect(result.text).toBe(original.text);
    expect(result.font_family).toBe("handwritten");
    expect(result.font_size).toBe(24);
    expect(result.author).toBe("Asha Rao");
  });
});
