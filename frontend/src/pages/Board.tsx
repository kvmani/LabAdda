import { useCallback, useEffect, useRef, useState } from "react";
import { api, newId } from "../api";
import { realtime } from "../realtime";
import { useSession } from "../session";
import type { BoardOp, Workspace } from "../types";

type Obj = { kind: "stroke" | "text" | "sticky"; data: any; author: string; alive: boolean; rev: number; dx: number; dy: number };
type Tool = "pen" | "eraser" | "text" | "sticky" | "pan";
type SaveState = "Saved" | "Saving…" | "Reconnecting…" | "Conflict — reloaded" | "Read-only";
type PendingOp = { op_id: string; epoch: number; type: string; object_id?: string; payload?: any; base_revision?: number };

const PEN_COLORS = ["#1f2933", "#c62828", "#1565c0", "#2e7d32", "#ef6c00", "#6a1b9a"];
const STICKY_COLORS = ["#fff59d", "#b3e5fc", "#c8e6c9", "#ffccbc"];

export function fold(ops: BoardOp[]): Map<string, Obj> {
  const objects = new Map<string, Obj>();
  const byRev = new Map<number, BoardOp>();
  for (const op of ops) {
    byRev.set(op.revision, op);
    const obj = objects.get(op.object_id);
    if (op.type === "add") {
      objects.set(op.object_id, { kind: op.payload.kind, data: op.payload.data, author: op.payload.author ?? op.actor_id, alive: true, rev: op.revision, dx: 0, dy: 0 });
    } else if (!obj) continue;
    else if (op.type === "erase") Object.assign(obj, { alive: false, rev: op.revision });
    else if (op.type === "move") Object.assign(obj, { dx: obj.dx + op.payload.dx, dy: obj.dy + op.payload.dy, rev: op.revision });
    else if (op.type === "undo") {
      const t = byRev.get(op.payload.target_revision);
      if (!t) continue;
      if (t.type === "add") obj.alive = false;
      if (t.type === "erase") obj.alive = true;
      if (t.type === "move") Object.assign(obj, { dx: obj.dx - t.payload.dx, dy: obj.dy - t.payload.dy });
      obj.rev = op.revision;
    }
  }
  return objects;
}

