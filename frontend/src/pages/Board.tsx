import { SelectedObjectControls } from "../features/whiteboard/SelectedObjectControls";
import { drawBoard } from "../features/whiteboard/drawBoard";
import { BoardToolbar } from "../features/whiteboard/BoardToolbar";
import {
  bounds,
  fold,
  hit,
  type BoardState,
  type Obj,
  type PendingOp,
  type Region,
  type SaveState,
  type Tool,
} from "../features/whiteboard/boardModel";
import { loadBoardFonts } from "../features/whiteboard/textStyle";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorCode, errorMessage, newId, outcomeUnknown } from "../api";
import { API, BASE } from "../config";
import { realtime, type StrokePreview } from "../realtime";
import type { BoardOp, NoteData, Point, Workspace } from "../types";
import { PublishSnapshot } from "../components/PublishSnapshot";
import { ConversationTask } from "../components/ConversationTask";
import { Button, Card, Dialog } from "../ui";
import {
  BoardTabs,
  STICKY_SHAPES,
  STICKY_COLORS,
  PEN_COLORS,
  generateShapePoints,
  StickyEditDialog,
  TextEditDialog,
  WhiteboardHoverTooltip,
  type HoverTooltipData,
  type StickyShape,
  type StickySize,
  type DrawMode,
  type StickyConfig,
} from "../features/whiteboard";
import "./board-chrome.css";
import { UploadRecovery, useUploadQueue } from "../components/UploadRecovery";
import type { UploadedAsset } from "../uploads";

export { STICKY_SHAPES };
export { fold, stickyDimensions, type Region } from "../features/whiteboard/boardModel";

