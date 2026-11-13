import { useRef, type PointerEvent } from "react";
import type { BoardObject } from "./types";

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

/** Draggable note with an equivalent keyboard movement path. */
export function StickyNote({ item, busy, selected, onSelect, onChange }: Props) {
  const drag = useRef<{ clientX: number; clientY: number; x: number; y: number } | null>(null);
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
      width="180"
      height="140"
      onPointerDown={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        disabled={busy}
        aria-pressed={selected}
        className={`personal-board__note board-color-${item.color}`}
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
