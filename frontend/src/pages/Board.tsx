import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorCode, errorMessage, newId, outcomeUnknown } from "../api";
import { API, BASE } from "../config";
import { realtime, type StrokePreview } from "../realtime";
import type { BoardObjectContent, BoardOp, BoardOpPayload, NoteData, Point, Workspace } from "../types";
import { PublishSnapshot } from "../components/PublishSnapshot";
import { ConversationTask } from "../components/ConversationTask";
import { Button, Card, Dialog } from "../ui";
import {
  STICKY_SHAPES,
  STICKY_SIZES,
  STICKY_COLORS,
  PEN_COLORS,
  getStickyDimensions,
  drawStickyCanvas,
  generateShapePoints,
  StickyEditDialog,
  TextEditDialog,
  type StickyShape,
  type StickySize,
  type DrawMode,
  type StickyConfig,
} from "../features/whiteboard";
import "./board-chrome.css";
import { UploadRecovery, useUploadQueue } from "../components/UploadRecovery";
import type { UploadedAsset } from "../uploads";

type Obj = BoardObjectContent & {
  author: string;
  created_at?: string;
  alive: boolean;
  rev: number;
  dx: number;
  dy: number;
};
/** GET /workspaces/{id}/board: replay after a revision, or a reset from the compacted snapshot. */
type BoardState = {
  epoch: number;
  revision: number;
  base_revision: number;
  reset: boolean;
  snapshot: { revision: number; objects: Record<string, Obj> } | null;
  ops: BoardOp[];
  can_write: boolean;
  can_moderate: boolean;
};
type Tool = "select" | "pen" | "eraser" | "text" | "sticky" | "image" | "snapshot" | "pan";
export type Region = { x: number; y: number; w: number; h: number };
type SaveState = "Saved" | "Saving…" | "Reconnecting…" | "Conflict — reloaded" | "Read-only";
type PendingOp = {
  op_id: string;
  epoch: number;
  type: string;
  object_id?: string;
  payload?: BoardOpPayload;
  base_revision?: number;
};

export { STICKY_SHAPES };

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
      if (type === "add") obj.alive = false;
      if (type === "erase") obj.alive = true;
      if (type === "move") Object.assign(obj, { dx: obj.dx - dx, dy: obj.dy - dy });
      obj.rev = op.revision;
    }
  }
  return objects;
}

function bounds(o: Obj): [number, number, number, number] {
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
    w = Math.max(40, o.data.text.length * 9);
    h = 24;
  }
  return [o.data.x + o.dx, o.data.y + o.dy, o.data.x + o.dx + w, o.data.y + o.dy + h];
}

function hit(o: Obj, x: number, y: number, tol: number): boolean {
  if (o.kind !== "stroke") {
    const [a, b, c, d] = bounds(o);
    return x >= a - tol && x <= c + tol && y >= b - tol && y <= d + tol;
  }
  return o.data.points.some((p) => Math.hypot(p[0] + o.dx - x, p[1] + o.dy - y) < tol + o.data.width);
}