/** Whiteboard. With ``panel`` set it runs as a board-only touch panel: no images, publishing or restore. */
export function Board({
  ws: workspace,
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
  const [serverCanContribute, setServerCanContribute] = useState(workspace.can_contribute);
  const ws = {
    ...workspace,
    can_contribute: workspace.can_contribute && serverCanContribute,
  };
  useEffect(() => setServerCanContribute(workspace.can_contribute), [workspace.can_contribute]);
  useEffect(() => {
    void loadBoardFonts().then(() => force((value) => value + 1));
  }, []);
  const [pairing, setPairing] = useState<{
    code: string;
    expires_at: string;
  } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const dragging = useRef<{
    id: string;
    start: Point;
    dx: number;
    dy: number;
    revision: number;
  } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [taskContext, setTaskContext] = useState<{
    epoch: number;
    revision: number;
  } | null>(null);
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
  const [hoverTooltip, setHoverTooltip] = useState<HoverTooltipData | null>(null);
  const [members, setMembers] = useState<Map<string, string>>(new Map());
  const shapeDrawing = useRef<{
    id: string;
    start: Point;
    points: Point[];
  } | null>(null);

  useEffect(() => {
    if (panel) return;
    api<{ id: string; display_name: string }[]>(`/workspaces/${ws.id}/members`)
      .then((list) => {
        const map = new Map<string, string>();
        list.forEach((m) => map.set(m.id, m.display_name));
        setMembers(map);
      })
      .catch(() => undefined);
  }, [ws.id, panel]);
  const [save, setSave] = useState<SaveState>(ws.can_contribute ? "Saved" : "Read-only");
  const [message, setMessage] = useState<string | null>(null);
  const uploads = useUploadQueue(maxUploadBytes, (asset) => {
    void placeImage(asset);
  });
  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [boardIndex, setBoardIndex] = useState(0);
  const activeScope = useRef(`${ws.id}:0`);
  activeScope.current = `${ws.id}:${boardIndex}`;
  const loadSequence = useRef(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const [boardTabs, setBoardTabs] = useState<{ board_index: number; title: string }[]>([
    { board_index: 0, title: "WhiteBoard_1" },
  ]);
  const [maxWhiteboards, setMaxWhiteboards] = useState(5);
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

  useEffect(() => {
    if (panel) return;
    api<
      | {
          boards?: { board_index: number; title: string }[];
          max_whiteboards?: number;
        }
      | { board_index: number; title: string }[]
    >(`/workspaces/${ws.id}/boards`)
      .then((res) => {
        const list = Array.isArray(res) ? res : (res.boards ?? []);
        if (list.length > 0) setBoardTabs(list);
        if (!Array.isArray(res) && typeof res.max_whiteboards === "number") {
          setMaxWhiteboards(res.max_whiteboards);
        }
      })
      .catch(() => undefined);
  }, [ws.id, panel]);

  const load = useCallback(
    async (full = false) => {
      const sequence = ++loadSequence.current;
      const scope = `${ws.id}:${boardIndex}`;
      const params: Record<string, string | number> = {
        board_index: boardIndex,
      };
      if (!full) {
        params.epoch = state.current.epoch;
        params.after = state.current.revision;
      }
      const r = await api<BoardState>(`/workspaces/${ws.id}/board`, { params });
      if (!alive.current || activeScope.current !== scope || sequence !== loadSequence.current) return;
      setServerCanContribute(r.can_write);
      if (r.epoch < state.current.epoch) return;
      // A reset response starts from the compacted snapshot (if any) plus later operations.
      if (r.reset) setBase(r.snapshot?.objects ?? null);
      setOps((prev) => {
        const kept = r.reset ? prev.filter((op) => op.epoch === r.epoch && op.revision > r.revision) : prev;
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
    [ws.id, boardIndex],
  );

  const apply = useCallback(
    (op: BoardOp) => {
      if (!alive.current || activeScope.current !== `${ws.id}:${boardIndex}`) return;
      const opIdx = (op as { board_index?: number }).board_index ?? 0;
      if (opIdx !== boardIndex) return;
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
    [load, boardIndex, ws.id],
  );

  const flush = useCallback(async () => {
    if (flushing.current) return;
    flushing.current = true;
    const scope = `${ws.id}:${boardIndex}`;
    try {
      while (pending.current.length) {
        setSave("Saving…");
        const op = pending.current[0];
        try {
          const r = await api<{ committed: BoardOp; duplicate: boolean }>(`/workspaces/${ws.id}/board/ops`, {
            body: { ...op, board_index: boardIndex },
          });
          if (!alive.current || activeScope.current !== scope) return;
          apply(r.committed);
          pending.current.shift();
        } catch (e: unknown) {
          if (!alive.current || activeScope.current !== scope) return;
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
  }, [ws.id, apply, load, boardIndex]);

  const submit = (op: Omit<PendingOp, "op_id" | "epoch">) => {
    pending.current.push({
      op_id: newId("op"),
      epoch: state.current.epoch,
      ...op,
    });
    void flush();
  };

  useEffect(() => {
    state.current = { revision: 0, epoch: 1 };
    setOps([]);
    setBase(null);
    setSelection(null);
    setPairing(null);
    setTaskContext(null);
    setSelectedId(null);
    dragging.current = null;
    setEditingSticky(null);
    setEditingText(null);
    setCreatingStickyAt(null);
    setCreatingTextAt(null);
    drawing.current = null;
    shapeDrawing.current = null;
    previews.current.clear();
    pending.current = [];
    load(true).catch((e) => setMessage(errorMessage(e)));
  }, [boardIndex, load]);

  function switchBoard(index: number) {
    if (pending.current.length || flushing.current) {
      setMessage("Wait for this board to finish saving before switching boards.");
      return;
    }
    activeScope.current = `${ws.id}:${index}`;
    setBoardIndex(index);
  }

  async function renameBoard(idx: number, currentTitle: string) {
    const title = window.prompt("Short board name (max 10 chars, or default WhiteBoard_N):", currentTitle);
    if (!title || !title.trim() || title.trim() === currentTitle) return;
    const clean = title.trim();
    if (!clean.match(/^WhiteBoard_\d+$/i) && clean.length > 10) {
      setMessage("Board name must be at most 10 characters (e.g. SiC Proj, AdminBoard).");
      return;
    }
    try {
      await api(`/workspaces/${ws.id}/boards/${idx}`, {
        method: "PATCH",
        body: { title: clean },
      });
      setBoardTabs((prev) => prev.map((t) => (t.board_index === idx ? { ...t, title: clean } : t)));
    } catch (e: unknown) {
      setMessage(errorMessage(e));
    }
  }

  async function addBoard() {
    if (boardTabs.length >= maxWhiteboards) {
      setMessage(`Maximum ${maxWhiteboards} whiteboards allowed.`);
      return;
    }
    const nextIdx = boardTabs.length;
    const newTitle = `WhiteBoard_${nextIdx + 1}`;
    try {
      await api(`/workspaces/${ws.id}/boards/${nextIdx}`, {
        method: "PATCH",
        body: { title: newTitle },
      });
      setBoardTabs((prev) => [...prev, { board_index: nextIdx, title: newTitle }]);
      switchBoard(nextIdx);
    } catch (e: unknown) {
      setMessage(errorMessage(e));
    }
  }

  useEffect(() => {
    load(true).catch((e) => setMessage(errorMessage(e)));
    const retry = window.setInterval(() => pending.current.length && flush(), 3000);
    const unsub = realtime.subscribe(ws.id, (ev) => {
      if (ev.type === "board.op") apply(ev.op);
      else if (ev.type === "board.epoch" && (ev.board_index ?? 0) === boardIndex) {
        pending.current = [];
        setMessage("A steward restored the board. Your view was refreshed.");
        load(true).catch((e) => setMessage(errorMessage(e)));
      } else if (ev.type === "board.preview" && (ev.board_index ?? 0) === boardIndex) {
        if (ev.done) previews.current.delete(ev.preview_id);
        else if (ev.stroke) previews.current.set(ev.preview_id, ev.stroke);
        force((n) => n + 1);
      } else if (ev.type === "presence") setPresence(ev.users);
      else if (ev.type === "subscribed" || ev.type === "access_changed") {
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
  }, [ws.id, load, apply, flush, boardIndex]);

  // ---- rendering ----------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    drawBoard(canvas, {
      objects,
      selected,
      drag: dragging.current,
      view,
      images: images.current,
      onImageLoad: () => force((n) => n + 1),
      imageBase: API,
      panel: Boolean(panel),
      shapeDrawing: shapeDrawing.current,
      previews: previews.current.values(),
      drawing: drawing.current,
      color,
      selection,
    });
  });

  const toWorld = (e: React.PointerEvent): Point => {
    const r = canvasRef.current!.getBoundingClientRect();
    return [(e.clientX - r.left - view.x) / view.scale, (e.clientY - r.top - view.y) / view.scale];
  };

  function openObjectEditor(targetId: string, targetObj: Obj) {
    if (targetObj.kind === "sticky") {
      setEditingSticky({
        id: targetId,
        obj: targetObj as Obj & { kind: "sticky"; data: NoteData },
        config: {
          text: targetObj.data.text,
          shape: targetObj.data.shape ?? "rectangle",
          size: targetObj.data.size ?? "medium",
          color: targetObj.data.color,
          font_family: targetObj.data.font_family,
          font_size: targetObj.data.font_size,
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
  const selected = selectedId ? objects.get(selectedId) : undefined;
  function editSelected() {
    if (selectedId && selected && ws.can_contribute && (selected.author === userId || ws.can_moderate))
      openObjectEditor(selectedId, selected);
  }
  function moveSelected(dx: number, dy: number) {
    if (selectedId && selected)
      submit({
        type: "move",
        object_id: selectedId,
        base_revision: selected.rev,
        payload: { dx, dy },
      });
  }

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
    if (!ws.can_contribute) return;
    if (tool === "image") return;
    if (tool === "select" || tool === "sticky" || tool === "text") {
      const target = [...objects.entries()]
        .reverse()
        .find(([, o]) => o.alive && hit(o, x, y, 6 / view.scale));
      if (target) {
        const [targetId, targetObj] = target;
        if (targetObj.author !== userId && !ws.can_moderate) {
          setMessage("Only the author or a steward can change this item.");
          return;
        }
        if (tool === "select") {
          setSelectedId(targetId);
          dragging.current = {
            id: targetId,
            start: [x, y],
            dx: 0,
            dy: 0,
            revision: targetObj.rev,
          };
          (e.target as Element).setPointerCapture(e.pointerId);
          return;
        }
        openObjectEditor(targetId, targetObj);
        return;
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
      if (target && (target[1].author === userId || ws.can_moderate))
        submit({ type: "erase", object_id: target[0] });
    }
  }

  function onMove(e: React.PointerEvent) {
    if (dragging.current) {
      const point = toWorld(e);
      dragging.current.dx = point[0] - dragging.current.start[0];
      dragging.current.dy = point[1] - dragging.current.start[1];
      force((value) => value + 1);
      return;
    }
    if (panning.current) {
      setView((v) => ({
        ...v,
        x: e.clientX - panning.current!.x,
        y: e.clientY - panning.current!.y,
      }));
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
          board_index: boardIndex,
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
    const drag = dragging.current;
    dragging.current = null;
    if (drag) {
      if (Math.abs(drag.dx) + Math.abs(drag.dy) > 2)
        submit({
          type: "move",
          object_id: drag.id,
          base_revision: drag.revision,
          payload: { dx: drag.dx, dy: drag.dy },
        });
      force((value) => value + 1);
      return;
    }
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
          payload: {
            kind: "stroke",
            data: { points: sd.points, color, width: 3 },
          },
        });
      }
      return;
    }
    const d = drawing.current;
    drawing.current = null;
    if (!d) return;
    const strokeW = drawMode === "pencil" ? 1.5 : drawMode === "brush" ? 8 : 3;
    realtime.send({
      type: "board.preview",
      board_index: boardIndex,
      workspace_id: ws.id,
      preview_id: d.id,
      done: true,
    });
    submit({
      type: "add",
      object_id: d.id,
      payload: {
        kind: "stroke",
        data: { points: d.points, color, width: strokeW },
      },
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
        body: {
          board_index: boardIndex,
          revision: Number(answer),
          reason: "Restored from board view",
        },
      });
      await load(true);
    } catch (e: unknown) {
      setMessage(errorMessage(e));
    }
  }

  const mine = ops.some((o) => o.actor_id === userId && o.type !== "undo");
  const listedObjects = [...objects.entries()].filter(([, object]) => object.alive);
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
        {!panel && (
          <BoardTabs
            tabs={boardTabs}
            selected={boardIndex}
            label="Whiteboard tabs"
            canWrite={ws.can_contribute}
            maximum={maxWhiteboards}
            onSelect={switchBoard}
            onRename={(index, title) => void renameBoard(index, title)}
            onAdd={() => void addBoard()}
          />
        )}
        <BoardToolbar
          {...{
            boardIndex,
            color,
            drawMode,
            epoch,
            fileRef,
            fit,
            mine,
            openOnPanel,
            panel,
            presence,
            restore,
            save,
            setColor,
            setDrawMode,
            setMessage,
            setSelection,
            setShowList,
            setStickyColor,
            setStickyShape,
            setStickySize,
            setTaskContext,
            setTool,
            setView,
            showList,
            state,
            stickyColor,
            stickyShape,
            stickySize,
            submit,
            tool,
            uploads,
            ws,
          }}
        />
        {tool === "snapshot" && !selection && (
          <p className="board-notice">Drag on the board to select the region to publish.</p>
        )}
        {selection && tool === "snapshot" && (
          <PublishSnapshot
            ws={ws}
            boardIndex={boardIndex}
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
          onDoubleClick={editSelected}
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
        {selected?.alive && ws.can_contribute && (selected.author === userId || ws.can_moderate) && (
          <SelectedObjectControls
            label={
              selected.kind === "sticky" || selected.kind === "text" ? selected.data.text : selected.kind
            }
            canEditText={selected.kind === "sticky" || selected.kind === "text"}
            onEdit={editSelected}
            onMove={moveSelected}
            onErase={() => submit({ type: "erase", object_id: selectedId ?? undefined })}
          />
        )}
        {showList && (
          <div className="board-list">
            <Card title="Board items">
              <div className="board-dialog">
                <p className="board-dialog__muted">
                  {[...objects.values()].filter((o) => o.alive && o.kind === "stroke").length} drawn strokes ·{" "}
                  {imageCount} images
                </p>
                {listedObjects.length === 0 ? (
                  <p className="board-dialog__muted">No items on this board.</p>
                ) : (
                  <ul className="board-dialog__items">
                    {listedObjects.map(([id, o]) => (
                      <li key={id}>
                        {o.kind === "sticky" || o.kind === "text"
                          ? `${o.kind === "sticky" ? "Sticky" : "Text"}: ${o.data.text}`
                          : o.kind === "image"
                            ? "Image"
                            : "Drawing stroke"}
                        {ws.can_contribute && (o.author === userId || ws.can_moderate) && (
                          <Button size="sm" onClick={() => setSelectedId(id)}>
                            Select item
                          </Button>
                        )}
                        {ws.can_contribute && (o.author === userId || ws.can_moderate) && (
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
        <WhiteboardHoverTooltip data={hoverTooltip} />
        {editingSticky && (
          <StickyEditDialog
            canEdit={ws.can_contribute}
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
              submit({
                type: "update",
                object_id: editingSticky.id,
                base_revision: editingSticky.obj.rev,
                payload: {
                  kind: "sticky",
                  data: {
                    x: editingSticky.obj.data.x,
                    y: editingSticky.obj.data.y,
                    text: cfg.text,
                    shape: cfg.shape,
                    size: cfg.size,
                    color: cfg.color,
                    font_family: cfg.font_family,
                    font_size: cfg.font_size,
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
            canEdit={ws.can_contribute}
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
                    font_family: cfg.font_family,
                    font_size: cfg.font_size,
                  },
                },
              });
            }}
          />
        )}
        {editingText && (
          <TextEditDialog
            canEdit={ws.can_contribute}
            open={true}
            initialText={editingText.text}
            initialColor={editingText.color}
            initialStyle={editingText.obj.data}
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
            onSave={(t, c, style) => {
              submit({
                type: "update",
                object_id: editingText.id,
                base_revision: editingText.obj.rev,
                payload: {
                  kind: "text",
                  data: {
                    x: editingText.obj.data.x,
                    y: editingText.obj.data.y,
                    ...style,
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
            canEdit={ws.can_contribute}
            open={true}
            initialColor={color}
            onClose={() => setCreatingTextAt(null)}
            onSave={(t, c, style) => {
              submit({
                type: "add",
                object_id: newId("t"),
                payload: {
                  kind: "text",
                  data: {
                    x: creatingTextAt[0],
                    y: creatingTextAt[1],
                    ...style,
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
