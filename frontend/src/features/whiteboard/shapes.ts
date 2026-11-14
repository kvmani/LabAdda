import type { DrawMode, StickyShape, StickySize } from "./types";

export const STICKY_SHAPES: { id: StickyShape; label: string; icon: string }[] = [
  { id: "rectangle", label: "Note", icon: "▭" },
  { id: "circle", label: "Circle", icon: "◯" },
  { id: "hexagon", label: "Hexagon", icon: "⬡" },
  { id: "diamond", label: "Diamond", icon: "◇" },
  { id: "cloud", label: "Cloud", icon: "☁" },
  { id: "star", label: "Star", icon: "★" },
];

export const STICKY_SIZES: { id: StickySize; label: string; scale: number }[] = [
  { id: "small", label: "Small", scale: 0.75 },
  { id: "medium", label: "Medium", scale: 1.0 },
  { id: "large", label: "Large", scale: 1.4 },
];

export const DRAW_MODES: { id: DrawMode; label: string; icon: string }[] = [
  { id: "pen", label: "Pen", icon: "✏️" },
  { id: "pencil", label: "Pencil", icon: "✎" },
  { id: "brush", label: "Marker", icon: "🖌️" },
  { id: "line", label: "Line", icon: "╱" },
  { id: "arrow", label: "Arrow", icon: "→" },
  { id: "rect", label: "Box", icon: "▭" },
  { id: "circle", label: "Circle", icon: "◯" },
];

export function getStickyDimensions(
  shape: StickyShape = "rectangle",
  size: StickySize = "medium",
): [number, number] {
  let bw = 180;
  let bh = 120;
  if (shape === "circle" || shape === "diamond") {
    bw = 150;
    bh = 150;
  } else if (shape === "hexagon") {
    bw = 160;
    bh = 140;
  } else if (shape === "cloud") {
    bw = 180;
    bh = 130;
  } else if (shape === "star") {
    bw = 160;
    bh = 160;
  }
  const scale = size === "small" ? 0.75 : size === "large" ? 1.4 : 1.0;
  return [Math.round(bw * scale), Math.round(bh * scale)];
}

