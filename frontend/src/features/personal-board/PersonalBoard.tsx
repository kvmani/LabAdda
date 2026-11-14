import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "../../session";
import { boardDraft, rememberBoard } from "./draft";
import { api, errorMessage, newId } from "../../api";
import { API } from "../../config";
import { Button, ErrorState, PageHeader, Skeleton } from "../../ui";
import {
  STICKY_COLORS,
  PEN_COLORS,
  getStickyDimensions,
  drawStickyCanvas,
  generateShapePoints,
  bounds,
  hit,
  StickyEditDialog,
  TextEditDialog,
  WhiteboardHoverTooltip,
  WhiteboardToolbar,
  type StickyShape,
  type StickySize,
  type DrawMode,
  type WhiteboardTool,
  type HoverTooltipData,
  type StickyConfig,
} from "../whiteboard";
import type { BoardDocument, BoardObject } from "./types";
import "../../pages/board-chrome.css";
import "./personal-board.css";

/** A private whiteboard with durable saves, local drafts, rich shapes, and full editability. */
export function PersonalBoard() {
  const { session } = useSession();
  const draftKey = `${session?.user.id}:${session?.csrf_token}`;
  const userName = session?.user.display_name ?? "You";
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const [document, setDocument] = useState<BoardDocument | null>(null);
  const [objects, setObjects] = useState<BoardObject[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const images = useRef(new Map<string, HTMLImageElement>());

  const [tool, setTool] = useState<WhiteboardTool>("pen");
  const [drawMode, setDrawMode] = useState<DrawMode>("pen");
  const [color, setColor] = useState<string>(PEN_COLORS[0]);
  const [stickyShape, setStickyShape] = useState<StickyShape>("rectangle");
  const [stickySize, setStickySize] = useState<StickySize>("medium");
  const [stickyColor, setStickyColor] = useState<string>(STICKY_COLORS[0]);

  const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
  const [hoverTooltip, setHoverTooltip] = useState<HoverTooltipData | null>(null);

  const [editingSticky, setEditingSticky] = useState<{
    id: string;
    config: StickyConfig;
    authorInfo?: { name: string; time: string };
  } | null>(null);
  const [creatingStickyAt, setCreatingStickyAt] = useState<[number, number] | null>(null);

  const [editingText, setEditingText] = useState<{
    id: string;
    text: string;
    color: string;
    authorInfo?: { name: string; time: string };
  } | null>(null);
  const [creatingTextAt, setCreatingTextAt] = useState<[number, number] | null>(null);

  const drawing = useRef<{ id: string; points: [number, number][]; last: number } | null>(null);
  const shapeDrawing = useRef<{ id: string; start: [number, number]; points: [number, number][] } | null>(
    null,
  );
  const panning = useRef<{ x: number; y: number } | null>(null);
  const draggingObj = useRef<{
    id: string;
    startX: number;
    startY: number;
    origX: number;
    origY: number;
  } | null>(null);
  const [, force] = useState(0);

  // Load document or restore draft
  useEffect(() => {
    const savedDraft = boardDraft(draftKey);
    if (savedDraft) {
      setDocument(savedDraft.document);
      setObjects(savedDraft.objects);
      setDirty(true);
      setLoading(false);
      return;
    }
    let active = true;
    api<BoardDocument>("/me/whiteboard")
      .then((result) => {
        if (active && mounted.current) {
          setDocument(result);
          setObjects(result.objects);
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [draftKey]);

  // Persist draft in session
  useEffect(() => {
    if (dirty && document) rememberBoard({ key: draftKey, document, objects });
  }, [dirty, document, draftKey, objects]);

  // Warn before closing dirty tab
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function changeObjects(next: BoardObject[]) {
    if (next.length > 500) {
      setError("This board has reached its 500-object limit.");
      return;
    }
    setObjects(next);
    setDirty(true);
    force((n) => n + 1);
  }

  async function save() {
    if (!document) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<BoardDocument>("/me/whiteboard", {
        method: "PUT",
        body: { revision: document.revision, objects },
      });
      if (!mounted.current) return;
      setDocument(result);
      setObjects(result.objects);
      setDirty(false);
    } catch (e: unknown) {
      if (!mounted.current) return;
      setError(errorMessage(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }

  function undo() {
    if (!objects.length) return;
    changeObjects(objects.slice(0, -1));
  }

  function fit() {
    const canvas = canvasRef.current;
    if (!objects.length || !canvas) return setView({ x: 0, y: 0, scale: 1 });
    const bs = objects.map((o) => bounds(o));
    const [minX, minY, maxX, maxY] = [
      Math.min(...bs.map((q) => q[0])),
      Math.min(...bs.map((q) => q[1])),
      Math.max(...bs.map((q) => q[2])),
      Math.max(...bs.map((q) => q[3])),
    ];
    const r = canvas.getBoundingClientRect();
    const scale = Math.min(
      3,
      Math.max(0.2, Math.min(r.width / (maxX - minX + 80), r.height / (maxY - minY + 80))),
    );
    setView({ scale, x: -minX * scale + 40, y: -minY * scale + 40 });
  }

  // Draw loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    if (canvas.width !== Math.floor(rect.width * dpr) || canvas.height !== Math.floor(rect.height * dpr)) {
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.scale, view.scale);

    const line = (pts: [number, number][], strokeCol: string, strokeW = 3) => {
      if (pts.length < 2) return;
      const first = pts[0];
      if (!first) return;
      ctx.strokeStyle = strokeCol;
      ctx.lineWidth = strokeW;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(first[0], first[1]);
      for (let i = 1; i < pts.length; i++) {
        const p = pts[i];
        if (p) ctx.lineTo(p[0], p[1]);
      }
      ctx.stroke();
    };

    for (const o of objects) {
      if (o.kind === "image") {
        const id = o.asset_id;
        if (id) {
          let img = images.current.get(id);
          if (!img) {
            img = new Image();
            img.onload = () => force((n) => n + 1);
            img.src = o.preview_url ?? `${API}/files/${id}/preview`;
            images.current.set(id, img);
          }
          if (img.complete && img.naturalWidth) {
            ctx.drawImage(img, o.x ?? 0, o.y ?? 0, o.w ?? 160, o.h ?? 120);
          } else {
            ctx.strokeStyle = "#9aa5b1";
            ctx.strokeRect(o.x ?? 0, o.y ?? 0, o.w ?? 160, o.h ?? 120);
          }
        }
      } else if (o.kind === "stroke") {
        if (o.points) line(o.points, o.color, o.width ?? 3);
      } else if (o.kind === "sticky") {
        const shape = o.shape ?? "rectangle";
        const [w, h] = getStickyDimensions(shape, o.size ?? "medium");
        drawStickyCanvas(ctx, o.x ?? 0, o.y ?? 0, w, h, shape, o.color, o.text ?? "");
      } else if (o.kind === "text") {
        ctx.fillStyle = o.color;
        ctx.font = "16px system-ui, sans-serif";
        ctx.textAlign = "left";
        const lines = (o.text ?? "").split("\n");
        lines.forEach((t: string, i: number) => ctx.fillText(t, o.x ?? 0, (o.y ?? 0) + 20 + i * 20));
      }
    }

    if (shapeDrawing.current) {
      line(shapeDrawing.current.points, color, 3);
    }
    if (drawing.current) {
      const strokeW = drawMode === "pencil" ? 1.5 : drawMode === "brush" ? 8 : 3;
      line(drawing.current.points, color, strokeW);
    }

    ctx.restore();
  });

  const toWorld = useCallback(
    (e: React.PointerEvent): [number, number] => {
      const r = canvasRef.current!.getBoundingClientRect();
      return [
        Math.round(((e.clientX - r.left - view.x) / view.scale) * 10) / 10,
        Math.round(((e.clientY - r.top - view.y) / view.scale) * 10) / 10,
      ];
    },
    [view],
  );

  function onDown(e: React.PointerEvent) {
    const [x, y] = toWorld(e);
    if (tool === "pan" || e.button === 1) {
      panning.current = { x: e.clientX - view.x, y: e.clientY - view.y };
      return;
    }
    if (tool === "select") {
      const target = [...objects].reverse().find((o) => hit(o, x, y, 6 / view.scale));
      if (target) {
        if (target.kind === "sticky") {
          setEditingSticky({
            id: target.id,
            config: {
              text: target.text ?? "",
              shape: target.shape ?? "rectangle",
              size: target.size ?? "medium",
              color: target.color,
            },
            authorInfo: {
              name: target.author ?? userName,
              time: target.created_at ? new Date(target.created_at).toLocaleString() : "Saved revision",
            },
          });
          return;
        }
        if (target.kind === "text") {
          setEditingText({
            id: target.id,
            text: target.text ?? "",
            color: target.color,
            authorInfo: {
              name: target.author ?? userName,
              time: target.created_at ? new Date(target.created_at).toLocaleString() : "Saved revision",
            },
          });
          return;
        }
        if (target.kind === "image" || target.kind === "stroke") {
          draggingObj.current = {
            id: target.id,
            startX: x,
            startY: y,
            origX: target.x ?? 0,
            origY: target.y ?? 0,
          };
          (e.target as Element).setPointerCapture(e.pointerId);
          return;
        }
      }
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
    if (tool === "pen") {
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
      return;
    }
    if (tool === "eraser") {
      const target = [...objects].reverse().find((o) => hit(o, x, y, 8 / view.scale));
      if (target) {
        changeObjects(objects.filter((o) => o.id !== target.id));
      }
    }
  }

  function onMove(e: React.PointerEvent) {
    if (panning.current) {
      setView((v) => ({ ...v, x: e.clientX - panning.current!.x, y: e.clientY - panning.current!.y }));
      return;
    }
    if (draggingObj.current) {
      const [x, y] = toWorld(e);
      const drag = draggingObj.current;
      const dx = x - drag.startX;
      const dy = y - drag.startY;
      changeObjects(
        objects.map((o) => (o.id === drag.id ? { ...o, x: drag.origX + dx, y: drag.origY + dy } : o)),
      );
      return;
    }
    if (shapeDrawing.current) {
      const [x, y] = toWorld(e);
      shapeDrawing.current.points = generateShapePoints(drawMode, shapeDrawing.current.start, [x, y]);
      force((n) => n + 1);
      return;
    }
    if (drawing.current) {
      const [x, y] = toWorld(e);
      drawing.current.points.push([Math.min(1000, Math.max(0, x)), Math.min(600, Math.max(0, y))]);
      force((n) => n + 1);
      return;
    }

    // Hover metadata check
    const [wx, wy] = toWorld(e);
    const hitObj = [...objects].reverse().find((o) => hit(o, wx, wy, 6 / view.scale));
    if (hitObj) {
      const author = hitObj.author ?? "You";
      const timeStr = hitObj.created_at
        ? new Date(hitObj.created_at).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "Current session";
      const kindLabel =
        hitObj.kind === "sticky"
          ? `${(hitObj.shape ?? "Rectangle").toUpperCase()} note (${hitObj.size ?? "medium"})`
          : hitObj.kind === "stroke"
            ? "Drawing stroke"
            : hitObj.kind === "text"
              ? "Text label"
              : "Image";
      setHoverTooltip({
        x: e.clientX + 14,
        y: e.clientY + 14,
        author,
        time: timeStr,
        kind: kindLabel,
      });
    } else {
      setHoverTooltip(null);
    }
  }

  function onUp() {
    panning.current = null;
    draggingObj.current = null;
    if (shapeDrawing.current) {
      const sd = shapeDrawing.current;
      shapeDrawing.current = null;
      if (sd.points.length >= 2) {
        changeObjects([
          ...objects,
          {
            id: sd.id,
            kind: "stroke",
            color,
            points: sd.points.map(([px, py]) => [
              Math.min(1000, Math.max(0, px)),
              Math.min(600, Math.max(0, py)),
            ]),
            width: 3,
            author: userName,
            created_at: new Date().toISOString(),
          },
        ]);
      }
      return;
    }
    const d = drawing.current;
    drawing.current = null;
    if (!d || d.points.length < 2) return;
    const strokeW = drawMode === "pencil" ? 1.5 : drawMode === "brush" ? 8 : 3;
    changeObjects([
      ...objects,
      {
        id: d.id,
        kind: "stroke",
        color,
        points: d.points.map(([px, py]) => [Math.min(1000, Math.max(0, px)), Math.min(600, Math.max(0, py))]),
        width: strokeW,
        author: userName,
        created_at: new Date().toISOString(),
      },
    ]);
  }

  function handleSaveSticky(cfg: StickyConfig) {
    if (editingSticky) {
      changeObjects(
        objects.map((o) =>
          o.id === editingSticky.id
            ? {
                ...o,
                text: cfg.text,
                shape: cfg.shape,
                size: cfg.size,
                color: cfg.color,
              }
            : o,
        ),
      );
      setEditingSticky(null);
    } else if (creatingStickyAt) {
      const [x, y] = creatingStickyAt;
      changeObjects([
        ...objects,
        {
          id: newId("k"),
          kind: "sticky",
          x: Math.min(820, Math.max(0, x)),
          y: Math.min(480, Math.max(0, y)),
          text: cfg.text,
          shape: cfg.shape,
          size: cfg.size,
          color: cfg.color,
          author: userName,
          created_at: new Date().toISOString(),
        },
      ]);
      setCreatingStickyAt(null);
    }
  }

  function handleSaveText(txt: string, textCol: string) {
    if (editingText) {
      changeObjects(objects.map((o) => (o.id === editingText.id ? { ...o, text: txt, color: textCol } : o)));
      setEditingText(null);
    } else if (creatingTextAt) {
      const [x, y] = creatingTextAt;
      changeObjects([
        ...objects,
        {
          id: newId("t"),
          kind: "text",
          x: Math.min(900, Math.max(0, x)),
          y: Math.min(560, Math.max(0, y)),
          text: txt,
          color: textCol,
          author: userName,
          created_at: new Date().toISOString(),
        },
      ]);
      setCreatingTextAt(null);
    }
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api<{ id: string; url: string; preview_url?: string }>("/files/upload", {
        method: "POST",
        body: formData,
      });
      const [cx, cy] = [400, 250];
      changeObjects([
        ...objects,
        {
          id: newId("i"),
          kind: "image",
          x: cx,
          y: cy,
          w: 200,
          h: 150,
          asset_id: res.id,
          preview_url: res.preview_url ?? res.url,
          color: "#9aa5b1",
          author: userName,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err: unknown) {
      setError(errorMessage(err));
    }
    e.target.value = "";
  }

  if (loading) return <Skeleton label="Loading your private whiteboard…" lines={5} />;
  if (error && !document) return <ErrorState title="Failed to load your whiteboard" message={error} />;

  return (
    <main className="personal-board" aria-label="Personal whiteboard">
      <PageHeader
        title="My Whiteboard"
        scope="Only you · Unified private whiteboard with rich drawing shapes, sticky notes, and text."
      />

      {error && (
        <p className="personal-board__error" role="alert">
          {error}
        </p>
      )}

      <section className="whiteboard" aria-label="Personal whiteboard canvas">
        <WhiteboardToolbar
          tool={tool}
          onSelectTool={setTool}
          drawMode={drawMode}
          onSelectDrawMode={setDrawMode}
          color={color}
          onSelectColor={setColor}
          stickyShape={stickyShape}
          onSelectStickyShape={setStickyShape}
          stickySize={stickySize}
          onSelectStickySize={setStickySize}
          stickyColor={stickyColor}
          onSelectStickyColor={setStickyColor}
          canWrite={!busy}
          canUndo={objects.length > 0}
          onUndo={undo}
          onFit={fit}
          onUploadImage={() => fileRef.current?.click()}
          saveState={busy ? "Saving…" : dirty ? "Unsaved changes" : "Saved"}
          saveStateOk={!dirty}
        >
          <Button
            size="sm"
            variant="primary"
            onClick={save}
            disabled={busy || !dirty}
            title="Save board to server"
          >
            💾 Save
          </Button>
        </WhiteboardToolbar>

        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg"
          hidden
          aria-label="Image to place on whiteboard"
          onChange={handleImageUpload}
        />

        <canvas
          ref={canvasRef}
          className={"canvas" + (tool === "pan" ? " tool-pan" : "")}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerLeave={() => {
            onUp();
            setHoverTooltip(null);
          }}
          aria-label="Whiteboard drawing surface"
        />

        <WhiteboardHoverTooltip data={hoverTooltip} />
      </section>

      {/* Sticky Edit Dialog */}
      <StickyEditDialog
        open={editingSticky !== null || creatingStickyAt !== null}
        title={editingSticky ? "Edit sticky note" : "Add sticky note"}
        initialConfig={
          editingSticky
            ? editingSticky.config
            : { text: "", shape: stickyShape, size: stickySize, color: stickyColor }
        }
        authorInfo={editingSticky?.authorInfo}
        onClose={() => {
          setEditingSticky(null);
          setCreatingStickyAt(null);
        }}
        onSave={handleSaveSticky}
        onDelete={
          editingSticky
            ? () => {
                changeObjects(objects.filter((o) => o.id !== editingSticky.id));
                setEditingSticky(null);
              }
            : undefined
        }
      />

      {/* Text Edit Dialog */}
      <TextEditDialog
        open={editingText !== null || creatingTextAt !== null}
        initialText={editingText?.text ?? ""}
        initialColor={editingText?.color ?? color}
        authorInfo={editingText?.authorInfo}
        onClose={() => {
          setEditingText(null);
          setCreatingTextAt(null);
        }}
        onSave={handleSaveText}
        onDelete={
          editingText
            ? () => {
                changeObjects(objects.filter((o) => o.id !== editingText.id));
                setEditingText(null);
              }
            : undefined
        }
      />
    </main>
  );
}
