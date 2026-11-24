import { describe, expect, it } from "vitest";
import type { BoardOp, BoardOpPayload } from "../../types";
import { bounds, fold, hit, type Obj } from "./boardModel";

const op = (revision: number, type: string, payload: BoardOpPayload = {}): BoardOp => ({
  revision,
  epoch: 1,
  op_id: `op${revision}`,
  actor_id: "u1",
  type,
  object_id: "a",
  payload,
});

const stroke = (): Obj =>
  fold([
    op(1, "add", {
      kind: "stroke",
      data: {
        points: [
          [0, 0],
          [100, 50],
        ],
        color: "#000",
        width: 2,
      },
    }),
  ]).get("a")!;

describe("board model", () => {
  it("keeps the author from the payload and replays updates and moves in order", () => {
    const objects = fold([
      op(1, "add", { kind: "text", data: { x: 10, y: 10, text: "a", color: "#000" }, author: "u9" }),
      op(2, "update", { data: { x: 10, y: 10, text: "b", color: "#000" } }),
      op(3, "move", { dx: 5, dy: -5 }),
    ]);
    const text = objects.get("a")!;
    expect(text.author).toBe("u9");
    expect(text.kind === "text" && text.data.text).toBe("b");
    expect([text.dx, text.dy, text.rev]).toEqual([5, -5, 3]);
  });

  it("ignores operations on unknown objects and adds without content", () => {
    expect(fold([op(1, "move", { dx: 1 }), op(2, "add", {})]).size).toBe(0);
  });

  it("undoes an update back to the recorded previous data", () => {
    const before = { x: 0, y: 0, text: "first", color: "#fff59d" };
    const objects = fold([
      op(1, "add", { kind: "sticky", data: before }),
      op(2, "update", { data: { ...before, text: "second" } }),
      op(3, "undo", { target_revision: 2, previous_data: before }),
    ]);
    const sticky = objects.get("a")!;
    expect(sticky.kind === "sticky" && sticky.data.text).toBe("first");
  });

  it("measures and hits strokes by their moved points", () => {
    const line = { ...stroke(), dx: 10, dy: 10 };
    expect(bounds(line)).toEqual([10, 10, 110, 60]);
    expect(hit(line, 10, 10, 1)).toBe(true);
    expect(hit(line, 0, 0, 1)).toBe(false);
  });

  it("hits notes anywhere inside their box, with tolerance", () => {
    const note = fold([
      op(1, "add", { kind: "sticky", data: { x: 0, y: 0, text: "n", color: "#fff59d" } }),
    ]).get("a")!;
    const [, , right, bottom] = bounds(note);
    expect(hit(note, right / 2, bottom / 2, 0)).toBe(true);
    expect(hit(note, right + 5, bottom, 6)).toBe(true);
    expect(hit(note, right + 20, bottom, 6)).toBe(false);
  });
});