export function drawStickyCanvas(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  shape: StickyShape,
  color: string,
  text: string,
): void {
  ctx.fillStyle = color;
  ctx.strokeStyle = "#00000033";
  ctx.lineWidth = 1.5;
  ctx.beginPath();

  if (shape === "circle") {
    const r = Math.min(w, h) / 2;
    ctx.arc(x + r, y + r, r, 0, Math.PI * 2);
  } else if (shape === "hexagon") {
    const cut = w * 0.22;
    ctx.moveTo(x + cut, y);
    ctx.lineTo(x + w - cut, y);
    ctx.lineTo(x + w, y + h / 2);
    ctx.lineTo(x + w - cut, y + h);
    ctx.lineTo(x + cut, y + h);
    ctx.lineTo(x, y + h / 2);
    ctx.closePath();
  } else if (shape === "diamond") {
    ctx.moveTo(x + w / 2, y);
    ctx.lineTo(x + w, y + h / 2);
    ctx.lineTo(x + w / 2, y + h);
    ctx.lineTo(x, y + h / 2);
    ctx.closePath();
  } else if (shape === "cloud") {
    const sx = w / 180;
    const sy = h / 130;
    ctx.arc(x + 45 * sx, y + 65 * sy, 30 * Math.min(sx, sy), Math.PI * 0.5, Math.PI * 1.5);
    ctx.arc(x + 75 * sx, y + 40 * sy, 32 * Math.min(sx, sy), Math.PI * 1, Math.PI * 1.85);
    ctx.arc(x + 115 * sx, y + 40 * sy, 28 * Math.min(sx, sy), Math.PI * 1.25, Math.PI * 2.05);
    ctx.arc(x + 145 * sx, y + 65 * sy, 28 * Math.min(sx, sy), Math.PI * 1.55, Math.PI * 0.5);
    ctx.arc(x + 90 * sx, y + 105 * sy, 35 * Math.min(sx, sy), 0, Math.PI);
    ctx.closePath();
  } else if (shape === "star") {
    const cx = x + w / 2;
    const cy = y + h / 2;
    const outerR = Math.min(w, h) / 2 - 4;
    const innerR = outerR * 0.46;
    for (let s = 0; s < 10; s++) {
      const r = s % 2 === 0 ? outerR : innerR;
      const angle = (s * Math.PI) / 5 - Math.PI / 2;
      const px = cx + Math.cos(angle) * r;
      const py = cy + Math.sin(angle) * r;
      if (s === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.closePath();
  } else {
    const roundRect = (
      ctx as unknown as { roundRect?: (rx: number, ry: number, rw: number, rh: number, rad: number) => void }
    ).roundRect;
    if (typeof roundRect === "function") {
      roundRect.call(ctx, x, y, w, h, 8);
    } else {
      ctx.rect(x, y, w, h);
    }
  }

  ctx.fill();
  ctx.stroke();

  // Text inside shape
  ctx.fillStyle = "#1f2933";
  ctx.font = shape === "star" ? "12px system-ui, sans-serif" : "14px system-ui, sans-serif";
  const lines = text.split("\n");
  if (shape === "rectangle") {
    ctx.textAlign = "left";
    lines.forEach((t: string, i: number) => {
      ctx.fillText(t, x + 12, y + 24 + i * 20, w - 24);
    });
  } else {
    ctx.textAlign = "center";
    const startY = y + Math.max(24, (h - lines.length * 20) / 2 + 14);
    lines.forEach((t: string, i: number) => {
      ctx.fillText(t, x + w / 2, startY + i * 20, w - 32);
    });
    ctx.textAlign = "left";
  }
}

export function generateShapePoints(
  mode: DrawMode,
  p1: [number, number],
  p2: [number, number],
): [number, number][] {
  const [x1, y1] = p1;
  const [x2, y2] = p2;

  if (mode === "line") {
    return [
      [x1, y1],
      [x2, y2],
    ];
  }
  if (mode === "arrow") {
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const headLen = 14;
    const a1 = angle - Math.PI / 6;
    const a2 = angle + Math.PI / 6;
    return [
      [x1, y1],
      [x2, y2],
      [
        Math.round((x2 - headLen * Math.cos(a1)) * 10) / 10,
        Math.round((y2 - headLen * Math.sin(a1)) * 10) / 10,
      ],
      [x2, y2],
      [
        Math.round((x2 - headLen * Math.cos(a2)) * 10) / 10,
        Math.round((y2 - headLen * Math.sin(a2)) * 10) / 10,
      ],
    ];
  }
  if (mode === "rect") {
    return [
      [x1, y1],
      [x2, y1],
      [x2, y2],
      [x1, y2],
      [x1, y1],
    ];
  }
  if (mode === "circle") {
    const cx = (x1 + x2) / 2;
    const cy = (y1 + y2) / 2;
    const rx = Math.abs(x2 - x1) / 2;
    const ry = Math.abs(y2 - y1) / 2;
    const steps = 32;
    const pts: [number, number][] = [];
    for (let i = 0; i <= steps; i++) {
      const theta = (i * 2 * Math.PI) / steps;
      pts.push([
        Math.round((cx + rx * Math.cos(theta)) * 10) / 10,
        Math.round((cy + ry * Math.sin(theta)) * 10) / 10,
      ]);
    }
    return pts;
  }
  return [
    [x1, y1],
    [x2, y2],
  ];
}

export type BoundsTarget = {
  kind: "stroke" | "sticky" | "text" | "image";
  data?: {
    points?: [number, number][];
    color?: string;
    width?: number;
    shape?: StickyShape;
    size?: StickySize;
    text?: string;
    x?: number;
    y?: number;
    w?: number;
    h?: number;
  };
  points?: [number, number][];
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  shape?: StickyShape;
  size?: StickySize;
  text?: string;
  width?: number;
  dx?: number;
  dy?: number;
};

export function bounds(o: BoundsTarget): [number, number, number, number] {
  const dx = o.dx ?? 0;
  const dy = o.dy ?? 0;
  const d = o.data ?? o;
  if (o.kind === "stroke") {
    const pts = d.points ?? o.points ?? [];
    if (!pts.length) return [dx, dy, dx, dy];
    const xs = pts.map((p) => p[0] + dx);
    const ys = pts.map((p) => p[1] + dy);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  const x = (d.x ?? o.x ?? 0) + dx;
  const y = (d.y ?? o.y ?? 0) + dy;
  if (o.kind === "image") {
    const w = d.w ?? o.w ?? 150;
    const h = d.h ?? o.h ?? 150;
    return [x, y, x + w, y + h];
  }
  if (o.kind === "sticky") {
    const shape = d.shape ?? o.shape ?? "rectangle";
    const size = d.size ?? o.size ?? "medium";
    const [w, h] = getStickyDimensions(shape, size);
    return [x, y, x + w, y + h];
  }
  // text
  const txt = d.text ?? o.text ?? "";
  const w = Math.max(40, txt.length * 9);
  const h = 24;
  return [x, y, x + w, y + h];
}

export function hit(o: BoundsTarget, x: number, y: number, tol = 6): boolean {
  const dx = o.dx ?? 0;
  const dy = o.dy ?? 0;
  const d = o.data ?? o;
  if (o.kind === "stroke") {
    const pts = d.points ?? o.points ?? [];
    const strokeW = d.width ?? o.width ?? 3;
    return pts.some((p) => Math.hypot(p[0] + dx - x, p[1] + dy - y) < tol + strokeW);
  }
  const [a, b, c, dCoord] = bounds(o);
  return x >= a - tol && x <= c + tol && y >= b - tol && y <= dCoord + tol;
}