/** Whiteboard. With ``panel`` set it runs as a board-only touch panel: no images, publishing or restore. */
export function Board({
  ws,
  userId,
  panel = false,
  onActivity,
  maxUploadBytes = 20 * 1048576,
}: {
  ws: Workspace;
  userId?: string;
  panel?: boolean;
  onActivity?: () => void;
  maxUploadBytes?: number;
}) {
  const [pairing, setPairing] = useState<{ code: string; expires_at: string } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [taskContext, setTaskContext] = useState<{ epoch: number; revision: number } | null>(null);
  const taskFormRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (taskContext) taskFormRef.current?.scrollIntoView({ block: "start" });
  }, [taskContext]);
  const [ops, setOps] = useState<BoardOp[]>([]);
  const [base, setBase] = useState<Record<string, Obj> | null>(null);
  const [selection, setSelection] = useState<Region | null>(null);
  const selecting = useRef<{ x: number; y: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const images = useRef(new Map<string, HTMLImageElement>());
  const [epoch, setEpoch] = useState(1);
  const [tool, setTool] = useState<Tool>("pen");
  const [drawMode, setDrawMode] = useState<DrawMode>("pen");
  const [color, setColor] = useState<string>(PEN_COLORS[0]);
  const [stickyShape, setStickyShape] = useState<StickyShape>("rectangle");
  const [stickySize, setStickySize] = useState<StickySize>("medium");
  const [stickyColor, setStickyColor] = useState<string>(STICKY_COLORS[0]);
  const [editingSticky, setEditingSticky] = useState<{
    id: string;
    obj: Obj & { kind: "sticky"; data: NoteData };
    config: StickyConfig;
  } | null>(null);
  const [creatingStickyAt, setCreatingStickyAt] = useState<Point | null>(null);
  const [editingText, setEditingText] = useState<{
    id: string;
    obj: Obj & { kind: "text"; data: NoteData };
    text: string;
    color: string;
  } | null>(null);
  const [creatingTextAt, setCreatingTextAt] = useState<Point | null>(null);
  const [hoverTooltip, setHoverTooltip] = useState<{
    x: number;
    y: number;
    author: string;
    time: string;
    kind: string;
  } | null>(null);
  const [members, setMembers] = useState<Map<string, string>>(new Map());
  const shapeDrawing = useRef<{ id: string; start: Point; points: Point[] } | null>(null);

  useEffect(() => {
    api<{ id: string; display_name: string }[]>(`/workspaces/${ws.id}/members`)
      .then((list) => {
        const map = new Map<string, string>();
        list.forEach((m) => map.set(m.id, m.display_name));
        setMembers(map);
      })
      .catch(() => undefined);
  }, [ws.id]);
  const [save, setSave] = useState<SaveState>(ws.can_write ? "Saved" : "Read-only");
  const [message, setMessage] = useState<string | null>(null);
  const uploads = useUploadQueue(maxUploadBytes, (asset) => {
    void placeImage(asset);
  });
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [showList, setShowList] = useState(false);
  const [presence, setPresence] = useState<{ id: string; display_name: string }[]>([]);
  const pending = useRef<PendingOp[]>([]);
  const flushing = useRef(false);
  const drawing = useRef<{ id: string; points: Point[]; last: number } | null>(null);
  const panning = useRef<{ x: number; y: number } | null>(null);
  const previews = useRef(new Map<string, StrokePreview>());
  const state = useRef({ revision: 0, epoch: 1 });
  const [, force] = useState(0);
  const objects = fold(ops, base);

  const load = useCallback(
    async (full = false) => {
      const r = await api<BoardState>(`/workspaces/${ws.id}/board`, {
        params: full ? {} : { epoch: state.current.epoch, after: state.current.revision },
      });
      // A reset response starts from the compacted snapshot (if any) plus later operations.
      if (r.reset) setBase(r.snapshot?.objects ?? null);
      setOps((prev) => {
        const kept = r.reset ? [] : prev;
        const known = new Set(kept.map((o) => o.revision));
        const merged = [...kept, ...r.ops.filter((o: BoardOp) => !known.has(o.revision))].sort(
          (a, b) => a.revision - b.revision,
        );
        const floor = r.reset ? (r.snapshot?.revision ?? r.base_revision ?? 0) : state.current.revision;
        state.current = {
          epoch: r.epoch,
          revision: Math.max(floor, merged[merged.length - 1]?.revision ?? floor),
        };
        return merged;
      });
      setEpoch(r.epoch);
    },
    [ws.id],
  );

  const apply = useCallback(
    (op: BoardOp) => {
      previews.current.delete(op.object_id);
      setOps((prev) => {
        if (op.epoch !== state.current.epoch || prev.some((o) => o.revision === op.revision)) return prev;
        const next = [...prev, op].sort((a, b) => a.revision - b.revision);
        const expected = state.current.revision + 1;
        state.current.revision = Math.max(state.current.revision, op.revision);
        if (op.revision !== expected) window.setTimeout(() => load(), 0); // gap: replay missed ops
        return next;
      });
    },
    [load],
  );

  const flush = useCallback(async () => {
    if (flushing.current) return;
    flushing.current = true;
    try {
      while (pending.current.length) {
        setSave("Saving…");
        const op = pending.current[0];
        try {
          const r = await api<{ committed: BoardOp; duplicate: boolean }>(`/workspaces/${ws.id}/board/ops`, {
            body: op,
          });
          apply(r.committed);
          pending.current.shift();
        } catch (e: unknown) {
          if (outcomeUnknown(e)) {
            setSave("Reconnecting…");
            return; // keep pending ops; resend with the same IDs later
          }
          pending.current.shift();
          if (errorCode(e) === "stale_epoch") pending.current = [];
          setSave("Conflict — reloaded");
          setMessage(errorMessage(e));
          await load(true);
          return;
        }
      }
      setSave("Saved");
    } finally {
      flushing.current = false;
    }
  }, [ws.id, apply, load]);

  const submit = (op: Omit<PendingOp, "op_id" | "epoch">) => {
    pending.current.push({ op_id: newId("op"), epoch: state.current.epoch, ...op });
    void flush();
  };

  useEffect(() => {
    load(true).catch((e) => setMessage(errorMessage(e)));
    const retry = window.setInterval(() => pending.current.length && flush(), 3000);
    const unsub = realtime.subscribe(ws.id, (ev) => {
      if (ev.type === "board.op") apply(ev.op);
      else if (ev.type === "board.epoch") {
        pending.current = [];
        setMessage("A steward restored the board. Your view was refreshed.");
        load(true).catch((e) => setMessage(errorMessage(e)));
      } else if (ev.type === "board.preview") {
        if (ev.done) previews.current.delete(ev.preview_id);
        else if (ev.stroke) previews.current.set(ev.preview_id, ev.stroke);
        force((n) => n + 1);
      } else if (ev.type === "presence") setPresence(ev.users);
      else if (ev.type === "subscribed") {
        previews.current.clear(); // disconnect discards uncommitted remote previews
        load()
          .then(flush)
          .catch((e) => setMessage(errorMessage(e)));
      }
    });
    return () => {
      unsub();
      window.clearInterval(retry);
    };
  }, [ws.id, load, apply, flush]);

  // ---- rendering ----------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    const ctx = canvas.getContext("2d")!;
    ctx.setTransform(ratio * view.scale, 0, 0, ratio * view.scale, ratio * view.x, ratio * view.y);
    ctx.clearRect(
      -view.x / view.scale,
      -view.y / view.scale,
      rect.width / view.scale,
      rect.height / view.scale,
    );
    const line = (pts: Point[], c: string, w: number, dx = 0, dy = 0) => {
      ctx.strokeStyle = c;
      ctx.lineWidth = w;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      pts.forEach((p, i) => (i ? ctx.lineTo(p[0] + dx, p[1] + dy) : ctx.moveTo(p[0] + dx, p[1] + dy)));
      const [only] = pts;
      if (pts.length === 1 && only) ctx.lineTo(only[0] + dx + 0.1, only[1] + dy);
      ctx.stroke();
    };
    for (const o of [...objects.values()].sort((a, b) => a.rev - b.rev)) {
      if (!o.alive) continue;
      if (o.kind === "image") {
        const id = o.data.asset_id;
        let img = images.current.get(id);
        if (!img) {
          img = new Image();
          img.onload = () => force((n) => n + 1);
          img.src = `${API}/files/${id}/preview${panel ? "?panel=1" : ""}`;
          images.current.set(id, img);
        }
        if (img.complete && img.naturalWidth)
          ctx.drawImage(img, o.data.x + o.dx, o.data.y + o.dy, o.data.w, o.data.h);
        else {
          ctx.strokeStyle = "#9aa5b1";
          ctx.strokeRect(o.data.x + o.dx, o.data.y + o.dy, o.data.w, o.data.h);
        }
      } else if (o.kind === "stroke") line(o.data.points, o.data.color, o.data.width, o.dx, o.dy);
      else {
        const x = o.data.x + o.dx,
          y = o.data.y + o.dy;
        if (o.kind === "sticky") {
          const shape = o.data.shape ?? "rectangle";
          const [w, h] = getStickyDimensions(shape, o.data.size);
          drawStickyCanvas(ctx, x, y, w, h, shape, o.data.color, o.data.text);
        } else {
          ctx.fillStyle = o.data.color;
          ctx.font = "16px system-ui, sans-serif";
          ctx.textAlign = "left";
          const lines = o.data.text.split("\n");
          lines.forEach((t: string, i: number) => ctx.fillText(t, x, y + 20 + i * 20));
        }
      }
    }
    if (shapeDrawing.current) {
      line(shapeDrawing.current.points, color, 3);
    }
    for (const p of previews.current.values()) line(p.points, p.color ?? "#999", 3);
    if (drawing.current) line(drawing.current.points, color, 3);
    if (selection) {
      ctx.setLineDash([8 / view.scale, 6 / view.scale]);
      ctx.strokeStyle = "#1d4ed8";
      ctx.lineWidth = 2 / view.scale;
      ctx.strokeRect(selection.x, selection.y, selection.w, selection.h);
      ctx.setLineDash([]);
    }
  });

  const toWorld = (e: React.PointerEvent): Point => {
    const r = canvasRef.current!.getBoundingClientRect();
    return [(e.clientX - r.left - view.x) / view.scale, (e.clientY - r.top - view.y) / view.scale];
  };

  function onDown(e: React.PointerEvent) {
    const [x, y] = toWorld(e);
    if (tool === "pan" || e.button === 1) {
      panning.current = { x: e.clientX - view.x, y: e.clientY - view.y };
      return;
    }
    if (tool === "snapshot") {
      (e.target as Element).setPointerCapture(e.pointerId);
      selecting.current = { x, y };
      setSelection({ x, y, w: 0, h: 0 });
      return;
    }
    if (!ws.can_write) return;
    if (tool === "image") return;
    if (tool === "select" || tool === "sticky" || tool === "text") {
      const target = [...objects.entries()]
        .reverse()
        .find(([, o]) => o.alive && hit(o, x, y, 6 / view.scale));
      if (target) {
        const [targetId, targetObj] = target;
        if (targetObj.kind === "sticky") {
          setEditingSticky({
            id: targetId,
            obj: targetObj as Obj & { kind: "sticky"; data: NoteData },
            config: {
              text: targetObj.data.text,
              shape: targetObj.data.shape ?? "rectangle",
              size: targetObj.data.size ?? "medium",
              color: targetObj.data.color,
            },
          });
          return;
        }
        if (targetObj.kind === "text") {
          setEditingText({
            id: targetId,
            obj: targetObj as Obj & { kind: "text"; data: NoteData },
            text: targetObj.data.text,
            color: targetObj.data.color,
          });
          return;
        }
      }
      if (tool === "sticky") {
        setCreatingStickyAt([x, y]);
        return;
      }
      if (tool === "text") {
        setCreatingTextAt([x, y]);
        return;
      }
    } else if (tool === "pen") {
      (e.target as Element).setPointerCapture(e.pointerId);
      if (["line", "arrow", "rect", "circle"].includes(drawMode)) {
        shapeDrawing.current = {
          id: newId("s"),
          start: [x, y],
          points: [
            [x, y],
            [x, y],
          ],
        };
      } else {
        drawing.current = { id: newId("s"), points: [[x, y]], last: 0 };
      }
    } else if (tool === "eraser") {
      const target = [...objects.entries()]
        .reverse()
        .find(([, o]) => o.alive && hit(o, x, y, 8 / view.scale));
      if (target) submit({ type: "erase", object_id: target[0] });
    }
  }

  function onMove(e: React.PointerEvent) {
    if (panning.current) {
      setView((v) => ({ ...v, x: e.clientX - panning.current!.x, y: e.clientY - panning.current!.y }));
      return;
    }
    if (selecting.current) {
      const [x, y] = toWorld(e);
      const s0 = selecting.current;
      setSelection({
        x: Math.min(s0.x, x),
        y: Math.min(s0.y, y),
        w: Math.abs(x - s0.x),
        h: Math.abs(y - s0.y),
      });
      return;
    }
    if (shapeDrawing.current) {
      const [x, y] = toWorld(e);
      shapeDrawing.current.points = generateShapePoints(drawMode, shapeDrawing.current.start, [x, y]);
      force((n) => n + 1);
      return;
    }
    const d = drawing.current;
    if (d) {
      const [x, y] = toWorld(e);
      d.points.push([Math.round(x * 10) / 10, Math.round(y * 10) / 10]);
      if (d.points.length > 3900) return onUp();
      const now = performance.now();
      if (now - d.last > 60) {
        d.last = now;
        realtime.send({
          type: "board.preview",
          workspace_id: ws.id,
          preview_id: d.id,
          stroke: { points: d.points.slice(-400), color },
        });
      }
      force((n) => n + 1);
      return;
    }

    const [wx, wy] = toWorld(e);
    const hitObj = [...objects.entries()]
      .reverse()
      .find(([, o]) => o.alive && hit(o, wx, wy, 6 / view.scale));
    if (hitObj) {
      const [, o] = hitObj;
      const authorName =
        o.author === userId
          ? "You"
          : (members.get(o.author) ?? presence.find((p) => p.id === o.author)?.display_name ?? "Team member");
      const timeStr = o.created_at
        ? new Date(o.created_at).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "Saved revision";
      const kindLabel =
        o.kind === "sticky"
          ? `${(o.data.shape ?? "Rectangle").toUpperCase()} note (${o.data.size ?? "medium"})`
          : o.kind === "stroke"
            ? "Drawing stroke"
            : o.kind === "text"
              ? "Text label"
              : "Image";
      setHoverTooltip({
        x: e.clientX + 14,
        y: e.clientY + 14,
        author: authorName,
        time: timeStr,
        kind: kindLabel,
      });
    } else {
      setHoverTooltip(null);
    }
  }

  function onUp() {
    panning.current = null;
    if (selecting.current) {
      selecting.current = null;
      setSelection((sel) => (sel && sel.w > 4 && sel.h > 4 ? sel : null));
      return;
    }
    if (shapeDrawing.current) {
      const sd = shapeDrawing.current;
      shapeDrawing.current = null;
      if (sd.points.length >= 2) {
        submit({
          type: "add",
          object_id: sd.id,
          payload: { kind: "stroke", data: { points: sd.points, color, width: 3 } },
        });
      }
      return;
    }
    const d = drawing.current;
    drawing.current = null;
    if (!d) return;
    const strokeW = drawMode === "pencil" ? 1.5 : drawMode === "brush" ? 8 : 3;
    realtime.send({ type: "board.preview", workspace_id: ws.id, preview_id: d.id, done: true });
    submit({
      type: "add",
      object_id: d.id,
      payload: { kind: "stroke", data: { points: d.points, color, width: strokeW } },
    });
  }

  function fit() {
    const live = [...objects.values()].filter((o) => o.alive);
    const canvas = canvasRef.current;
    if (!live.length || !canvas) return setView({ x: 0, y: 0, scale: 1 });
    const bs = live.map(bounds);
    const [a, b, c, d] = [
      Math.min(...bs.map((q) => q[0])),
      Math.min(...bs.map((q) => q[1])),
      Math.max(...bs.map((q) => q[2])),
      Math.max(...bs.map((q) => q[3])),
    ];
    const r = canvas.getBoundingClientRect();
    const scale = Math.min(4, Math.max(0.1, Math.min(r.width / (c - a + 80), r.height / (d - b + 80))));
    setView({ scale, x: -a * scale + 40, y: -b * scale + 40 });
  }

  async function placeImage(asset: UploadedAsset) {
    try {
      const probe = new Image();
      probe.src = asset.preview_url ?? asset.url;
      await probe.decode().catch(() => undefined);
      const ratio =
        probe.naturalWidth && probe.naturalHeight ? probe.naturalHeight / probe.naturalWidth : 0.75;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const r = canvas.getBoundingClientRect();
      const w = Math.min(320, (r.width / view.scale) * 0.5);
      const cx = (r.width / 2 - view.x) / view.scale,
        cy = (r.height / 2 - view.y) / view.scale;
      submit({
        type: "add",
        object_id: newId("i"),
        payload: {
          kind: "image",
          data: {
            x: Math.round(cx - w / 2),
            y: Math.round(cy - (w * ratio) / 2),
            w: Math.round(w),
            h: Math.round(w * ratio),
            asset_id: asset.id,
          },
        },
      });
    } catch (e: unknown) {
      setMessage(errorMessage(e));
    }
  }

  async function openOnPanel() {
    try {
      setPairing(await api("/panel/pairings", { body: { workspace_id: ws.id } }));
    } catch (e: unknown) {
      setMessage(errorMessage(e));
    }
  }

  async function restore() {
    const answer = window.prompt("Restore the board to which revision? (0 clears the board)", "0");
    if (answer === null) return;
    try {
      await api(`/workspaces/${ws.id}/board/restore`, {
        body: { revision: Number(answer), reason: "Restored from board view" },
      });
      await load(true);
    } catch (e: unknown) {
      setMessage(errorMessage(e));
    }
  }

  const mine = ops.some((o) => o.actor_id === userId && o.type !== "undo");
  const typed = [...objects.entries()].filter(
    (entry): entry is [string, Obj & { kind: "text" | "sticky" }] =>
      entry[1].alive && (entry[1].kind === "text" || entry[1].kind === "sticky"),
  );
  const imageCount = [...objects.values()].filter((o) => o.alive && o.kind === "image").length;

  return (
    <>
      <section
        className={"whiteboard" + (panel ? " panel-board" : "")}
        aria-label={`Whiteboard for ${ws.name}`}
        onPointerDownCapture={() => onActivity?.()}
      >
        <Dialog
          open={pairing !== null}
          title="Open this board on a touch panel"
          onClose={() => setPairing(null)}
          size="sm"
          footer={
            <Button variant="primary" onClick={() => setPairing(null)}>
              Done
            </Button>
          }
        >
          {pairing && (
            <div className="board-dialog">
              <p>
                On the panel, open{" "}
                <strong>
                  {window.location.origin}
                  {BASE}/panel
                </strong>{" "}
                and enter:
              </p>
              <p className="pair-code" aria-label="Pairing code">
                {pairing.code}
              </p>
              <p className="board-dialog__muted">
                Single use. Expires at {new Date(pairing.expires_at).toLocaleTimeString()}. The panel can use
                only this board, as you, and locks when idle.
              </p>
            </div>
          )}
        </Dialog>
        <div className="toolbar" role="toolbar" aria-label="Drawing tools">
          {(["select", "pen", "eraser", "text", "sticky", "pan"] as Tool[]).map((t) => (
            <button
              key={t}
              className={"tool" + (tool === t ? " active" : "")}
              aria-pressed={tool === t}
              onClick={() => setTool(t)}
              disabled={!ws.can_write && t !== "pan"}
            >
              {t === "select"
                ? "↖ Select"
                : t === "pen"
                  ? "✏️ Draw"
                  : t === "eraser"
                    ? "🧽 Eraser"
                    : t === "text"
                      ? "🔤 Text"
                      : t === "sticky"
                        ? "🗒 Sticky"
                        : "✋ Pan"}
            </button>
          ))}
          {tool === "pen" && (
            <span className="tool-group" role="radiogroup" aria-label="Drawing tools">
              {(
                [
                  { id: "pen", label: "Pen", icon: "✏️" },
                  { id: "pencil", label: "Pencil", icon: "✎" },
                  { id: "brush", label: "Marker", icon: "🖌️" },
                  { id: "line", label: "Line", icon: "╱" },
                  { id: "arrow", label: "Arrow", icon: "→" },
                  { id: "rect", label: "Box", icon: "▭" },
                  { id: "circle", label: "Circle", icon: "◯" },
                ] as { id: DrawMode; label: string; icon: string }[]
              ).map((m) => (
                <button
                  key={m.id}
                  role="radio"
                  aria-checked={drawMode === m.id}
                  className={"tool tool--sub" + (drawMode === m.id ? " active" : "")}
                  onClick={() => setDrawMode(m.id)}
                  title={m.label}
                >
                  {m.icon} {m.label}
                </button>
              ))}
            </span>
          )}
          {!panel && (
            <>
              <button
                className="tool"
                onClick={() => fileRef.current?.click()}
                disabled={!ws.can_write || uploads.attempts.length > 0}
              >
                🖼 Image
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg"
                hidden
                aria-label="Image to place on the board"
                onChange={(e) => {
                  try {
                    uploads.queue.add(Array.from(e.target.files ?? []), 1);
                  } catch (error: unknown) {
                    setMessage(errorMessage(error));
                  }
                  e.target.value = "";
                }}
              />
              <button
                className={"tool" + (tool === "snapshot" ? " active" : "")}
                aria-pressed={tool === "snapshot"}
                onClick={() => {
                  setTool("snapshot");
                  setSelection(null);
                }}
              >
                📷 Publish snapshot
              </button>
            </>
          )}
          {tool === "sticky" && (
            <>
              <span className="tool-group" role="radiogroup" aria-label="Sticky note shape">
                {STICKY_SHAPES.map((s) => (
                  <button
                    key={s.id}
                    role="radio"
                    aria-checked={stickyShape === s.id}
                    aria-label={`${s.label} shape`}
                    className={"tool tool--sub tool--shape" + (stickyShape === s.id ? " active" : "")}
                    onClick={() => setStickyShape(s.id)}
                    title={`${s.label} sticky note`}
                  >
                    {s.icon} {s.label}
                  </button>
                ))}
              </span>
              <span className="tool-group" role="radiogroup" aria-label="Sticky note size">
                {STICKY_SIZES.map((sz) => (
                  <button
                    key={sz.id}
                    role="radio"
                    aria-checked={stickySize === sz.id}
                    aria-label={`${sz.label} size`}
                    className={"tool tool--sub" + (stickySize === sz.id ? " active" : "")}
                    onClick={() => setStickySize(sz.id)}
                    title={`${sz.label} size`}
                  >
                    {sz.label[0]}
                  </button>
                ))}
              </span>
            </>
          )}
          <span className="swatches" role="radiogroup" aria-label="Colour">
            {(tool === "sticky" ? STICKY_COLORS : PEN_COLORS).map((c) => (
              <button
                key={c}
                role="radio"
                aria-checked={(tool === "sticky" ? stickyColor : color) === c}
                aria-label={`Colour ${c}`}
                className={"swatch" + ((tool === "sticky" ? stickyColor : color) === c ? " active" : "")}
                style={{ background: c }}
                onClick={() => (tool === "sticky" ? setStickyColor(c) : setColor(c))}
              />
            ))}
          </span>
          <button className="tool" onClick={() => submit({ type: "undo" })} disabled={!ws.can_write || !mine}>
            ↶ Undo mine
          </button>
          <button
            className="tool"
            onClick={() => setView((v) => ({ ...v, scale: Math.min(4, v.scale * 1.25) }))}
            aria-label="Zoom in"
          >
            ＋
          </button>
          <button
            className="tool"
            onClick={() => setView((v) => ({ ...v, scale: Math.max(0.1, v.scale / 1.25) }))}
            aria-label="Zoom out"
          >
            －
          </button>
          <button className="tool" onClick={fit}>
            Fit
          </button>
          <button className="tool" onClick={() => setShowList((v) => !v)} aria-expanded={showList}>
            List view
          </button>
          {!panel && ws.can_moderate && ws.can_write && (
            <button className="tool" onClick={restore}>
              Restore…
            </button>
          )}
          {!panel && (
            <button
              className="tool"
              disabled={state.current.revision === 0 || save === "Saving…" || save === "Reconnecting…"}
              title="Add research-plan content before creating a task reference"
              onClick={() => setTaskContext({ ...state.current })}
            >
              Create task from board
            </button>
          )}
          {!panel && (
            <button className="tool" onClick={openOnPanel}>
              📺 Open on touch panel
            </button>
          )}
          <span className={"save-state" + (save === "Saved" ? " ok" : "")} role="status">
            {save}
          </span>
          <span className="board-meta">
            Epoch {epoch} · rev {state.current.revision} · {presence.length} here:{" "}
            {presence.map((p) => p.display_name).join(", ")}
          </span>
        </div>
        {tool === "snapshot" && !selection && (
          <p className="board-notice">Drag on the board to select the region to publish.</p>
        )}
        {selection && tool === "snapshot" && (
          <PublishSnapshot
            ws={ws}
            region={selection}
            revision={state.current.revision}
            onClose={(done) => {
              setSelection(null);
              if (done) setTool("pen");
            }}
          />
        )}
        {message && (
          <p className="board-notice" role="alert">
            {message}{" "}
            <Button variant="quiet" size="sm" onClick={() => setMessage(null)}>
              Dismiss
            </Button>
          </p>
        )}
        {!panel && <UploadRecovery queue={uploads.queue} />}
        <canvas
          ref={canvasRef}
          className={`canvas tool-${tool}`}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          onWheel={(e) =>
            setView((v) => ({
              ...v,
              scale: Math.min(4, Math.max(0.1, v.scale * (e.deltaY < 0 ? 1.1 : 0.9))),
            }))
          }
          aria-label="Drawing canvas. Use the list view for a text alternative."
          role="img"
        />
        {showList && (
          <div className="board-list">
            <Card title="Board items">
              <div className="board-dialog">
                <p className="board-dialog__muted">
                  {[...objects.values()].filter((o) => o.alive && o.kind === "stroke").length} drawn strokes ·{" "}
                  {imageCount} images
                </p>
                {typed.length === 0 ? (
                  <p className="board-dialog__muted">No text or sticky notes.</p>
                ) : (
                  <ul className="board-dialog__items">
                    {typed.map(([id, o]) => (
                      <li key={id}>
                        {o.kind === "sticky" ? "Sticky" : "Text"}: {o.data.text}
                        {ws.can_write && (
                          <Button
                            variant="quiet"
                            size="sm"
                            onClick={() => submit({ type: "erase", object_id: id })}
                          >
                            Erase
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
          </div>
        )}
        {hoverTooltip && (
          <div className="board-tooltip" style={{ left: hoverTooltip.x, top: hoverTooltip.y }}>
            <span className="board-tooltip__author">{hoverTooltip.author}</span>
            <span className="board-tooltip__meta">
              {hoverTooltip.time} · {hoverTooltip.kind}
            </span>
          </div>
        )}
        {editingSticky && (
          <StickyEditDialog
            open={true}
            title="Edit sticky note"
            initialConfig={editingSticky.config}
            authorInfo={{
              name:
                editingSticky.obj.author === userId
                  ? "You"
                  : (members.get(editingSticky.obj.author) ?? "Team member"),
              time: editingSticky.obj.created_at
                ? new Date(editingSticky.obj.created_at).toLocaleString()
                : "Saved revision",
            }}
            onClose={() => setEditingSticky(null)}
            onSave={(cfg) => {
              submit({ type: "erase", object_id: editingSticky.id });
              submit({
                type: "add",
                object_id: newId("s"),
                payload: {
                  kind: "sticky",
                  data: {
                    x: editingSticky.obj.data.x + editingSticky.obj.dx,
                    y: editingSticky.obj.data.y + editingSticky.obj.dy,
                    text: cfg.text,
                    shape: cfg.shape,
                    size: cfg.size,
                    color: cfg.color,
                  },
                },
              });
            }}
            onDelete={() => {
              submit({ type: "erase", object_id: editingSticky.id });
              setEditingSticky(null);
            }}
          />
        )}
        {creatingStickyAt && (
          <StickyEditDialog
            open={true}
            title="Add sticky note"
            initialConfig={{
              text: "",
              shape: stickyShape,
              size: stickySize,
              color: stickyColor,
            }}
            onClose={() => setCreatingStickyAt(null)}
            onSave={(cfg) => {
              submit({
                type: "add",
                object_id: newId("s"),
                payload: {
                  kind: "sticky",
                  data: {
                    x: creatingStickyAt[0],
                    y: creatingStickyAt[1],
                    text: cfg.text,
                    shape: cfg.shape,
                    size: cfg.size,
                    color: cfg.color,
                  },
                },
              });
            }}
          />
        )}
        {editingText && (
          <TextEditDialog
            open={true}
            initialText={editingText.text}
            initialColor={editingText.color}
            authorInfo={{
              name:
                editingText.obj.author === userId
                  ? "You"
                  : (members.get(editingText.obj.author) ?? "Team member"),
              time: editingText.obj.created_at
                ? new Date(editingText.obj.created_at).toLocaleString()
                : "Saved revision",
            }}
            onClose={() => setEditingText(null)}
            onSave={(t, c) => {
              submit({ type: "erase", object_id: editingText.id });
              submit({
                type: "add",
                object_id: newId("t"),
                payload: {
                  kind: "text",
                  data: {
                    x: editingText.obj.data.x + editingText.obj.dx,
                    y: editingText.obj.data.y + editingText.obj.dy,
                    text: t,
                    color: c,
                  },
                },
              });
            }}
            onDelete={() => {
              submit({ type: "erase", object_id: editingText.id });
              setEditingText(null);
            }}
          />
        )}
        {creatingTextAt && (
          <TextEditDialog
            open={true}
            initialColor={color}
            onClose={() => setCreatingTextAt(null)}
            onSave={(t, c) => {
              submit({
                type: "add",
                object_id: newId("t"),
                payload: {
                  kind: "text",
                  data: {
                    x: creatingTextAt[0],
                    y: creatingTextAt[1],
                    text: t,
                    color: c,
                  },
                },
              });
            }}
          />
        )}
      </section>
      {!panel && taskContext && (
        <div ref={taskFormRef}>
          <ConversationTask
            source={ws}
            kind="board"
            boardContext={taskContext}
            text="Research plan followup"
            close={() => setTaskContext(null)}
          />
        </div>
      )}
    </>
  );
}