function bounds(o: Obj): [number, number, number, number] {
  if (o.kind === "stroke") {
    const xs = o.data.points.map((p: number[]) => p[0] + o.dx);
    const ys = o.data.points.map((p: number[]) => p[1] + o.dy);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  const w = o.kind === "sticky" ? 180 : Math.max(40, o.data.text.length * 9);
  const h = o.kind === "sticky" ? 120 : 24;
  return [o.data.x + o.dx, o.data.y + o.dy, o.data.x + o.dx + w, o.data.y + o.dy + h];
}

function hit(o: Obj, x: number, y: number, tol: number): boolean {
  if (o.kind !== "stroke") {
    const [a, b, c, d] = bounds(o);
    return x >= a - tol && x <= c + tol && y >= b - tol && y <= d + tol;
  }
  return o.data.points.some((p: number[]) => Math.hypot(p[0] + o.dx - x, p[1] + o.dy - y) < tol + o.data.width);
}

export function Board({ ws }: { ws: Workspace }) {
  const { session } = useSession();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [ops, setOps] = useState<BoardOp[]>([]);
  const [epoch, setEpoch] = useState(1);
  const [tool, setTool] = useState<Tool>("pen");
  const [color, setColor] = useState(PEN_COLORS[0]);
  const [save, setSave] = useState<SaveState>(ws.can_write ? "Saved" : "Read-only");
  const [message, setMessage] = useState<string | null>(null);
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [showList, setShowList] = useState(false);
  const [presence, setPresence] = useState<{ id: string; display_name: string }[]>([]);
  const pending = useRef<PendingOp[]>([]);
  const flushing = useRef(false);
  const drawing = useRef<{ id: string; points: number[][]; last: number } | null>(null);
  const panning = useRef<{ x: number; y: number } | null>(null);
  const previews = useRef(new Map<string, { points: number[][]; color: string }>());
  const state = useRef({ revision: 0, epoch: 1 });
  const [, force] = useState(0);
  const objects = fold(ops);

  const load = useCallback(async (full = false) => {
    const r = await api(`/workspaces/${ws.id}/board`, { params: full ? {} : { epoch: state.current.epoch, after: state.current.revision } });
    setOps((prev) => {
      const base = r.reset ? [] : prev;
      const known = new Set(base.map((o) => o.revision));
      const merged = [...base, ...r.ops.filter((o: BoardOp) => !known.has(o.revision))].sort((a, b) => a.revision - b.revision);
      state.current = { epoch: r.epoch, revision: merged.length ? merged[merged.length - 1].revision : 0 };
      return merged;
    });
    setEpoch(r.epoch);
  }, [ws.id]);

  const apply = useCallback((op: BoardOp) => {
    previews.current.delete(op.object_id);
    setOps((prev) => {
      if (op.epoch !== state.current.epoch || prev.some((o) => o.revision === op.revision)) return prev;
      const next = [...prev, op].sort((a, b) => a.revision - b.revision);
      const expected = state.current.revision + 1;
      state.current.revision = Math.max(state.current.revision, op.revision);
      if (op.revision !== expected) window.setTimeout(() => load(), 0); // gap: replay missed ops
      return next;
    });
  }, [load]);

  const flush = useCallback(async () => {
    if (flushing.current) return;
    flushing.current = true;
    try {
      while (pending.current.length) {
        setSave("Saving…");
        const op = pending.current[0];
        try {
          const r = await api(`/workspaces/${ws.id}/board/ops`, { body: op });
          apply(r.committed);
          pending.current.shift();
        } catch (e: any) {
          if (e.status === 0 || e.status >= 500) {
            setSave("Reconnecting…");
            return; // keep pending ops; resend with the same IDs later
          }
          pending.current.shift();
          if (e.code === "stale_epoch") pending.current = [];
          setSave("Conflict — reloaded");
          setMessage(e.message);
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
    flush();
  };

  useEffect(() => {
    load(true).catch((e) => setMessage(e.message));
    const retry = window.setInterval(() => pending.current.length && flush(), 3000);
    const unsub = realtime.subscribe(ws.id, (ev) => {
      if (ev.type === "board.op") apply(ev.op);
      else if (ev.type === "board.epoch") {
        pending.current = [];
        setMessage("A steward restored the board. Your view was refreshed.");
        load(true);
      } else if (ev.type === "board.preview") {
        if (ev.done) previews.current.delete(ev.preview_id);
        else previews.current.set(ev.preview_id, ev.stroke);
        force((n) => n + 1);
      } else if (ev.type === "presence") setPresence(ev.users);
      else if (ev.type === "subscribed") {
        previews.current.clear(); // disconnect discards uncommitted remote previews
        load().then(flush);
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
    ctx.clearRect(-view.x / view.scale, -view.y / view.scale, rect.width / view.scale, rect.height / view.scale);
    const line = (pts: number[][], c: string, w: number, dx = 0, dy = 0) => {
      ctx.strokeStyle = c;
      ctx.lineWidth = w;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      pts.forEach((p, i) => (i ? ctx.lineTo(p[0] + dx, p[1] + dy) : ctx.moveTo(p[0] + dx, p[1] + dy)));
      if (pts.length === 1) ctx.lineTo(pts[0][0] + dx + 0.1, pts[0][1] + dy);
      ctx.stroke();
    };
    for (const o of objects.values()) {
      if (!o.alive) continue;
      if (o.kind === "stroke") line(o.data.points, o.data.color, o.data.width, o.dx, o.dy);
      else {
        const x = o.data.x + o.dx, y = o.data.y + o.dy;
        if (o.kind === "sticky") {
          ctx.fillStyle = o.data.color;
          ctx.fillRect(x, y, 180, 120);
          ctx.strokeStyle = "#00000033";
          ctx.strokeRect(x, y, 180, 120);
        }
        ctx.fillStyle = o.kind === "sticky" ? "#1f2933" : o.data.color;
        ctx.font = "16px system-ui, sans-serif";
        const lines = o.data.text.split("\n");
        lines.forEach((t: string, i: number) => ctx.fillText(t, x + (o.kind === "sticky" ? 10 : 0), y + 20 + i * 20, o.kind === "sticky" ? 160 : undefined));
      }
    }
    for (const p of previews.current.values()) line(p.points, p.color ?? "#999", 3);
    if (drawing.current) line(drawing.current.points, color, 3);
  });

  const toWorld = (e: React.PointerEvent) => {
    const r = canvasRef.current!.getBoundingClientRect();
    return [(e.clientX - r.left - view.x) / view.scale, (e.clientY - r.top - view.y) / view.scale];
  };

  function onDown(e: React.PointerEvent) {
    const [x, y] = toWorld(e);
    if (tool === "pan" || e.button === 1) {
      panning.current = { x: e.clientX - view.x, y: e.clientY - view.y };
      return;
    }
    if (!ws.can_write) return;
    if (tool === "pen") {
      (e.target as Element).setPointerCapture(e.pointerId);
      drawing.current = { id: newId("s"), points: [[x, y]], last: 0 };
    } else if (tool === "eraser") {
      const target = [...objects.entries()].reverse().find(([, o]) => o.alive && hit(o, x, y, 8 / view.scale));
      if (target) submit({ type: "erase", object_id: target[0] });
    } else {
      const text = window.prompt(tool === "sticky" ? "Sticky note text" : "Text");
      if (text && text.trim()) submit({ type: "add", object_id: newId(tool[0]), payload: { kind: tool, data: { x, y, text: text.slice(0, 1000), color: tool === "sticky" ? STICKY_COLORS[0] : color } } });
    }
  }

  function onMove(e: React.PointerEvent) {
    if (panning.current) {
      setView((v) => ({ ...v, x: e.clientX - panning.current!.x, y: e.clientY - panning.current!.y }));
      return;
    }
    const d = drawing.current;
    if (!d) return;
    const [x, y] = toWorld(e);
    d.points.push([Math.round(x * 10) / 10, Math.round(y * 10) / 10]);
    if (d.points.length > 3900) return onUp();
    const now = performance.now();
    if (now - d.last > 60) {
      d.last = now;
      realtime.send({ type: "board.preview", workspace_id: ws.id, preview_id: d.id, stroke: { points: d.points.slice(-400), color } });
    }
    force((n) => n + 1);
  }

  function onUp() {
    panning.current = null;
    const d = drawing.current;
    drawing.current = null;
    if (!d) return;
    realtime.send({ type: "board.preview", workspace_id: ws.id, preview_id: d.id, done: true });
    submit({ type: "add", object_id: d.id, payload: { kind: "stroke", data: { points: d.points, color, width: 3 } } });
  }

  function fit() {
    const live = [...objects.values()].filter((o) => o.alive);
    const canvas = canvasRef.current;
    if (!live.length || !canvas) return setView({ x: 0, y: 0, scale: 1 });
    const bs = live.map(bounds);
    const [a, b, c, d] = [Math.min(...bs.map((q) => q[0])), Math.min(...bs.map((q) => q[1])), Math.max(...bs.map((q) => q[2])), Math.max(...bs.map((q) => q[3]))];
    const r = canvas.getBoundingClientRect();
    const scale = Math.min(4, Math.max(0.1, Math.min(r.width / (c - a + 80), r.height / (d - b + 80))));
    setView({ scale, x: -a * scale + 40, y: -b * scale + 40 });
  }

  async function restore() {
    const answer = window.prompt("Restore the board to which revision? (0 clears the board)", "0");
    if (answer === null) return;
    try {
      await api(`/workspaces/${ws.id}/board/restore`, { body: { revision: Number(answer), reason: "Restored from board view" } });
      await load(true);
    } catch (e: any) {
      setMessage(e.message);
    }
  }

  const mine = ops.some((o) => o.actor_id === session?.user.id && o.type !== "undo");
  const typed = [...objects.entries()].filter(([, o]) => o.alive && o.kind !== "stroke");

  return (
    <section className="whiteboard" aria-label={`Whiteboard for ${ws.name}`}>
      <div className="toolbar" role="toolbar" aria-label="Drawing tools">
        {(["pen", "eraser", "text", "sticky", "pan"] as Tool[]).map((t) => (
          <button key={t} className={"tool" + (tool === t ? " active" : "")} aria-pressed={tool === t} onClick={() => setTool(t)} disabled={!ws.can_write && t !== "pan"}>
            {t === "pen" ? "✏️ Pen" : t === "eraser" ? "🧽 Eraser" : t === "text" ? "🔤 Text" : t === "sticky" ? "🗒 Sticky" : "✋ Pan"}
          </button>
        ))}
        <span className="swatches" role="radiogroup" aria-label="Colour">
          {PEN_COLORS.map((c) => (
            <button key={c} role="radio" aria-checked={color === c} aria-label={`Colour ${c}`} className={"swatch" + (color === c ? " active" : "")} style={{ background: c }} onClick={() => setColor(c)} />
          ))}
        </span>
        <button className="tool" onClick={() => submit({ type: "undo" })} disabled={!ws.can_write || !mine}>↶ Undo mine</button>
        <button className="tool" onClick={() => setView((v) => ({ ...v, scale: Math.min(4, v.scale * 1.25) }))} aria-label="Zoom in">＋</button>
        <button className="tool" onClick={() => setView((v) => ({ ...v, scale: Math.max(0.1, v.scale / 1.25) }))} aria-label="Zoom out">－</button>
        <button className="tool" onClick={fit}>Fit</button>
        <button className="tool" onClick={() => setShowList((v) => !v)} aria-expanded={showList}>List view</button>
        {ws.can_moderate && ws.can_write && <button className="tool" onClick={restore}>Restore…</button>}
        <span className={"save-state" + (save === "Saved" ? " ok" : "")} role="status">{save}</span>
        <span className="muted small">Epoch {epoch} · rev {state.current.revision} · {presence.length} here: {presence.map((p) => p.display_name).join(", ")}</span>
      </div>
      {message && <p className="notice" role="alert">{message} <button className="ghost small" onClick={() => setMessage(null)}>Dismiss</button></p>}
      <canvas
        ref={canvasRef}
        className={`canvas tool-${tool}`}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        onWheel={(e) => setView((v) => ({ ...v, scale: Math.min(4, Math.max(0.1, v.scale * (e.deltaY < 0 ? 1.1 : 0.9))) }))}
        aria-label="Drawing canvas. Use the list view for a text alternative."
        role="img"
      />
      {showList && (
        <div className="card board-list">
          <h2>Board items</h2>
          <p className="muted small">{[...objects.values()].filter((o) => o.alive && o.kind === "stroke").length} drawn strokes</p>
          {typed.length === 0 ? <p className="muted">No text or sticky notes.</p> : (
            <ul className="plain">{typed.map(([id, o]) => (
              <li key={id}>{o.kind === "sticky" ? "Sticky" : "Text"}: {o.data.text}
                {ws.can_write && <button className="ghost small" onClick={() => submit({ type: "erase", object_id: id })}>Erase</button>}
              </li>
            ))}</ul>
          )}
        </div>
      )}
    </section>
  );
}
