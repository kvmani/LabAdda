import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

export type DragPayload = { kind: "unit" | "person"; id: string; label: string };
type Active = { payload: DragPayload; over: string | null };

const THRESHOLD = 6;

/**
 * Pointer-based drag shared by units and people: nothing happens until the pointer moves a few
 * pixels, the unit under the pointer (marked `data-drop-unit`) is tracked, and a drop only
 * reports the pair so the caller can open a review. Escape cancels. Menus offer the same actions.
 */
export function useDrag(onDrop: (payload: DragPayload, unitId: string) => void) {
  const [active, setActive] = useState<Active | null>(null);
  const cleanup = useRef<(() => void) | null>(null);
  const dragged = useRef(false);
  const drop = useRef(onDrop);
  useEffect(() => {
    drop.current = onDrop;
  }, [onDrop]);
  useEffect(() => () => cleanup.current?.(), []);

  const start = useCallback((event: ReactPointerEvent, payload: DragPayload) => {
    if (event.button !== 0) return;
    const origin = { x: event.clientX, y: event.clientY };
    let moving = false;
    const find = (x: number, y: number) =>
      document.elementFromPoint(x, y)?.closest("[data-drop-unit]")?.getAttribute("data-drop-unit") ?? null;
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", stop);
      window.removeEventListener("keydown", key);
      cleanup.current = null;
      setActive(null);
    };
    const move = (next: PointerEvent) => {
      if (!moving && Math.hypot(next.clientX - origin.x, next.clientY - origin.y) < THRESHOLD) return;
      moving = true;
      setActive({ payload, over: find(next.clientX, next.clientY) });
    };
    const up = (next: PointerEvent) => {
      const target = moving ? find(next.clientX, next.clientY) : null;
      dragged.current = moving;
      if (moving) window.setTimeout(() => (dragged.current = false), 0);
      stop();
      if (target && !(payload.kind === "unit" && target === payload.id)) drop.current(payload, target);
    };
    const key = (next: KeyboardEvent) => {
      if (next.key === "Escape") stop();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", stop);
    window.addEventListener("keydown", key);
    cleanup.current = stop;
  }, []);

  /** True just after a drag ended, so the click that follows it does not also select. */
  const wasDrag = useCallback(() => dragged.current, []);
  return { active, start, wasDrag };
}
