import type { Point } from "../../types";
import type { StrokePreview } from "../../realtime";
import { bounds, type Obj, type Region } from "./boardModel";
import { drawStickyCanvas, getStickyDimensions } from "./shapes";
import { canvasFont } from "./textStyle";
import { PEN_COLORS } from "./types";

/** Everything one frame of the shared whiteboard shows. */
export type BoardScene = {
  objects: Map<string, Obj>;
  selected: Obj | undefined;
  /** The selected object's in-progress drag, drawn before the move is committed. */
  drag: { dx: number; dy: number } | null;
  view: { x: number; y: number; scale: number };
  /** Image elements by asset ID, kept between frames so each preview is fetched once. */
  images: Map<string, HTMLImageElement>;
  onImageLoad: () => void;
  imageBase: string;
  panel: boolean;
  shapeDrawing: { points: Point[] } | null;
  previews: Iterable<StrokePreview>;
  drawing: { points: Point[] } | null;
  color: string;
  selection: Region | null;
};

/** Draw a frame onto the canvas at the device's pixel ratio. Pure apart from the canvas. */
export function drawBoard(canvas: HTMLCanvasElement, scene: BoardScene): void {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * ratio;
  canvas.height = rect.height * ratio;
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(
    ratio * scene.view.scale,
    0,
    0,
    ratio * scene.view.scale,
    ratio * scene.view.x,
    ratio * scene.view.y,
  );
  ctx.clearRect(
    -scene.view.x / scene.view.scale,
    -scene.view.y / scene.view.scale,
    rect.width / scene.view.scale,
    rect.height / scene.view.scale,
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
  for (const original of [...scene.objects.values()].sort((a, b) => a.rev - b.rev)) {
    const drag = scene.drag;
    const o =
      drag && original === scene.selected
        ? {
            ...original,
            dx: original.dx + drag.dx,
            dy: original.dy + drag.dy,
          }
        : original;
    if (!o.alive) continue;
    if (o.kind === "image") {
      const id = o.data.asset_id;
      let img = scene.images.get(id);
      if (!img) {
        img = new Image();
        img.onload = scene.onImageLoad;
        img.src = `${scene.imageBase}/files/${id}/preview${scene.panel ? "?panel=1" : ""}`;
        scene.images.set(id, img);
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
        drawStickyCanvas(ctx, x, y, w, h, shape, o.data.color, o.data.text, o.data);
      } else {
        ctx.fillStyle = o.data.color;
        ctx.font = canvasFont(o.data);
        ctx.textAlign = "left";
        const lines = o.data.text.split("\n");
        lines.forEach((t: string, i: number) =>
          ctx.fillText(t, x, y + (o.data.font_size ?? 16) * 1.25 + i * (o.data.font_size ?? 16) * 1.3),
        );
      }
    }
  }
  if (scene.shapeDrawing) {
    line(scene.shapeDrawing.points, scene.color, 3);
  }
  for (const p of scene.previews) line(p.points, p.color ?? "#999", 3);
  if (scene.drawing) line(scene.drawing.points, scene.color, 3);
  if (scene.selected?.alive) {
    const [x0, y0, x1, y1] = bounds(scene.selected);
    const drag = scene.drag;
    ctx.strokeStyle = PEN_COLORS[2];
    ctx.lineWidth = 2 / scene.view.scale;
    ctx.strokeRect(x0 + (drag?.dx ?? 0), y0 + (drag?.dy ?? 0), x1 - x0, y1 - y0);
  }
  if (scene.selection) {
    ctx.setLineDash([8 / scene.view.scale, 6 / scene.view.scale]);
    ctx.strokeStyle = "#1d4ed8";
    ctx.lineWidth = 2 / scene.view.scale;
    ctx.strokeRect(scene.selection.x, scene.selection.y, scene.selection.w, scene.selection.h);
    ctx.setLineDash([]);
  }
}
