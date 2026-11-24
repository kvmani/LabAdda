import type { BoardObjectContent, BoardOp, BoardOpPayload } from "../../types";
import { getStickyDimensions } from "./shapes";
import type { StickyShape, StickySize } from "./types";

/** A board object as drawn: its content plus author, liveness and accumulated movement. */
export type Obj = BoardObjectContent & {
  author: string;
  created_at?: string;
  alive: boolean;
  rev: number;
  dx: number;
  dy: number;
};
/** GET /workspaces/{id}/board: replay after a revision, or a reset from the compacted snapshot. */
export type BoardState = {
  epoch: number;
  revision: number;
  base_revision: number;
  reset: boolean;
  snapshot: { revision: number; objects: Record<string, Obj> } | null;
  ops: BoardOp[];
  can_write: boolean;
  can_moderate: boolean;
};
export type Tool = "select" | "pen" | "eraser" | "text" | "sticky" | "image" | "snapshot" | "pan";
export type Region = { x: number; y: number; w: number; h: number };
export type SaveState = "Saved" | "Saving…" | "Reconnecting…" | "Conflict — reloaded" | "Read-only";
export type PendingOp = {
  op_id: string;
  epoch: number;
  type: string;
  object_id?: string;
  payload?: BoardOpPayload;
  base_revision?: number;
};

export function stickyDimensions(shape?: string, size?: string): [number, number] {
  return getStickyDimensions(shape as StickyShape, size as StickySize);
}

export function fold(ops: BoardOp[], base?: Record<string, Obj> | null): Map<string, Obj> {
  const objects = new Map<string, Obj>(Object.entries(base ?? {}).map(([k, v]) => [k, { ...v }]));
  const byRev = new Map<number, BoardOp>();
  for (const op of ops) {
    byRev.set(op.revision, op);
    const obj = objects.get(op.object_id);
    if (op.type === "add") {
      const { kind, data } = op.payload;
      if (!kind || !data) continue; // the server never commits an add without both
      // The server validated `data` against `kind` before committing the operation.
      const content = { kind, data } as BoardObjectContent;
      objects.set(op.object_id, {
        ...content,
        author: op.payload.author ?? op.actor_id,
        created_at: op.created_at,
        alive: true,
        rev: op.revision,
        dx: 0,
        dy: 0,
      });
    } else if (!obj) continue;
    else if (op.type === "update") Object.assign(obj, { data: op.payload.data, rev: op.revision });
    else if (op.type === "erase") Object.assign(obj, { alive: false, rev: op.revision });
    else if (op.type === "move")
      Object.assign(obj, {
        dx: obj.dx + (op.payload.dx ?? 0),
        dy: obj.dy + (op.payload.dy ?? 0),
        rev: op.revision,
      });
    else if (op.type === "undo") {
      // Undo payloads carry their effect, so they still apply after the target was compacted.
      const target = op.payload.target_revision;
      const t = target === undefined ? undefined : byRev.get(target);
      const type = op.payload.target_type ?? t?.type;
      const dx = op.payload.dx ?? t?.payload.dx ?? 0;
      const dy = op.payload.dy ?? t?.payload.dy ?? 0;
      if (!type) continue;
      if (type === "update") obj.data = op.payload.previous_data ?? obj.data;
      if (type === "add") obj.alive = false;
      if (type === "erase") obj.alive = true;
      if (type === "move") Object.assign(obj, { dx: obj.dx - dx, dy: obj.dy - dy });
      obj.rev = op.revision;
    }
  }
  return objects;
}

/** World-space box of an object: [left, top, right, bottom]. */
export function bounds(o: Obj): [number, number, number, number] {
  if (o.kind === "stroke") {
    const xs = o.data.points.map((p) => p[0] + o.dx);
    const ys = o.data.points.map((p) => p[1] + o.dy);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  if (o.kind === "image")
    return [o.data.x + o.dx, o.data.y + o.dy, o.data.x + o.dx + o.data.w, o.data.y + o.dy + o.data.h];
  let w = 180;
  let h = 120;
  if (o.kind === "sticky") {
    [w, h] = getStickyDimensions(o.data.shape, o.data.size);
  } else {
    const fontSize = o.data.font_size ?? 16;
    const lines = o.data.text.split("\n");
    w = Math.max(40, ...lines.map((line) => line.length * fontSize * 0.65));
    h = Math.max(24, lines.length * fontSize * 1.3);
  }
  return [o.data.x + o.dx, o.data.y + o.dy, o.data.x + o.dx + w, o.data.y + o.dy + h];
}

/** Whether a point is on an object, with a tolerance in world units. */
export function hit(o: Obj, x: number, y: number, tol: number): boolean {
  if (o.kind !== "stroke") {
    const [a, b, c, d] = bounds(o);
    return x >= a - tol && x <= c + tol && y >= b - tol && y <= d + tol;
  }
  return o.data.points.some((p) => Math.hypot(p[0] + o.dx - x, p[1] + o.dy - y) < tol + o.data.width);
}
