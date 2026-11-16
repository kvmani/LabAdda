import type { BoardObject } from "./types";

/** Translate from an original object, keeping all stored coordinates on the private board. */
export function moveObject(object: BoardObject, dx: number, dy: number): BoardObject {
  if (object.kind === "stroke" && object.points?.length) {
    const xs = object.points.map((point) => point[0]);
    const ys = object.points.map((point) => point[1]);
    const moveX = Math.max(-Math.min(...xs), Math.min(dx, 1000 - Math.max(...xs)));
    const moveY = Math.max(-Math.min(...ys), Math.min(dy, 600 - Math.max(...ys)));
    return {
      ...object,
      points: object.points.map(([x, y]) => [x + moveX, y + moveY]),
    };
  }
  return {
    ...object,
    x: Math.min(1000, Math.max(0, (object.x ?? 0) + dx)),
    y: Math.min(600, Math.max(0, (object.y ?? 0) + dy)),
  };
}
