import { useState, type KeyboardEvent } from "react";

/** The point a chart is reading out: which series, and which position along it. */
export type Active = { series: number; index: number };

/**
 * Keyboard reading of a chart as one tab stop (UX-09). Left and right move along the series,
 * up and down switch series, Home and End jump to the ends, Escape stops reading.
 * `lengths[s]` is how many points series `s` has.
 */
export function useActivePoint(lengths: number[]) {
  const [active, setActive] = useState<Active | null>(null);

  function move(next: Active) {
    const series = Math.min(Math.max(next.series, 0), lengths.length - 1);
    const last = Math.max(0, (lengths[series] ?? 1) - 1);
    setActive({ series, index: Math.min(Math.max(next.index, 0), last) });
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    const now = active ?? { series: 0, index: 0 };
    const last = Math.max(0, (lengths[now.series] ?? 1) - 1);
    const targets: Record<string, Active | undefined> = {
      ArrowRight: { ...now, index: now.index + 1 },
      ArrowLeft: { ...now, index: now.index - 1 },
      ArrowDown: { ...now, series: now.series + 1 },
      ArrowUp: { ...now, series: now.series - 1 },
      Home: { ...now, index: 0 },
      End: { ...now, index: last },
    };
    if (event.key === "Escape") {
      setActive(null);
      return;
    }
    const target = targets[event.key];
    if (!target) return;
    event.preventDefault();
    move(target);
  }

  return {
    active,
    setActive,
    handlers: {
      onKeyDown,
      onFocus: () => setActive((current) => current ?? { series: 0, index: 0 }),
      onBlur: () => setActive(null),
    },
  };
}
