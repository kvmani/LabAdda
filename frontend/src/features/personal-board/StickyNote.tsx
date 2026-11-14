import { useRef, type PointerEvent, type CSSProperties } from "react";
import type { BoardObject } from "./types";
import { getStickyDimensions } from "../whiteboard/shapes";

type Props = {
  item: BoardObject;
  busy: boolean;
  selected: boolean;
  onSelect: () => void;
  onChange: (item: BoardObject) => void;
};
const arrows: Record<string, [number, number]> = {
  ArrowLeft: [-20, 0],
  ArrowRight: [20, 0],
  ArrowUp: [0, -20],
  ArrowDown: [0, 20],
};

function positioned(item: BoardObject, x: number, y: number): BoardObject {
  return { ...item, x: Math.min(820, Math.max(0, x)), y: Math.min(460, Math.max(0, y)) };
}

function shapeStyle(shape = "rectangle"): CSSProperties {
  if (shape === "circle") return { borderRadius: "50%" };
  if (shape === "hexagon") {
    return { clipPath: "polygon(22% 0%, 78% 0%, 100% 50%, 78% 100%, 22% 100%, 0% 50%)" };
  }
  if (shape === "diamond") {
    return { clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" };
  }
  if (shape === "cloud") {
    return { borderRadius: "28px" };
  }
  if (shape === "star") {
    return {
      clipPath:
        "polygon(50% 0%, 62% 35%, 100% 38%, 72% 62%, 81% 100%, 50% 78%, 19% 100%, 28% 62%, 0% 38%, 38% 35%)",
    };
  }
  return { borderRadius: "8px" };
}

/** Draggable note with shape support and an equivalent keyboard movement path. */
export function StickyNote({ item, busy, selected, onSelect, onChange }: Props) {
  const drag = useRef<{ clientX: number; clientY: number; x: number; y: number } | null>(null);
  const [w, h] = getStickyDimensions(item.shape, item.size);
  const isHex = item.color.startsWith("#");

  function start(event: PointerEvent<HTMLButtonElement>) {
    if (busy) return;
    drag.current = { clientX: event.clientX, clientY: event.clientY, x: item.x, y: item.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function move(event: PointerEvent<HTMLButtonElement>) {
    const origin = drag.current;
    const rect = event.currentTarget.closest("svg")?.getBoundingClientRect();
    if (!origin || !rect) return;
    onChange(
      positioned(
        item,
        origin.x + ((event.clientX - origin.clientX) * 1000) / rect.width,
        origin.y + ((event.clientY - origin.clientY) * 600) / rect.height,
      ),
    );
  }
  return (
    <foreignObject
      x={item.x}
      y={item.y}
      width={w}
      height={h}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        disabled={busy}
        aria-pressed={selected}
        title="Created by You (click to select and edit)"
        className={`personal-board__note ${isHex ? "" : `board-color-${item.color}`}`}
        style={{
          width: `${w}px`,
          height: `${h}px`,
          ...(isHex ? { background: item.color } : {}),
          ...shapeStyle(item.shape),
          outline: selected ? "3px solid var(--color-primary, #1565c0)" : undefined,
          outlineOffset: "2px",
          textAlign: item.shape === "rectangle" ? "left" : "center",
          padding: item.shape === "star" ? "24px 16px" : item.shape === "diamond" ? "20px 14px" : "16px",
        }}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
        onClick={onSelect}
        onKeyDown={(event) => {
          const delta = arrows[event.key];
          if (delta) {
            event.preventDefault();
            onSelect();
            onChange(positioned(item, item.x + delta[0], item.y + delta[1]));
          }
        }}
      >
        {item.text}
      </button>
    </foreignObject>
  );
}
