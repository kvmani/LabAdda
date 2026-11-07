import { describe, expect, it } from "vitest";
import { fold } from "./pages/Board";
import { treeOrder } from "./workspaces";
import type { BoardOp, Workspace } from "./types";

const op = (revision: number, type: string, object_id: string, payload: any = {}, actor_id = "u1"): BoardOp => ({ revision, epoch: 1, op_id: `op${revision}`, actor_id, type, object_id, payload });

describe("board fold", () => {
  it("applies add, erase, undo and move like the server", () => {
    const add = { kind: "sticky", data: { x: 0, y: 0, text: "hi", color: "#fff59d" } };
    const objs = fold([op(1, "add", "a", add), op(2, "move", "a", { dx: 5, dy: 5 }), op(3, "erase", "a", {}, "u2"), op(4, "undo", "a", { target_revision: 3 }, "u2"), op(5, "undo", "a", { target_revision: 2 })]);
    const a = objs.get("a")!;
    expect(a.alive).toBe(true);
    expect([a.dx, a.dy]).toEqual([0, 0]);
  });
});

describe("workspace tree order", () => {
  const ws = (id: string, parent: string | null, name: string): Workspace => ({ id, parent_id: parent, name, kind: "org", description: "", archived: false, posting_policy: "open", role: null, inherited: true, can_write: true, can_moderate: false, unread_chat: 0 });
  it("indents children under parents and treats unreadable parents as roots", () => {
    const out = treeOrder([ws("c", "b", "Section"), ws("b", "a", "Division"), ws("a", null, "Root"), ws("x", "hidden", "Orphan")]);
    expect(out.map((o) => [o.ws.name, o.depth])).toEqual([["Orphan", 0], ["Root", 0], ["Division", 1], ["Section", 2]]);
  });
});
