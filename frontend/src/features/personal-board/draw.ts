import { canvasFont } from "../whiteboard/textStyle";
import { bounds, drawStickyCanvas, getStickyDimensions, PEN_COLORS, type DrawMode } from "../whiteboard";
import type { BoardObject } from "./types";

/** Everything one frame of the private whiteboard shows. */
export type PersonalScene = {
  objects: BoardObject[];
  selected: BoardObject | undefined;
  view: { x: number; y: number; scale: number };
  /** Image elements by asset ID, kept between frames so each preview is fetched once. */
  images: Map<string, HTMLImageElement>;
  onImageLoad: () => void;
  imageBase: string;
  shapeDrawing: { points: [number, number][] } | null;
  drawing: { points: [number, number][] } | null;
  drawMode: DrawMode;
  color: string;
};

/** Draw a frame of the private board onto the canvas. Pure apart from the canvas. */
export function drawPersonalBoard(canvas: HTMLCanvasElement, scene: PersonalScene): void {
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
  ctx.translate(scene.view.x, scene.view.y);
  ctx.scale(scene.view.scale, scene.view.scale);

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

  for (const o of scene.objects) {
    if (o.kind === "image") {
      const id = o.asset_id;
      if (id) {
        let img = scene.images.get(id);
        if (!img) {
          img = new Image();
          img.onload = scene.onImageLoad;
          img.src = o.preview_url ?? `${scene.imageBase}/files/${id}/preview`;
          scene.images.set(id, img);
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
      drawStickyCanvas(ctx, o.x ?? 0, o.y ?? 0, w, h, shape, o.color, o.text ?? "", o);
    } else if (o.kind === "text") {
      ctx.fillStyle = o.color;
      ctx.font = canvasFont(o);
      ctx.textAlign = "left";
      const lines = (o.text ?? "").split("\n");
      lines.forEach((t: string, i: number) =>
        ctx.fillText(t, o.x ?? 0, (o.y ?? 0) + (o.font_size ?? 16) * 1.25 + i * (o.font_size ?? 16) * 1.3),
      );
    }
  }

  if (scene.selected) {
    const [x0, y0, x1, y1] = bounds(scene.selected);
    ctx.strokeStyle = PEN_COLORS[2];
    ctx.lineWidth = 2 / scene.view.scale;
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
  }
  if (scene.shapeDrawing) {
    line(scene.shapeDrawing.points, scene.color, 3);
  }
  if (scene.drawing) {
    const strokeW = scene.drawMode === "pencil" ? 1.5 : scene.drawMode === "brush" ? 8 : 3;
    line(scene.drawing.points, scene.color, strokeW);
  }

  ctx.restore();
}
